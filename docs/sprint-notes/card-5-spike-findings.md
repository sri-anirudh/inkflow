# Card 5 — Spike Findings: Auth + JWT + RLS Integration Chain

**Author:** Backend Engineer
**Date:** 2026-07-02
**Status:** Card 5's own acceptance criteria are met (below). **One new
blocking finding (Finding 2) discovered during follow-up work, confirmed via
reproduction, fix pending Architect review — not yet applied.** Do not treat
this doc as "all clear" for Card 6 until Finding 2 is resolved.
**Card:** Sprint 1, Card 5 (`docs/sprint-notes/sprint-1-planning.md`)
**Evidence:** `apps/api/spikes/card5_auth_jwt_rls/spike.py` (not production code — see its docstring)

---

## What this spike set out to prove

That the chain Deliverable 2 Batch 2 describes actually works, together, against
this project's real dev Supabase instance:

> Supabase Auth signup → JWT issued → verified via JWKS (ADR-004) → DB lookup
> resolves `company_id`/`role` (ADR-008) → Postgres RLS enforces tenant
> isolation on a direct query (ADR-006).

## Result

**All three acceptance criteria are met**, using `companies` and `envelopes`
as the RLS-scoped tables the criteria call for — but a follow-up pass, and a
direct question about whether `profiles` specifically had been tested, found
a real, confirmed, unfixed bug on that table (Finding 2). The spike script
ran end-to-end against the live dev project with two throwaway companies/users,
proving:

- [x] Signup → JWT → verified request → RLS-scoped query returns only that
      company's data (`companies`, `envelopes`)
- [x] A second test company/user confirms cross-tenant queries (read *and*
      write) are blocked
- [x] Every gap or surprise found — including one found after the original
      run, in response to being asked whether `profiles` was actually
      covered — is documented here, before Card 6 starts

**`profiles` itself does not currently pass the same bar** — see Finding 2.
It's outside this card's literal AC (which names no specific table), but
it's the same mechanism the AC is about, on a table central to ADR-008, so
it's flagged here rather than left for Card 6/7/8 to discover.

---

## Finding 1 (blocking, now fixed on dev): RLS policies existed but were unreachable

**What we expected:** per Batch 3 §2 / ADR-006, the `authenticated` Postgres
role should be blocked from cross-tenant rows by RLS policies, and allowed
same-tenant rows.

**What we found:** the baseline migration (`2fa42fe6f771`, Card 2) enables RLS
and creates all the policies from Batch 3 §2, but never runs the corresponding
`GRANT` statements. Postgres checks table-level privileges *before* it
evaluates row-security policies — with no `GRANT SELECT/INSERT/UPDATE/DELETE`
to `authenticated`, every query failed with `permission denied for table
companies`, never even reaching the RLS policy. Confirmed by querying
`information_schema.role_table_grants`: `authenticated` and `anon` only had
`REFERENCES`/`TRIGGER`/`TRUNCATE` (Postgres defaults), nothing that lets them
actually read or write a row.

**Why this matters:** ADR-006's entire premise is that RLS is a working
safety net "so even a bug in application-layer authorization logic can't leak
one company's data to another," and the *only* documented path that relies on
RLS directly (no app-layer check in front of it) is BR-12e's internal-recipient
dashboard read, where the web app queries Supabase directly. As migrated,
that path wasn't just unprotected — it was completely broken (every query
denied, not just insufficiently isolated), so the gap would have surfaced
immediately once any real feature touched it, but it was silent to anyone
just reading the migration and RLS policy code.

**What we did during the spike:** with explicit sign-off, applied the missing
grants directly to the dev sandbox DB as a live patch (not a migration) just
to confirm the fix resolved the immediate `permission denied` error and let
the spike run finish — granted `SELECT, INSERT, UPDATE, DELETE` broadly at
that point, more than actually needed, purely to unblock the investigation.

**Real fix, done as a proper follow-up (2026-07-02):** committed migration
`a45b7568fa27` (`grant select on rls-protected tables to authenticated`),
applied via `alembic upgrade head`, and documented as **ADR-027**
(`docs/adr/ADR-027-authenticated-role-grants.md`). The live-patch's
`INSERT`/`UPDATE`/`DELETE` grants were revoked first, since the considered
design is narrower than the spike's quick patch:

```sql
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT SELECT ON public.companies TO authenticated;
GRANT SELECT ON public.profiles TO authenticated;
GRANT SELECT ON public.envelopes TO authenticated;
GRANT SELECT ON public.recipients TO authenticated;
GRANT SELECT ON public.fields TO authenticated;
GRANT SELECT ON public.audit_events TO authenticated;
```

`SELECT` only, not the spike's broader `INSERT`/`UPDATE`/`DELETE` — all
writes to these tables go through the API's service-role connection, which
bypasses RLS/grants entirely, so `authenticated` never needs write access.
The one legitimate direct-from-browser path (BR-12e's internal-recipient
dashboard read) is read-only. `recipient_tokens` deliberately excluded —
Batch 3 §2 is explicit that no `authenticated`/`anon` role should ever get
row access to it, service-role only. Verified against
`information_schema.role_table_grants` post-migration, and the spike script
re-run clean against the migrated state (same result: all acceptance
criteria proven — the cross-tenant write attempt now fails on privilege
absence rather than the RLS `WITH CHECK` clause, since `authenticated` has
no `INSERT` at all, which is a stricter and more correct block than before).

Two companion claims proposed alongside this fix were withdrawn after
verification against the actual baseline migration: a "missing" `companies`
policy (it already existed) and `current_user_company_id()` needing a
`SECURITY DEFINER` fix (it already was). See `docs/adr/README.md` for that
note. A **third** claim proposed in the same message — that `profiles`' own
policy needed to switch to the `current_user_company_id()` helper — was
*not* withdrawn. It's confirmed as a real bug; see Finding 2 below.

---

## Finding 2 (blocking, confirmed, NOT YET FIXED — pending Architect review): `profiles` RLS policy causes infinite recursion

**Status:** Identified 2026-07-02, during a follow-up to Finding 1 prompted
by a direct question about whether this was ever actually tested (it wasn't,
in the original spike run — see below). Reproduced independently, twice, with
different query shapes. **Fix not applied** — holding for Architect review
since a companion claim in the same original proposal was wrong on two other
points (see Finding 1), so this one gets independent sign-off before any
schema change, even though the evidence here is unambiguous.

**What we found:** every query against `profiles` under the `authenticated`
role — regardless of shape (primary-key lookup, `company_id`-scoped, or a
bare unqualified `SELECT`) — raises:

```
asyncpg.exceptions.InvalidObjectDefinitionError: infinite recursion detected
in policy for relation "profiles"
```

Confirmed three ways independently: inside the extended spike script
(`[6/rls-own]` and `[7/rls-cross]` steps), and in a standalone diagnostic
script testing three query shapes against a freshly created real Supabase
Auth user + profile row, all three failing identically.

**Root cause:** `profiles`' RLS policy is a *literal self-referencing
subquery* —

```sql
CREATE POLICY profiles_company_isolation ON profiles
FOR ALL
USING (company_id = (SELECT company_id FROM profiles WHERE id = auth.uid()))
WITH CHECK (company_id = (SELECT company_id FROM profiles WHERE id = auth.uid()))
```

— rather than the `current_user_company_id()` `SECURITY DEFINER` helper every
other table's policy uses. The baseline migration's own comment explains this
was a deliberate choice: *"literal subquery, not the helper (the helper
itself queries profiles — using it here would be circular in a way that's
harder to read, even though Postgres would evaluate it fine either way)."*
**That last clause is empirically false.** Postgres's RLS query rewriter
can't resolve a policy on table X whose own condition reads from table X
again without hitting a hard recursion guard — it errors rather than
looping forever. The `SECURITY DEFINER` helper pattern exists specifically
to avoid this: the helper's inner `profiles` lookup runs as the function's
owning role (which bypasses RLS), so it never re-triggers the outer policy.
`profiles`' own policy skips that helper and hits the exact trap it exists
to avoid.

**Why this wasn't caught in the original spike run:** the original spike's
ADR-008 lookup (`[5/lookup]`) runs on the service-role connection, which
bypasses RLS by design (matching how the real API does it — Batch 2/3 are
explicit that ADR-008's lookup is never meant to go through the
`authenticated` role). The original RLS-scoped query checks (`[6/rls-own]`,
`[7/rls-cross]`) only exercised `companies` and `envelopes`, not `profiles`
— an actual coverage gap in the original run, surfaced only when directly
asked "was this actually tested?"

**Why this was invisible until now, even on the dev DB:** Finding 1's grant
gap masked it. Before ADR-027's grants were applied, every query against
`profiles` under `authenticated` failed at the privilege-check stage
(`permission denied`) — before Postgres ever got far enough to evaluate the
policy and hit the recursion. Fixing Finding 1 is what exposed Finding 2; the
two bugs were stacked in the same original migration, independently of each
other.

**Blast radius:** not a data leak — this fails closed with a hard error, the
same category of outcome R-07 cares about avoiding the *opposite* of. But it
means `profiles` is currently unusable under RLS for any direct,
non-service-role access. Nothing in the current codebase exercises this path
yet (the real `GET /me` flow goes through the API's service-role connection
per Batch 2), so no live feature is broken today — but any future feature
that queries `profiles` directly as `authenticated` (a plausible shape for
something profile-page-adjacent under BR-12e's general pattern of direct
browser-to-Supabase reads) will hard-fail the moment it's built, not
gracefully deny.

**Proposed fix (not applied):** switch `profiles`' policy to use
`current_user_company_id()`, matching every other table:

```sql
CREATE POLICY profiles_company_isolation ON profiles
FOR ALL
USING (company_id = current_user_company_id())
WITH CHECK (company_id = current_user_company_id());
```

This is the fix originally proposed (correctly, on this one point) alongside
the two withdrawn claims in Finding 1. Not applying it here — holding for
explicit Architect sign-off given the mixed accuracy of that original
proposal, despite this specific piece now having independent, reproducible
confirmation.

---

## Finding 3 (non-blocking, informational): signup → JWT isn't a one-step flow for automated testing

The dev project has `mailer_autoconfirm: false` (confirmed via
`GET /auth/v1/settings`), so the public `signUp` endpoint alone doesn't yield
a usable session — a real user has to click a confirmation email first. That's
correct and expected for the real product (nothing to fix), but it means:

- **Card 7/8's own integration tests** (and this spike) can't call `signUp`
  and immediately get a JWT. The workaround used here — and the one Cards 7/8
  should reuse — is the service-role Admin API
  (`POST /auth/v1/admin/users` with `email_confirm: true`), the same
  mechanism Batch 2 §2 already documents for the invite flow, followed by a
  normal password-grant sign-in (`POST /auth/v1/token?grant_type=password`)
  to get a real JWT through the real token-issuing path.
- This is worth stating explicitly in Testing Strategy's eventual integration
  test fixtures (not urgent — noting here so Cards 7/8 don't have to
  rediscover it).

## Finding 4 (confirms an assumption, no action needed): JWT signing scheme

Batch 2 assumes JWKS-based verification (ADR-004's "one JWT scheme"). Confirmed:
this project's `/auth/v1/.well-known/jwks.json` serves a single `ES256`
(asymmetric EC) key — not the legacy HS256 shared-secret scheme some older
Supabase projects use. This means Card 8's JWT verification middleware can
rely purely on JWKS + `PyJWK`-style key resolution, with **no JWT secret
needed anywhere in the API's config** — `JWT_JWKS_URL` in `.env.example` is
sufficient; there's no missing `SUPABASE_JWT_SECRET` variable to add.

One implementation detail for Card 8: `PyJWT`'s built-in `PyJWKClient` shells
out to stdlib `urllib` to fetch the JWKS document, which failed local TLS
verification on this machine (unrelated to Supabase — a local Python/cert-store
issue). The spike script fetches the JWKS JSON via `httpx` (already a project
dependency) and builds the verifying key from the matching `kid` manually
instead. Recommend Card 8 do the same — fetch JWKS with the project's existing
HTTP client rather than `PyJWKClient`'s internal fetcher — both to sidestep
this class of environment issue and to keep one HTTP client library in use
across the module rather than two.

---

## What was proven, concretely

Ran twice against the live dev Supabase project (`wwoshaonpsrrmmwvtwtf`), with
two throwaway companies ("Spike Co A", "Spike Co B"), each getting:

1. A pre-confirmed Supabase Auth user (Admin API)
2. A real JWT from the real password-grant login endpoint
3. That JWT verified via live JWKS fetch + signature + `aud` check (ES256)
4. A `companies` + `profiles` row created via the service-role-equivalent DB
   connection (mirrors Batch 2 §1's post-signup company creation)
5. `company_id`/`role`/`active` resolved from `profiles` via a plain lookup
   keyed on the JWT's `sub` claim (ADR-008's exact pattern)
6. One `envelopes` row seeded per company

Then, impersonating each user via `SET LOCAL ROLE authenticated` +
`request.jwt.claims` (the same GUC Supabase's `auth.uid()` reads, set by
PostgREST on every real request):

- Each user's query of `companies`/`envelopes` returned **only their own
  company's rows** — confirmed for both companies independently.
- Company A querying Company B's company row or envelopes by ID: **0 rows**,
  not an error — RLS silently filters, exactly as designed.
- Company A attempting to `INSERT` an envelope with Company B's `company_id`:
  **rejected** (`InsufficientPrivilegeError`, the `WITH CHECK` clause firing).
- Each user's query of `profiles` (own row, and cross-tenant): **fails with
  `InvalidObjectDefinitionError`, not a clean result** — see Finding 2. This
  is a fail-closed outcome (no leak), but not the working behavior the other
  five tables demonstrate.

All test companies, profiles, envelopes, and Supabase Auth users were deleted
at the end of the run (including on failure — cleanup is in a `finally`
block, which ran correctly even when the profiles query raised). Verified
zero residual rows post-run, across both the original run and the extended
run that surfaced Finding 2.

---

## Recommendation for Cards 6/7/8

- **Finding 2 blocks nothing in Card 5 itself** (its acceptance criteria are
  about the chain generally, proven via `companies`/`envelopes`), but it's a
  real, confirmed defect in a table Card 6/7 will very likely touch.
  Recommend resolving it — Architect sign-off, then a committed
  migration + ADR, same pattern as ADR-027 — before Card 6 builds anything
  that reads `profiles` under anything other than the service-role
  connection.
- **Card 7** (Company + Admin registration): the Batch 2 §1 flow is confirmed
  workable as designed — no changes needed to the approach. (This flow uses
  the service-role connection for the profile write, so Finding 2 doesn't
  block it directly — but see the note above.)
- **Card 8** (Login + JWT middleware): use `httpx` + manual JWK matching
  (Finding 4) rather than `PyJWKClient`; JWKS caching (Batch 2's ~10 min TTL
  guidance) still needs implementing — this spike fetched fresh every run,
  deliberately, to keep the spike simple. ADR-008's lookup goes through the
  service-role connection (per Batch 2/3), so Finding 2 doesn't block Card 8
  either — but any temptation to "simplify" that lookup into an
  `authenticated`-role query later will hit it immediately.
- **Finding 1:** done — migration `a45b7568fa27` / ADR-027 is committed and
  applied to the dev DB. RLS now provides actual protection on five of six
  tables; `profiles` remains blocked by Finding 2.
