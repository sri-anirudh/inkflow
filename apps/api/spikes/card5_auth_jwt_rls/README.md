# Card 5 Spike — Auth + JWT + RLS Integration Chain

Not production code. Findings are in
[`docs/sprint-notes/card-5-spike-findings.md`](../../../../docs/sprint-notes/card-5-spike-findings.md)
— that document is the actual deliverable; `spike.py` is the evidence run
behind it.

## Run it

Requires the repo-root `.env` populated with real dev Supabase credentials
and the baseline migration applied (both already true per Card 2).

```bash
cd apps/api
uv run --with "pyjwt[crypto]" python spikes/card5_auth_jwt_rls/spike.py
```

Creates two throwaway companies/users/envelopes in the dev DB and two
throwaway Supabase Auth users, and deletes all of them again before exiting
— including on failure.

`pyjwt` is intentionally not added to `pyproject.toml` — this is a
timeboxed investigation, not the real JWT verification implementation.
Card 8 owns picking (and properly adding) the real dependency.
