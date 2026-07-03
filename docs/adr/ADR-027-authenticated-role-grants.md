# ADR-027: Explicit GRANT SELECT to `authenticated` on RLS-Protected Tables

**Status:** Accepted
**Date:** 2026-07-02
**Deciders:** Technical Architect, Backend Engineer
**Related:** ADR-006 (RLS as defense-in-depth), Card 5 spike findings
(`docs/sprint-notes/card-5-spike-findings.md`)

## Decision

Explicit `GRANT SELECT` to the `authenticated` role on all six
RLS-protected application tables — `companies`, `profiles`, `envelopes`,
`recipients`, `fields`, `audit_events` — alongside their existing RLS
policies from the baseline migration.

```sql
GRANT SELECT ON companies TO authenticated;
GRANT SELECT ON profiles TO authenticated;
GRANT SELECT ON envelopes TO authenticated;
GRANT SELECT ON recipients TO authenticated;
GRANT SELECT ON fields TO authenticated;
GRANT SELECT ON audit_events TO authenticated;
```

`SELECT` only — all writes to these tables go through the API's
service-role connection, which bypasses RLS/grants entirely by design
(ADR-006). The one legitimate direct-from-browser path (`authenticated`
role, no API in front of it) is the internal-recipient dashboard read
(BR-12e), which is read-only. `authenticated` never needs
`INSERT`/`UPDATE`/`DELETE` on these tables.

`recipient_tokens` is deliberately **not** granted anything here — Batch 3
§2 already specifies zero `authenticated`/`anon` access to that table, only
the service-role connection touches it, and this ADR doesn't change that.

## Why

RLS policies don't grant access on their own — Postgres checks base table
privileges *before* it evaluates row-security policies. A role with a
matching RLS policy but no `GRANT` on the table gets `permission denied`
on every query, never reaching the policy at all.

Card 5's spike (`apps/api/spikes/card5_auth_jwt_rls/spike.py`) found
exactly this: the baseline migration (`2fa42fe6f771`) enables RLS and
creates all six policies from Batch 3 §2 correctly, but never issues the
corresponding grants. Confirmed via `information_schema.role_table_grants`
— `authenticated` had only Postgres's default `REFERENCES`/`TRIGGER`/
`TRUNCATE`, nothing that lets it read or write a row. As migrated, RLS
provided no actual protection for the one path (BR-12e) that relies on it
directly — the policies were correctly defined but silently inert.

## Alternative considered

None. This isn't a new design choice — it's completing a mechanism ADR-006
already decided but didn't fully implement. The only question was whether
to grant broader privileges (`INSERT`/`UPDATE`/`DELETE`) for convenience;
rejected in favor of the minimum privilege the one real direct-access path
actually needs, consistent with the Handbook's least-privilege principle
(§11).

## Note on a withdrawn (partially) companion ADR

A draft ADR-026 was proposed alongside this one, bundling three claims. Two
were withdrawn before being written — verification against the actual
baseline migration showed a "missing" `companies` policy and
`current_user_company_id()` needing `SECURITY DEFINER` don't describe real
problems; both were already correct as migrated. The third claim — that
`profiles`' own RLS policy needed to switch to the `current_user_company_id()`
helper instead of its literal self-referencing subquery — was **not**
withdrawn. It's confirmed as a real, reproducible bug (Postgres raises
`infinite recursion detected in policy for relation "profiles"` on every
query against that table under the `authenticated` role). See
`docs/sprint-notes/card-5-spike-findings.md` Finding 2 for the full
reproduction and root-cause writeup, and `docs/adr/README.md` for the
ADR-026 number-gap note. The fix itself is not applied here — pending
Architect sign-off before any change to `profiles`' policy.
