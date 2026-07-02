# AGENTS.md — apps/api

**Status:** Placeholder. Full template/content is Deliverable 7 (Documentation Templates) — not yet written.

## What this codebase is

The InkFlow backend: a FastAPI modular monolith. One deployable, internally split into modules by business capability under `src/modules/`.

## The one rule that must not be broken

**Module boundaries.** Modules (`identity`, `envelope`, `signing`, `document_generation`, `audit`, `notification`, `storage`) talk to each other only through service-layer function calls — never by importing another module's `repository.py` or `schemas.py` directly. `service.py` calling another module's `service.py` is fine; reaching into its `repository.py` is the violation. Cross-cutting code only (JWT verification, DB client, exceptions, logging) belongs in `src/common/`.

## Where the real documentation lives

- Root `/AGENTS.md` and `/docs/handbook/` — full engineering practice.
- `docs/handbook/deliverable-04-repository-structure.md` §2 — the exact module folder shape (`router.py` / `service.py` / `repository.py` / `schemas.py`).
- `docs/handbook/deliverable-05-coding-standards.md` — Python conventions, ORM choice (SQLAlchemy 2.0 async + Alembic).
- Each module folder gets its own scoped `AGENTS.md` once that module has real code (not yet — no business logic exists in this repo yet).
