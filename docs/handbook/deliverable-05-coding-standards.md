# InkFlow — Coding Standards

**Author:** Technical Architect
**Version:** 1.0
**Date:** 2026-07-01
**Status:** Draft — Awaiting Review
**Builds on:** Deliverable 3 (Engineering Handbook), Deliverable 4 (Repository Structure)

---

## Purpose

The Handbook (§5) stated coding *values* — simple over clever, explicit over implicit. This deliverable turns those into concrete, checkable rules: what version of what language, how files are named, how errors are raised, how a commit is written. Nothing here should contradict the Handbook; if it seems to, the Handbook wins and this document needs fixing.

---

## 1. Python (Backend — `apps/api`)

| Item | Standard |
|---|---|
| Version | Python 3.12+ (async performance improvements, current stable baseline) |
| Formatter | `ruff format` (Black-compatible, but one tool instead of two — faster, less config) |
| Linter | `ruff check` (replaces flake8 + isort + several plugins in one fast tool — this is the current mainstream default, not a niche choice) |
| Type hints | Mandatory on all function signatures. `mypy` (or `ruff`'s type-checking mode) run in CI. |
| Docstrings | Google-style, required on every `service.py` public function (business logic needs explaining; simple `router.py` passthroughs don't) |
| Async | `async def` for all I/O-bound code (DB calls, HTTP calls, Storage calls) — FastAPI and the async DB driver are both built around this; mixing sync blocking calls into an async route silently kills concurrency |

**Naming:**
- Functions/variables: `snake_case`
- Classes (Pydantic models, exceptions): `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Files: `snake_case.py`

---

## 2. TypeScript (Frontend — `apps/web`)

| Item | Standard |
|---|---|
| Mode | `strict: true` in `tsconfig.json` — no exceptions. Catches an entire class of bugs before they reach a browser. |
| Formatter | Prettier |
| Linter | ESLint with `next/core-web-vitals` config |
| Components | Function components only, `PascalCase.tsx` filenames matching the component name |
| Hooks | `useSomething.ts`, `camelCase` |
| Utilities | `camelCase.ts` |
| Folders | `kebab-case` (Next.js/React community convention) |

---

## 3. SQL / Database

- Table names: plural, `snake_case` (`envelopes`, `recipient_tokens`) — already the convention used since Deliverable 2, Batch 3.
- Column names: `snake_case`.
- Indexes: `idx_<table>_<column(s)>`.
- Foreign keys: `<referenced_table_singular>_id` (e.g., `company_id`, `owner_id`).
- Migration files: timestamp-prefixed, descriptive (`20260701_add_recipient_tokens.py`) — never edit a migration that's already been applied to a shared environment; write a new one.

### ORM decision (resolves the open item from Deliverable 4)

**Decision: SQLAlchemy 2.0 (async) + Alembic for migrations.**

This gets its own reasoning below since it's a real architectural choice, not just a style preference.

---

## 4. Markdown / Documentation

- One `#` H1 per document (the title). Everything else nests under `##`/`###`.
- Fenced code blocks always tagged with a language (` ```python `, ` ```mermaid `, etc.) — untagged blocks don't get syntax highlighting and are harder for tooling to parse.
- Mermaid diagrams over ASCII art or external image files — stays version-controlled as text, per the Handbook's "documentation is the source of truth" principle.
- Full templates (ADR, README, Sprint Notes) are Deliverable 7's job — this section just sets baseline formatting conventions those templates will follow.

---

## 5. API Naming (baseline — full REST conventions are Deliverable 8)

Consistent with what's already used across Deliverable 2's diagrams:
- Resource paths: plural nouns (`/envelopes`, `/recipients`), nested for ownership (`/envelopes/{id}/recipients`).
- Action-style endpoints where a resource verb doesn't fit cleanly: `/users/invite`, `/envelopes/{id}/void` — kebab-case for multi-word actions (`/upload-url`, not `/uploadUrl`).
- Token-authenticated recipient routes stay short and opaque by design (`/sign/{token}`, `/d/{token}`) — already established in Deliverable 2, Batch 2/4, not renamed here for consistency.

---

## 6. Logging Standards

Implements the Handbook's §6 "structured logging from day one" principle concretely:

- **Library:** `structlog` for the API and Worker — a widely-used, async-friendly structured logging library that outputs JSON without hand-rolling a formatter. More ergonomic than configuring the standard `logging` module for JSON output by hand.
- **Required fields on every log line:** `timestamp`, `level`, `module`, `request_id`. Add `user_id` or `recipient_id` where the context has one.
- **Never log:** raw tokens (signing/download), passwords, full JWTs. Log the token's hash prefix if a token needs to be traceable in logs at all.

---

## 7. Exception Handling

Implements Handbook §6's "expected vs. unexpected" distinction as actual code structure:

- A `common/exceptions/` module (per Deliverable 4) defines a small hierarchy: `InkFlowError` (base) → `BusinessRuleViolation` (expected, maps to 4xx) and `InfrastructureError` (unexpected, maps to 500).
- FastAPI exception handlers catch these at the app level and format consistent JSON error responses — individual route handlers don't hand-format error JSON themselves.
- Never a bare `except:` — always catch specific exceptions, and if re-raising, use `raise NewError(...) from original_error` so the original traceback isn't lost.

---

## 8. Configuration Management

- **API:** environment variables loaded via `pydantic-settings` — gives type-validated config (a missing required env var fails fast at startup, not three requests later).
- **Frontend:** Next.js's built-in `.env.local` handling; anything needed client-side is explicitly prefixed `NEXT_PUBLIC_` (Next.js's own convention for what's safe to ship to the browser vs. server-only).
- `.env.example` is committed with every variable name and a placeholder value; `.env`/`.env.local` are gitignored, always. No exceptions, including "just for testing."
- Full local-environment setup (which variables, how to get Supabase/Azure credentials) is Deliverable 10's job — this section is the convention, not the values.

---

## 9. Dependency Management

- **Python:** `uv` with `pyproject.toml` — a modern, fast dependency/environment manager that's become the mainstream default over Poetry/pip+venv for new projects as of the last couple of years; single tool for venv creation, dependency resolution, and lockfile management.
- **Frontend:** `npm` with `package-lock.json` — the simplest, most universally-supported choice; no strong reason to introduce `pnpm`/`yarn` for a single-app frontend at this scale.
- Lockfiles (`uv.lock`, `package-lock.json`) are always committed — reproducible installs, not "works on my machine."

---

## 10. Commit Message Format

**Conventional Commits** — `<type>(<scope>): <description>`, e.g. `feat(signing): add decline endpoint`, `fix(envelope): correct sequential order lookup`.

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`.

**Why:** it's the most widely adopted commit convention in industry, machine-parseable (enables automated changelog generation, which Branching Strategy's release-tagging process below relies on), and the `type` alone tells a reviewer what kind of change to expect before reading the diff.

---

## 11. Code Review Expectations

The *process* (PR requirements, who reviews what) is Branching Strategy's job. This is what a reviewer checks for at the code-standards level, layered on top of the Handbook §9 checklist:

- [ ] Type hints present (Python) / no `any` types without justification (TypeScript)
- [ ] Lint and format checks pass (CI-enforced, but worth a human glance too)
- [ ] No commented-out code left in — delete it, git history remembers it
- [ ] Structured logging used where the Handbook's tracing principle applies (not every line, but every meaningful state change)
- [ ] Commit messages follow Conventional Commits

---

## Architecture Decision Records

### ADR-018: SQLAlchemy 2.0 (Async) + Alembic for ORM and Migrations
**Decision:** Use SQLAlchemy's async ORM for all database access from the API and Worker, with Alembic managing schema migrations.
**Why:** SQLAlchemy is the most mature, widely-adopted Python ORM, with first-class async support (2.0's `AsyncSession`) that pairs naturally with FastAPI's async-first design. Alembic (SQLAlchemy's companion migration tool) auto-generates migrations from model changes, reducing hand-written SQL for routine schema changes while still allowing raw SQL where needed (e.g., RLS policy definitions, which live outside what an ORM models). This is the standard, boring, well-documented choice — exactly what a learning project building "real" patterns should reach for over something newer and less proven.
**Alternative considered:** SQLModel (also from the FastAPI ecosystem, unifies Pydantic + SQLAlchemy models into one class) — attractive for reducing duplication between API schemas and DB models, but newer and less battle-tested for the kind of complex, multi-join queries and RLS-aware access patterns InkFlow needs (sequential signing lookups, tenant-scoped queries). Raw `asyncpg` with hand-written SQL — rejected as unnecessary boilerplate for standard CRUD, though nothing stops dropping to raw SQL inside a `repository.py` when the ORM gets in the way.

---

## Open Items Carried Forward

- **Full REST API conventions** (status codes, pagination, versioning, error schema) — Deliverable 8.
- **Pre-commit hook configuration** (running ruff/mypy/prettier automatically) — Deliverable 10 (Development Environment).
- **README/ADR/AGENTS.md templates** — Deliverable 7.

---

*Next: Deliverable 6 — Branching Strategy (built alongside this one, see below).*
