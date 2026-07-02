# InkFlow — Repository Structure

**Author:** Technical Architect
**Version:** 1.0
**Date:** 2026-06-30
**Status:** Draft — Awaiting Review
**Builds on:** Deliverable 2 (Architecture Diagrams), Deliverable 3 (Engineering Handbook)

---

## Purpose

This defines where every file lives before any code is written. It makes two things from the Handbook literal: the module boundaries from Deliverable 2 become actual folders, and the "each module owns one folder" principle (Handbook §7) gets an actual folder to own.

---

## 1. Top-Level Layout (Monorepo)

```
inkflow/
├── apps/
│   ├── api/                 # FastAPI backend — the modular monolith
│   └── web/                 # Next.js frontend
├── docs/                    # All project documentation (source of truth)
├── infra/                   # Infrastructure-as-code, local dev config
├── scripts/                 # One-off and recurring dev scripts
├── e2e/                     # Cross-cutting end-to-end tests (span API + web)
├── .github/
│   └── workflows/           # CI/CD pipelines (Deliverable 11)
├── .env.example
├── docker-compose.yml
├── README.md                # Project overview, local setup — content: Deliverable 6
├── AGENTS.md                 # Root-level AI agent context — content: Deliverable 6
└── CONTRIBUTING.md
```

**On `AGENTS.md`:** this is the emerging tool-agnostic convention for AI-coding-agent context files (read by Claude Code and other agent tools), preferred here over the Claude-specific `CLAUDE.md` naming so the project isn't locked to one tool. It is **not** a copy of the Engineering Handbook — it's a short pointer document: what this codebase is, the one rule that must not be broken (module boundaries), and where the real detail lives (Handbook, ADRs). Every module folder under `apps/api/src/modules/` and each app root also gets its own `AGENTS.md`, scoped to that boundary — see §2.1. **This is the mechanism that makes the Handbook's module-boundary rule (§4) something an agent reads *before* acting, not just something a reviewer catches after.** Full content/template for all of these is Deliverable 6's job; this deliverable only reserves where they live.

**On READMEs:** a root `README.md` (project overview, how to get everything running locally) plus one per app (`apps/api/README.md`, `apps/web/README.md` — see §2 and §3) covering how to run that piece specifically. Complex modules (Signing, given its token/concurrency logic) may warrant their own `README.md` too; simple ones don't need one just for the sake of it. Templates: Deliverable 6.

**Why `e2e/` sits at the root, not inside `apps/api` or `apps/web`:** an end-to-end test (e.g., "sender sends envelope → recipient signs → completed PDF generated") exercises both apps together. Putting it under either one would misrepresent what it's actually testing. Full tooling/strategy for this folder is Deliverable 12's job — this just reserves its place.

---

## 2. `apps/api/` — Backend (FastAPI)

```
apps/api/
├── src/
│   ├── modules/
│   │   ├── identity/         # JWT verification, Company/Profile, invite/deactivate
│   │   ├── envelope/         # Envelope, Recipient, Field, state machine, void/resend
│   │   ├── signing/          # Token validation, signing session, signature/decline
│   │   ├── document_generation/  # Completed PDF assembly
│   │   ├── audit/            # Append-only event log
│   │   ├── notification/     # Email job construction & enqueueing
│   │   └── storage/          # Supabase Storage abstraction
│   ├── common/                # Shared, cross-cutting code — see §2.2
│   ├── config/                 # Settings, environment loading
│   ├── worker/                 # RQ worker entrypoint + job definitions
│   └── main.py                 # FastAPI app entrypoint
├── tests/
│   ├── unit/                   # Mirrors src/modules structure
│   ├── integration/
│   └── fixtures/
├── migrations/                 # Postgres schema migrations
├── pyproject.toml
├── README.md                   # How to run the API locally — content: Deliverable 6
├── AGENTS.md                    # API-scoped agent context — content: Deliverable 6
└── Dockerfile
```

### 2.1 Standard shape of a module folder

Every folder under `modules/` follows the same internal shape, so moving between modules doesn't require relearning a layout:

```
modules/envelope/
├── __init__.py
├── router.py      # FastAPI route handlers — HTTP layer only
├── service.py      # Business logic — the actual rules (BR-XX enforcement lives here)
├── repository.py   # Data access — Postgres queries, nothing else
├── schemas.py       # Pydantic request/response models
└── AGENTS.md         # Scoped agent context for this module — see §1
```

**Why this split (router / service / repository):** it's the standard layered pattern for exactly the reason the Handbook's "single responsibility" principle calls for — a route handler shouldn't contain business logic, and business logic shouldn't contain raw SQL. This also makes the Handbook's module-boundary rule (§4) mechanically enforceable: `service.py` in one module calling `service.py` in another is fine; reaching into another module's `repository.py` or `schemas.py` directly is the violation to catch in review (Handbook §9 checklist item 1).

**Exact ORM/query library choice** (SQLAlchemy vs. a lighter async driver) is deliberately not decided here — that's Deliverable 5's job (Coding Standards). This structure works either way.

### 2.2 `common/` — what qualifies as shared

Only things genuinely used by *multiple* modules belong here, to avoid it becoming a dumping ground:

```
common/
├── auth/          # JWT verification middleware, Supabase JWKS caching (Deliverable 2, Batch 2)
├── db/            # Supabase Postgres client/connection setup
├── exceptions/    # Custom exception classes (Handbook §6 — expected vs. unexpected errors)
└── logging/       # Structured (JSON) logger setup (Handbook §6)
```

If something is only used by one module, it stays in that module's folder — promoting it to `common/` prematurely is the kind of unnecessary abstraction Handbook §5 already warns against ("plain data structures until a second real use case justifies it").

---

## 3. `apps/web/` — Frontend (Next.js)

```
apps/web/
├── src/
│   ├── app/           # Routes — matches the convention from Deliverable 2, Batch 5
│   ├── components/     # Reusable UI components
│   ├── lib/             # Supabase client, API client wrapper
│   ├── hooks/            # React hooks
│   └── styles/
├── tests/
├── public/
├── package.json
├── README.md          # How to run the frontend locally — content: Deliverable 6
├── AGENTS.md           # Web-scoped agent context — content: Deliverable 6
└── Dockerfile
```

Detailed component organization and naming conventions are Deliverable 5's job; this just establishes the top-level shape.

---

## 4. `docs/` — Documentation (Source of Truth)

```
docs/
├── product/            # Product Vision and future PM deliverables
├── architecture/        # Deliverable 2 (all batches)
├── handbook/             # Deliverable 3 (this handbook)
├── adr/                   # One file per ADR — see Deliverable 6 for the template
├── api/                    # API documentation (Deliverable 7)
└── sprint-notes/
```

**Why ADRs get their own folder instead of living only inside the batch documents that introduced them:** ADR-001 through ADR-016 currently live embedded in Deliverable 2's batch files. Once Deliverable 6 (Documentation Templates) defines the standalone ADR format, each one should also exist as its own file here — searchable and referenceable independent of which batch it originated in. Flagging this now so it's not a surprise when Deliverable 6 asks for it; no action needed yet.

---

## 5. `infra/` and `scripts/`

```
infra/
├── azure/          # Container Apps, Redis config, IaC definitions
└── docker/          # docker-compose for local development

scripts/
├── setup.sh          # Local environment bootstrap
├── seed_data.py       # Sample/test data for local dev
└── supabase_keepalive.py  # Pings the Supabase project to avoid the 7-day pause (Deliverable 2, Batch 1, ADR-004)
```

Full CI/CD pipeline definitions live in `.github/workflows/`, not here — `infra/` is for infrastructure *configuration*, the pipelines themselves are Deliverable 11.

---

## 6. Directory Ownership Table

| Directory | Owning role | Notes |
|---|---|---|
| `apps/api/src/modules/*` | Backend Engineer | One folder per module, per Deliverable 2's Component Diagram |
| `apps/api/src/common/` | Backend Engineer | Cross-cutting only — see §2.2 |
| `apps/web/` | Frontend Engineer | |
| `apps/api/migrations/` | Database Engineer | |
| `docs/` | Documentation Engineer | All roles contribute; DE maintains structure/templates |
| `infra/` | DevOps Engineer | |
| `.github/workflows/` | DevOps Engineer | |
| `e2e/` | QA Engineer | |
| `apps/api/tests/`, `apps/web/tests/` | Backend / Frontend Engineer respectively | Unit + integration tests live with the code they test |
| `scripts/` | Shared — whoever needs a script owns their own | |
| `AGENTS.md` (root, per-app, per-module) | Owning role of that scope | Content template: Deliverable 6. Kept in sync with the Handbook, not a duplicate of it |

---

## Architecture Decision Records (this deliverable)

### ADR-017: Monorepo, Not Separate Repositories
**Decision:** API, web frontend, and infrastructure config all live in a single repository, not split across separate repos per app.
**Why:** Polyrepo setups earn their overhead when different teams need independent deploy cadences, different access controls, or genuinely decoupled release schedules — none of which apply here. A single developer working across the whole stack (with AI agents contributing across modules too) benefits far more from atomic commits that span, say, an API route change and its corresponding frontend call, plus a single CI pipeline to maintain instead of three. This is also the more common real-world starting point for small teams; companies that eventually split repos usually grew into that need rather than starting there — the same reasoning already used for ADR-001 (modular monolith over microservices).
**Alternative considered:** Separate repos for `api`, `web`, and `infra` — rejected as premature coordination overhead at this team size and project stage. Revisit if the team or deployment cadence genuinely diverges later.

---

## Open Items Carried Forward

- **Exact ORM/query library for the API** — Deliverable 5 (Coding Standards).
- **Standalone ADR file format**, and backfilling ADR-001–016 into `docs/adr/` as individual files — Deliverable 6 (Documentation Templates).
- **Frontend component/naming conventions** inside `apps/web/src/components/` — Deliverable 5.
- **Content/template for every `README.md` and `AGENTS.md` placed in this structure** (root, per-app, per-module) — Deliverable 6 (Documentation Templates), which explicitly owns "AI context files." This deliverable only reserved their locations.

---

*Next, pending your approval: Deliverable 5 — Coding Standards.*
