"""Card 5 spike — Auth + JWT + RLS integration chain.

NOT PRODUCTION CODE. Timeboxed investigation proving the full chain from
Deliverable 2 Batch 2 works together in this actual codebase:

    Supabase Auth signup -> JWT issued -> verified via JWKS (ADR-004)
    -> DB lookup resolves company_id/role (ADR-008)
    -> Postgres RLS enforces tenant isolation on a direct query (ADR-006)

Findings are written up separately in
docs/sprint-notes/card-5-spike-findings.md — that doc, not this script, is
the actual deliverable. This script is the evidence behind it.

Requires: repo-root `.env` populated with real dev Supabase credentials
(already the case per Card 2), and the baseline migration applied (Card 2).

Run from apps/api/:
    uv run --with "pyjwt[crypto]" python spikes/card5_auth_jwt_rls/spike.py

Creates two throwaway companies/users/envelopes in the dev DB and two
throwaway Supabase Auth users, and deletes all of them again before exiting
-- including on failure.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import jwt

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # apps/api/, for `import src...`

from src.config.settings import settings  # noqa: E402

AUTH_URL = settings.supabase_url.rstrip("/") + "/auth/v1"
JWKS_URL = f"{AUTH_URL}/.well-known/jwks.json"
TEST_PASSWORD = f"Sp1ke!{uuid.uuid4().hex}"  # never persisted, thrown away with the users


def db_dsn() -> str:
    """asyncpg wants a plain postgresql:// DSN; settings holds the +asyncpg SQLAlchemy form."""
    return settings.supabase_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def admin_headers() -> dict[str, str]:
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }


async def admin_create_user(client: httpx.AsyncClient, email: str) -> str:
    """Backend-only Admin API call, mirroring the invite flow in Batch 2 §2.

    Used here instead of the public signUp endpoint because this dev project
    has mailer_autoconfirm=false (confirmed via GET /auth/v1/settings) -- a
    real signup would sit unconfirmed until a real inbox clicks a link. The
    Admin API creates a pre-confirmed user directly, which is the only way
    to get a real JWT for an automated, unattended script.
    """
    resp = await client.post(
        f"{AUTH_URL}/admin/users",
        headers=admin_headers(),
        json={"email": email, "password": TEST_PASSWORD, "email_confirm": True},
    )
    resp.raise_for_status()
    return str(resp.json()["id"])


async def sign_in(client: httpx.AsyncClient, email: str) -> tuple[str, str]:
    """Password grant -- the same token-issuing path a real login hits."""
    resp = await client.post(
        f"{AUTH_URL}/token?grant_type=password",
        headers={"apikey": settings.supabase_anon_key},
        json={"email": email, "password": TEST_PASSWORD},
    )
    resp.raise_for_status()
    body = resp.json()
    return str(body["access_token"]), str(body["user"]["id"])


async def verify_jwt(client: httpx.AsyncClient, access_token: str) -> dict[str, Any]:
    """The FastAPI middleware's job (Batch 2 §3): verify signature + expiry via JWKS.

    Fetches JWKS via the same httpx client used for the rest of this script
    rather than PyJWT's built-in PyJWKClient -- PyJWKClient shells out to
    stdlib urllib, which fails local cert-chain verification on this
    machine's Python install (a local environment quirk, unrelated to
    Supabase or the JWKS endpoint itself, which httpx resolves fine).
    """
    resp = await client.get(JWKS_URL)
    resp.raise_for_status()
    jwks = resp.json()

    unverified_header = jwt.get_unverified_header(access_token)
    matching_key = next(k for k in jwks["keys"] if k["kid"] == unverified_header["kid"])
    signing_key = jwt.PyJWK.from_dict(matching_key)

    claims: dict[str, Any] = jwt.decode(
        access_token,
        signing_key.key,
        algorithms=["ES256"],
        audience="authenticated",
    )
    return claims


async def admin_delete_user(client: httpx.AsyncClient, user_id: str) -> None:
    resp = await client.delete(f"{AUTH_URL}/admin/users/{user_id}", headers=admin_headers())
    if resp.status_code not in (200, 204, 404):
        print(f"[cleanup] WARNING: failed to delete auth user {user_id}: {resp.status_code}")


async def query_as_user(conn: asyncpg.Connection, user_id: str, sql: str) -> list[asyncpg.Record]:
    """Simulate what PostgREST does per-request: SET ROLE authenticated + the
    request.jwt.claims GUC that Supabase's auth.uid() reads from, scoped to
    one transaction so it never leaks into later queries on this connection.
    """
    async with conn.transaction():
        await conn.execute("SET LOCAL ROLE authenticated")
        await conn.execute(
            "SELECT set_config('request.jwt.claims', $1, true)",
            json.dumps({"sub": user_id, "role": "authenticated"}),
        )
        rows = await conn.fetch(sql)
        await conn.execute("RESET ROLE")
        return rows


async def attempt_cross_tenant_insert(
    conn: asyncpg.Connection, as_user_id: str, into_company_id: str, owner_id: str
) -> bool:
    """Returns True if the write was correctly blocked by RLS's WITH CHECK clause."""
    try:
        async with conn.transaction():
            await conn.execute("SET LOCAL ROLE authenticated")
            await conn.execute(
                "SELECT set_config('request.jwt.claims', $1, true)",
                json.dumps({"sub": as_user_id, "role": "authenticated"}),
            )
            await conn.execute(
                """INSERT INTO envelopes (id, company_id, owner_id, name, status, signing_order)
                   VALUES ($1, $2, $3, 'hostile cross-tenant insert', 'draft', 'parallel')""",
                str(uuid.uuid4()),
                into_company_id,
                owner_id,
            )
            await conn.execute("RESET ROLE")
        return False  # insert succeeded -- RLS gap
    except asyncpg.exceptions.InsufficientPrivilegeError:
        return True


async def main() -> None:
    suffix = uuid.uuid4().hex[:8]
    companies = [
        {"label": "Spike Co A", "email": f"spike-a-{suffix}@inkflow-spike.test"},
        {"label": "Spike Co B", "email": f"spike-b-{suffix}@inkflow-spike.test"},
    ]

    conn = await asyncpg.connect(db_dsn())
    created_auth_user_ids: list[str] = []
    all_passed = True

    try:
        # --- static check: current_user_company_id()'s SECURITY DEFINER status ------
        # A proposed "fix" (later withdrawn, see docs/adr/README.md) assumed this
        # function wasn't SECURITY DEFINER. Checked directly against pg_proc rather
        # than trusted from reading the migration source, since that's the actual
        # live property that matters for the profiles self-reference below.
        helper_row = await conn.fetchrow(
            "SELECT prosecdef FROM pg_proc WHERE proname = 'current_user_company_id'"
        )
        assert helper_row is not None, "current_user_company_id() not found in pg_proc"
        assert helper_row["prosecdef"] is True, "current_user_company_id() is NOT SECURITY DEFINER"
        print("[0/static] current_user_company_id(): confirmed SECURITY DEFINER via pg_proc")

        async with httpx.AsyncClient(timeout=15) as client:
            # --- signup (Admin API, pre-confirmed) ---------------------------------
            for c in companies:
                c["user_id"] = await admin_create_user(client, c["email"])
                created_auth_user_ids.append(c["user_id"])
                print(f"[1/signup] {c['label']}: created auth user {c['user_id']}")

            # --- login -> JWT --------------------------------------------------------
            for c in companies:
                token, uid = await sign_in(client, c["email"])
                assert uid == c["user_id"], "sign-in returned a different user id than signup"
                c["access_token"] = token
                print(f"[2/login] {c['label']}: signed in, JWT issued")

            # --- FastAPI-middleware-equivalent: verify via JWKS ----------------------
            for c in companies:
                claims = await verify_jwt(client, c["access_token"])
                assert claims["sub"] == c["user_id"], "verified sub does not match signed-in user"
                c["claims"] = claims
                print(
                    f"[3/verify] {c['label']}: JWT verified via JWKS "
                    f"(alg=ES256, sub={claims['sub']}, aud={claims['aud']})"
                )

            # --- Company+Profile creation (service-role connection, bypasses RLS) ---
            # Mirrors Batch 2 §1: the API creates Company+Profile right after Auth
            # confirms the identity exists. This connection uses the `postgres`
            # pooler role, which is BYPASSRLS in Supabase -- the same trust level
            # as the app's real service-role DB connection (ADR-006's documented
            # exception).
            for c in companies:
                company_id = str(uuid.uuid4())
                await conn.execute(
                    "INSERT INTO companies (id, name) VALUES ($1, $2)", company_id, c["label"]
                )
                await conn.execute(
                    """INSERT INTO profiles (id, company_id, full_name, email, role, active)
                       VALUES ($1, $2, $3, $4, 'admin', true)""",
                    c["user_id"],
                    company_id,
                    f"{c['label']} Admin",
                    c["email"],
                )
                c["company_id"] = company_id
                print(f"[4/provision] {c['label']}: company {company_id} + profile created")

            # --- ADR-008: per-request DB lookup of company_id/role/active -----------
            for c in companies:
                row = await conn.fetchrow(
                    "SELECT company_id, role, active FROM profiles WHERE id = $1", c["user_id"]
                )
                assert row is not None, "profile lookup returned nothing for a just-created profile"
                assert str(row["company_id"]) == c["company_id"]
                assert row["role"] == "admin"
                assert row["active"] is True
                print(
                    f"[5/lookup] {c['label']}: DB lookup resolved "
                    f"company_id={row['company_id']} role={row['role']} active={row['active']}"
                )

            # --- seed one envelope per company so RLS has real rows to isolate -------
            for c in companies:
                env_id = str(uuid.uuid4())
                await conn.execute(
                    """INSERT INTO envelopes (id, company_id, owner_id, name, status, signing_order)
                       VALUES ($1, $2, $3, $4, 'draft', 'parallel')""",
                    env_id,
                    c["company_id"],
                    c["user_id"],
                    f"{c['label']} Envelope",
                )
                c["envelope_id"] = env_id

            # --- RLS same-company query ------------------------------------------------
            for c in companies:
                company_rows = await query_as_user(
                    conn, c["user_id"], "SELECT id, name FROM companies"
                )
                seen_company_names = {r["name"] for r in company_rows}
                ok = seen_company_names == {c["label"]}
                all_passed &= ok
                verdict = "OK" if ok else "FAIL"
                print(
                    f"[6/rls-own] {c['label']}: sees companies={seen_company_names} "
                    f"(expected only own) -> {verdict}"
                )

                env_rows = await query_as_user(conn, c["user_id"], "SELECT id, name FROM envelopes")
                seen_env_names = {r["name"] for r in env_rows}
                ok = seen_env_names == {f"{c['label']} Envelope"}
                all_passed &= ok
                verdict = "OK" if ok else "FAIL"
                print(
                    f"[6/rls-own] {c['label']}: sees envelopes={seen_env_names} "
                    f"(expected only own) -> {verdict}"
                )

                # profiles itself -- deliberately its own check, not folded into the
                # loop above. This is the one table whose policy is a *literal
                # self-referencing subquery* (company_id = (SELECT company_id FROM
                # profiles WHERE id = auth.uid())), not the current_user_company_id()
                # helper every other table's policy uses.
                #
                # KNOWN BUG, confirmed 2026-07-02, fix pending Architect review (not
                # applied here -- see docs/sprint-notes/card-5-spike-findings.md
                # "Finding 2"): every query shape against profiles under the
                # authenticated role (PK-scoped, company_id-scoped, unqualified) raises
                # asyncpg.exceptions.InvalidObjectDefinitionError: infinite recursion
                # detected in policy for relation "profiles". Postgres's RLS rewriter
                # can't resolve a policy that queries the same table it protects
                # without the SECURITY DEFINER bypass -- caught and recorded as a
                # documented FAIL here rather than left to crash the whole run.
                try:
                    profile_rows = await query_as_user(
                        conn, c["user_id"], "SELECT id, full_name FROM profiles"
                    )
                    seen_profile_names = {r["full_name"] for r in profile_rows}
                    ok = seen_profile_names == {f"{c['label']} Admin"}
                    verdict = "OK" if ok else "FAIL"
                    print(
                        f"[6/rls-own] {c['label']}: sees profiles={seen_profile_names} "
                        f"(expected only own) -> {verdict}"
                    )
                except asyncpg.exceptions.InvalidObjectDefinitionError as e:
                    ok = False
                    print(f"[6/rls-own] {c['label']}: profiles query FAILED (known bug) -> {e}")
                all_passed &= ok

            # --- RLS cross-tenant block: read -------------------------------------------
            a, b = companies
            cross_rows = await query_as_user(
                conn, a["user_id"], f"SELECT id FROM companies WHERE id = '{b['company_id']}'"
            )
            read_blocked = len(cross_rows) == 0
            all_passed &= read_blocked
            verdict = "BLOCKED (OK)" if read_blocked else "LEAKED (FAIL)"
            print(
                f"[7/rls-cross] {a['label']} reading {b['label']}'s company row: "
                f"{len(cross_rows)} rows -> {verdict}"
            )

            cross_env_sql = f"SELECT id FROM envelopes WHERE company_id = '{b['company_id']}'"
            cross_env_rows = await query_as_user(conn, a["user_id"], cross_env_sql)
            read_blocked_env = len(cross_env_rows) == 0
            all_passed &= read_blocked_env
            verdict = "BLOCKED (OK)" if read_blocked_env else "LEAKED (FAIL)"
            print(
                f"[7/rls-cross] {a['label']} reading {b['label']}'s envelopes: "
                f"{len(cross_env_rows)} rows -> {verdict}"
            )

            # Known bug (see the [6/rls-own] profiles block above): this always
            # raises rather than blocking cleanly. Still a safe fail-closed outcome
            # (hard error, not a leak) but not the "0 rows" result this AC wants.
            cross_profile_sql = f"SELECT id FROM profiles WHERE company_id = '{b['company_id']}'"
            try:
                cross_profile_rows = await query_as_user(conn, a["user_id"], cross_profile_sql)
                read_blocked_profile = len(cross_profile_rows) == 0
                verdict = "BLOCKED (OK)" if read_blocked_profile else "LEAKED (FAIL)"
                print(
                    f"[7/rls-cross] {a['label']} reading {b['label']}'s profile: "
                    f"{len(cross_profile_rows)} rows -> {verdict}"
                )
            except asyncpg.exceptions.InvalidObjectDefinitionError as e:
                read_blocked_profile = False
                print(
                    f"[7/rls-cross] {a['label']} reading {b['label']}'s profile: "
                    f"FAILED (known bug, fail-closed not fail-clean) -> {e}"
                )
            all_passed &= read_blocked_profile

            # --- RLS cross-tenant block: write ------------------------------------------
            write_blocked = await attempt_cross_tenant_insert(
                conn, a["user_id"], b["company_id"], a["user_id"]
            )
            all_passed &= write_blocked
            verdict = "BLOCKED (OK)" if write_blocked else "SUCCEEDED (FAIL)"
            print(f"[7/rls-cross] {a['label']} inserting an envelope into {b['label']}: {verdict}")

    finally:
        # --- cleanup: DB rows first (service-role connection), then auth users -------
        for c in companies:
            if "company_id" in c:
                # cascades to profiles/envelopes
                await conn.execute("DELETE FROM companies WHERE id = $1", c["company_id"])
        await conn.close()
        async with httpx.AsyncClient(timeout=15) as client:
            for uid in created_auth_user_ids:
                await admin_delete_user(client, uid)
        print("[cleanup] removed test companies/profiles/envelopes and auth users")

    print()
    verdict = "ALL ACCEPTANCE CRITERIA PROVEN" if all_passed else "AT LEAST ONE CHECK FAILED"
    print("RESULT:", verdict)
    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
