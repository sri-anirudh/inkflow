# InkFlow

An educational project building an enterprise-grade e-signature platform (inspired by DocuSign), at a scale realistic for a production SaaS serving ~1,000 users. See `docs/product/product-vision.md` for the full pitch.

**Status:** Sprint 1 — repo scaffold. Not runnable end-to-end yet (Supabase provisioning is Sprint 1 Card 2, working Docker Compose is Card 3).

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

## Contributing

See `CONTRIBUTING.md` for branch naming, commit format, and the PR process.
