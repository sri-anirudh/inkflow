# InkFlow — Development Environment

**Author:** Technical Architect
**Version:** 1.0
**Date:** 2026-07-01
**Status:** Draft — Awaiting Review
**Builds on:** Deliverable 4 (Repository Structure), Coding Standards (tool choices), your environment: macOS, Docker Desktop already set up

---

## Purpose

How to get InkFlow running on a laptop before touching production infrastructure. Scoped to macOS + Docker Desktop since that's confirmed as your setup — no need to hedge for Windows/Linux instructions you won't use.

---

## 1. The One Real Correction to the Original Scope

The Sprint 0 deliverable table assumes a local **PostgreSQL** container. That's no longer right, given ADR-004 (Supabase adoption): running Postgres locally in Docker would mean developing against a different Postgres version, missing extensions, and no RLS policies compared to what actually runs in Supabase — a local environment that lies to you about how the real system behaves.

**Correct version:** local dev talks to a real Supabase project (free tier — a second project, separate from whatever gets used for Staging/Production, see Deliverable 11). Docker is only for the pieces that genuinely are local: the API, the Worker, and Redis.

## 2. What's Local vs. Cloud

| Component | Where it runs in dev |
|---|---|
| API (FastAPI) | Docker, local |
| Worker (RQ) | Docker, local |
| Redis | Docker, local |
| Postgres + Auth + Storage | Supabase (cloud) — a dedicated free-tier "dev" project |
| Web app (Next.js) | `npm run dev`, local — not containerized (Next.js's dev server with hot reload is materially better outside Docker; no benefit to containerizing it locally) |
| Email (SendGrid) | Real SendGrid, sandbox/test API key — emails actually send during dev, easiest way to verify templates render correctly |

## 3. Prerequisites (macOS)

- Docker Desktop — ✅ already set up.
- **`uv`** (Python package/env manager, Coding Standards §9) — `brew install uv`.
- **Node.js LTS** — via `nvm` (`brew install nvm`, then `nvm install --lts`) rather than a bare Homebrew Node install, so you can pin versions per-project without fighting a global one later.
- **Supabase CLI** — `brew install supabase/tap/supabase` — used for running migrations against the dev project and generating typed DB clients, not for running Supabase itself locally (see §6 for why).

## 4. `docker-compose.yml` (local services)

```yaml
services:
  api:
    build: ./apps/api
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [redis]
    volumes: ["./apps/api:/app"]  # live reload

  worker:
    build: ./apps/api
    command: rq worker --url redis://redis:6379
    env_file: .env
    depends_on: [redis]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

No `postgres` service — deliberately, per §1.

## 5. Environment Variables

`.env.example` (committed, placeholders only — real values never committed, per Coding Standards §8):

```
# Supabase (dev project)
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# Redis
REDIS_URL=redis://redis:6379

# SendGrid
SENDGRID_API_KEY=
SENDGRID_FROM_EMAIL=

# App
JWT_JWKS_URL=            # Supabase's JWKS endpoint, for API-side JWT verification (Deliverable 2, Batch 2)
ENVIRONMENT=development
```

## 6. Why Not Supabase CLI's Local Stack

Supabase CLI can spin up a fully local Supabase (Postgres + Auth + Storage) via Docker, entirely offline. Worth knowing it exists, but **not the default here**: it means maintaining two separate Supabase configurations (local Docker stack + cloud dev project) in sync, for a benefit (offline development) that doesn't matter much for a solo developer who's online anyway. A real cloud dev project is simpler to keep in sync with Staging/Production and is one less thing to debug when "it works on my machine" turns out to mean "my local Supabase Docker image is stale." Revisit only if offline development becomes a real, recurring need.

## 7. Startup Flow (`scripts/setup.sh`)

```bash
#!/usr/bin/env bash
set -e
cp .env.example .env                    # then fill in real values manually
uv sync --directory apps/api            # install Python deps
cd apps/web && npm install && cd ../..  # install frontend deps
supabase link --project-ref <dev-project-ref>
supabase db push                        # apply migrations to the dev project
docker compose up -d redis api worker
cd apps/web && npm run dev              # separate terminal, not backgrounded
```

## 8. Pre-commit Hooks

`pre-commit` framework (Python-ecosystem standard, works fine for a mixed Python/TS repo), running on every commit:
- `ruff format` + `ruff check` (Python)
- `mypy` (Python types)
- `prettier` + `eslint` (TypeScript)

Configured once in `.pre-commit-config.yaml` at repo root, installed via `pre-commit install` — part of `setup.sh` above.

## 9. IDE

**Recommended: VS Code** — not mandated, but the extension list below assumes it since it's the most common choice for this stack and has first-class support for everything here. Kept intentionally short — a wall of "recommended extensions" nobody installs isn't useful:

- Python + Pylance (Microsoft)
- ESLint, Prettier
- Docker
- Mermaid Preview (for reading the architecture docs without leaving the editor)

## 10. Running Tests Locally

- Backend: `uv run pytest` inside `apps/api` (talks to the dev Supabase project — no separate local test DB; test data is created/torn down per-test, see Deliverable 12 for the exact pattern).
- Frontend: `npm test` inside `apps/web`.
- Full stack (`e2e/`): Deliverable 12.

---

## Architecture Decision Records

### ADR-022: Local Development Targets a Cloud Supabase Project, Not Containerized Postgres
**Decision:** Local dev uses a dedicated Supabase free-tier project for Postgres/Auth/Storage; only API, Worker, and Redis run in local Docker.
**Why:** A local Postgres container would diverge from the real Supabase runtime (version, extensions, RLS) — developing against something that behaves differently from production undermines the point of having RLS-based tenant isolation at all, since you'd never actually exercise those policies locally. A real dev-tier cloud project costs nothing (free tier) and guarantees dev matches Staging/Production behavior.
**Alternative considered:** Supabase CLI's local Docker stack — rejected as added sync overhead for a solo developer without a real offline-development need; revisit if that need emerges.

---

## Open Items Carried Forward

- **Dev Supabase project provisioning** (actual project creation, migration baseline) — first task once this deliverable is approved, not a separate deliverable.

---

*Next: Deliverable 11 — CI/CD Design.*
