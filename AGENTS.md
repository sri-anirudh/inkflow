# AGENTS.md — InkFlow

**Status:** Placeholder. Full template/content is Deliverable 7 (Documentation Templates) — not yet written. This is the minimum viable version so an agent landing here before Deliverable 7 exists still has the one rule that matters.

## What this codebase is

InkFlow is an educational project building an enterprise-grade e-signature platform (inspired by DocuSign), at a scale realistic for a production SaaS serving ~1,000 users. It's a monorepo: `apps/api` (FastAPI modular monolith) + `apps/web` (Next.js).

## The one rule that must not be broken

**Module boundaries.** The API is one deployable, internally split into modules by business capability (Identity, Envelope, Signing, Document Generation, Audit, Notification, Storage — see `apps/api/src/modules/`). Modules talk to each other through service-layer function calls only — never by importing another module's database models or repository directly. If Signing needs envelope data, it calls `envelope_service.get_envelope(...)`, not `from envelope.models import Envelope`.

## Where the real documentation lives

- `docs/handbook/` — Engineering Handbook (start here) plus Repository Structure, Coding Standards, Branching Strategy, Development Environment, CI/CD Design, Testing Strategy.
- `docs/architecture/` — system diagrams, data model, request flows, ADRs 001–016.
- `docs/product/` — Product Vision and project management setup.
- `docs/api/` — REST API conventions.
- `docs/adr/` — standalone ADR files (currently empty — ADRs still live embedded in their originating deliverables under `docs/architecture/` and `docs/handbook/`; backfilling into standalone files is deferred to Deliverable 7's ADR template, per Deliverable 4 §4 — note that D4's own text says "Deliverable 6" here, which is stale; see the PR description for why).

Read `docs/handbook/deliverable-03-engineering-handbook.md` first — it's the front door and points to everything else.

Every app and every module folder gets its own scoped `AGENTS.md`; this root one is intentionally short.
