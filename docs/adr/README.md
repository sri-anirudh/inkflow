# ADRs

This folder is intentionally empty as of the initial repo scaffold.

ADR-001 through ADR-024 currently live embedded in the deliverables that introduced them (`docs/architecture/deliverable-02-*.md` for ADR-001–016, `docs/handbook/deliverable-04-repository-structure.md` for ADR-017, `deliverable-05-coding-standards.md` for ADR-018, `deliverable-06-branching-strategy.md` for ADR-019, `deliverable-10-development-environment.md` for ADR-022, `deliverable-11-cicd-design.md` for ADR-023–024).

Per Deliverable 4 §4: once Deliverable 7 (Documentation Templates — not yet written) defines the standalone ADR format, each one should also exist here as its own file, searchable independent of which deliverable it originated in. No action needed until then.

ADR-025 (Playwright for End-to-End Tests) is embedded in `docs/handbook/deliverable-12-testing-strategy.md`.

**ADR-026 was proposed but never created — partially withdrawn, partially confirmed.** During the Card 5 spike, content attributed to the Technical Architect proposed it, bundling three claims. Two were withdrawn: verification against the actual baseline migration (`apps/api/migrations/versions/20260701_baseline_schema_with_rls.py`) showed a "missing" `companies` RLS policy and a `SECURITY DEFINER` fix for `current_user_company_id()` don't describe real problems — the policy was already present and the function was already `SECURITY DEFINER`. The third claim — that `profiles`' own policy needed to switch to the `current_user_company_id()` helper instead of its literal self-referencing subquery — was **not** withdrawn. It's confirmed as a real, reproducible bug (Postgres raises `infinite recursion detected in policy for relation "profiles"` on every query against that table under the `authenticated` role). See `docs/sprint-notes/card-5-spike-findings.md` Finding 2 for the reproduction. No ADR-026 file was created either way — the two false claims made the original proposal unsafe to file as-is, and the one real claim is pending Architect sign-off before a fix is written up and applied. Flagging the number gap here, rather than silently reusing 026 later, per the Handbook's "flag assumptions instead of burying them" principle.

**ADR-027** (`ADR-027-authenticated-role-grants.md`) is the first standalone ADR file in this folder — the one genuine gap the same spike found (RLS policies with no underlying table grants, ADR-006 incompletely implemented). It does not cover the `profiles` recursion bug above — that's a separate, still-open issue.
