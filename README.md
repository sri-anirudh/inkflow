# InkFlow

An educational project building an enterprise-grade e-signature platform (inspired by DocuSign), at a scale realistic for a production SaaS serving ~1,000 users. See `docs/product/product-vision.md` for the full pitch.

**Status:** Sprint 1 — API, Worker, and Redis run locally via Docker Compose against a real Supabase dev project. No product features yet (that starts with Card 7).

## Layout

- `apps/api/` — FastAPI backend (modular monolith)
- `apps/web/` — Next.js frontend
- `docs/` — all project documentation, source of truth
- `infra/` — infrastructure-as-code, local dev config
- `scripts/` — one-off and recurring dev scripts
- `e2e/` — cross-cutting end-to-end tests

Full structure rationale: `docs/handbook/deliverable-04-repository-structure.md`.

## Local setup

Prerequisites (macOS): Docker Desktop, [`uv`](https://docs.astral.sh/uv/), Node.js (via `nvm`), [Supabase CLI](https://supabase.com/docs/guides/cli).

```bash
./scripts/setup.sh
```

See `docs/handbook/deliverable-10-development-environment.md` for the full rationale and what runs where (local Docker vs. cloud Supabase).

**One gotcha:** `SUPABASE_DB_URL` in `.env` must use Supabase's **session pooler** connection string (`postgres.<ref>@aws-x-region.pooler.supabase.com:5432`), not the direct `db.<ref>.supabase.co` host — the direct host is IPv6-only and Docker's default network can't reach it (`docker compose up` will show `db: "unreachable"` from `/health` if you use the wrong one). Find the pooler string in the Supabase dashboard under Project Settings → Database, or in `supabase/.temp/pooler-url` after `supabase link`.

## Contributing

See `CONTRIBUTING.md` for branch naming, commit format, and the PR process.
