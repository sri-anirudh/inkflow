# Card 5 — Spike Findings: Auth + JWT + RLS Integration Chain

**Author:** Backend Engineer
**Date:** 2026-07-02
**Status:** Complete
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

**All three acceptance criteria are met**, but only after fixing a real gap
found along the way (below). The spike script ran end-to-end against the live
dev project with two throwaway companies/users, proving:

- [x] Signup → JWT → verified request → RLS-scoped query returns only that
      company's data
- [x] A second test company/user confirms cross-tenant queries (read *and*
      write) are blocked
- [x] The gap found is documented here, before Cards 7/8 start

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

**What we did:** with explicit sign-off, applied the missing grants directly
to the dev sandbox DB (not committed as a migration — that's the Database
Engineer's lane) to confirm the fix actually resolves it:

```sql
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.companies TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.profiles TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.envelopes TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.recipients TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.fields TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.audit_events TO authenticated;
```

`recipient_tokens` deliberately excluded — Batch 3 §2 is explicit that no
`authenticated`/`anon` role should ever get row access to it, service-role
only. This matches that table's already-correct "zero policies, zero grants"
state.

**Required follow-up (not done here — flagging per role charter, this is a
schema/migration change):** a new Alembic migration, owned by the Database
Engineer, adding these grants to the schema definition itself before Card 7
starts, since the current migration produces a DB where RLS silently does
nothing. Recommend filing this as its own chore card rather than folding it
into Card 7/8's estimate, per this spike's own sizing note.

---

## Finding 2 (non-blocking, informational): signup → JWT isn't a one-step flow for automated testing

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

## Finding 3 (confirms an assumption, no action needed): JWT signing scheme

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

All test companies, profiles, envelopes, and Supabase Auth users were deleted
at the end of the run (including on failure — cleanup is in a `finally`
block). Verified zero residual rows post-run.

---

## Recommendation for Cards 7/8

- **Card 7** (Company + Admin registration): the Batch 2 §1 flow is confirmed
  workable as designed — no changes needed to the approach.
- **Card 8** (Login + JWT middleware): use `httpx` + manual JWK matching
  (Finding 3) rather than `PyJWKClient`; JWKS caching (Batch 2's ~10 min TTL
  guidance) still needs implementing — this spike fetched fresh every run,
  deliberately, to keep the spike simple.
- **Before Card 7 starts:** file and merge the grants migration (Finding 1).
  Until that lands, RLS on this project provides no actual protection —
  worth treating as higher priority than its `S`-sized spike origin implies.
