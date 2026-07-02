# InkFlow — API Conventions

**Author:** Technical Architect
**Version:** 1.0
**Date:** 2026-07-01
**Status:** Draft — Awaiting Review
**Builds on:** Coding Standards §5 (naming baseline), Deliverable 2 (endpoints already implied by diagrams)

---

## Purpose

Coding Standards §5 set naming baselines. This is the full contract: request/response shape, pagination, errors, status codes, auth headers, versioning — what a Backend Engineer implements directly and a Frontend Engineer codes a client against.

---

## 1. Resource Naming — recap + extension

- Plural nouns, nested for ownership: `/envelopes`, `/envelopes/{id}/recipients`.
- Kebab-case for action-style endpoints: `/users/invite`, `/envelopes/{id}/void`, `/envelopes/{id}/upload-url`.
- Token-authenticated routes stay short and opaque: `/sign/{token}`, `/d/{token}` (unchanged since Deliverable 2).

## 2. URI Versioning

All routes prefixed `/api/v1/...`.

**Why now, with only one client:** retrofitting a version prefix after routes exist means either breaking every existing frontend call or running a messy migration. Adding it costs nothing today. Not over-building — no content negotiation, no version-per-resource, just a prefix reserved for the day a breaking change is unavoidable.

## 3. Request / Response Format

- All bodies JSON, `Content-Type: application/json`.
- Single resource: return the object directly (`{ "id": ..., "status": ... }`), not wrapped.
- List endpoints: wrapped, to carry pagination metadata alongside the data:
```json
{
  "data": [ { "id": "...", "status": "sent" } ],
  "pagination": { "page": 1, "page_size": 20, "total": 47 }
}
```

## 4. Pagination

**Offset/limit** (`?page=1&page_size=20`), not cursor-based.

**Why:** cursor pagination earns its complexity at high write-concurrency, real-time-feed scale — neither applies here (a company's envelope list is, at most, a few thousand rows over the platform's lifetime at ~1,000 users). Offset/limit is simpler to implement, simpler for the frontend to reason about (jump to page 3), and the standard default absent a specific reason not to use it.

## 5. Filtering & Sorting

Query params, not custom endpoints: `?status=sent&sort=-created_at` (`-` prefix = descending). Filterable fields are allow-listed per endpoint in `schemas.py` — never pass raw query params into a DB query unfiltered (Handbook §11, never trust client input).

## 6. Error Response Format

```json
{
  "error": {
    "code": "ENVELOPE_ALREADY_COMPLETED",
    "message": "This envelope has already been completed and cannot be voided.",
    "details": null
  }
}
```

Maps directly to the exception hierarchy from Coding Standards §7: `BusinessRuleViolation` subclasses carry their own `code` and human-readable `message`; `InfrastructureError` returns a generic message (never leaks internals like a stack trace or SQL error to the client).

## 7. Status Codes

| Code | Used for |
|---|---|
| 200 | Successful GET/PATCH |
| 201 | Resource created (`POST /envelopes`) |
| 204 | Successful action with no body (`POST /envelopes/{id}/void`) |
| 400 | Malformed request (bad JSON, wrong types) |
| 401 | Missing/invalid JWT |
| 403 | Valid JWT, but caller lacks permission (RLS/app-layer authorization failure) |
| 404 | Resource doesn't exist, or exists but caller shouldn't know that (tenant isolation) |
| 409 | Conflict — concurrent action lost a race (e.g., token already consumed, Batch 4 §2) |
| 410 | Signing/download token structurally valid but no longer usable (expired, envelope voided/declined) — distinct from 404 so the frontend can show the right message (Deliverable 2, Batch 4 §1) |
| 422 | Validation failure — Pydantic schema rejection, field-level errors in `details` |
| 429 | Rate limited (signing/download endpoints, per ADR-013) |
| 500 | Unexpected/infrastructure error |

## 8. Authentication Headers

- Session endpoints: `Authorization: Bearer <supabase_jwt>` (Deliverable 2, Batch 2).
- Recipient endpoints: token is in the **path**, not a header — `/sign/{token}` — since these links are meant to work from a plain browser click with zero client-side logic required.

## 9. Validation

Pydantic `schemas.py` models are the single source of truth for request/response shape — no manual validation logic scattered in route handlers. A validation failure returns 422 with per-field messages, not a generic 400.

## 10. API Documentation

**No separate hand-written API doc.** FastAPI auto-generates OpenAPI/Swagger (`/docs`) and ReDoc (`/redoc`) directly from the Pydantic schemas and route definitions — free, always in sync with the actual code (a hand-maintained doc drifts; a generated one can't). This is the same "don't build what's already solved" principle from the Learning Philosophy applied to documentation itself. Deliverable 7 (Documentation Templates, still pending) covers narrative docs like ADRs and READMEs — this is different, and doesn't need a template because there's no manual authoring step.

---

## Architecture Decision Records

### ADR-020: URI Versioning from Day One (`/api/v1`)
**Decision:** Every route lives under `/api/v1/`, even with a single first-party client.
**Why:** Trivial to add now, painful to retrofit — the standard "cheap insurance" argument for API versioning applies even to internal-only APIs.
**Alternative considered:** No versioning until actually needed — rejected; the cost asymmetry (near-zero now vs. a breaking migration later) makes waiting the worse bet.

### ADR-021: Offset/Limit Pagination, Not Cursor-Based
**Decision:** All list endpoints use `page`/`page_size` query params.
**Why:** Simpler to implement and consume; cursor pagination solves problems (stable pagination under heavy concurrent writes, infinite-scroll feeds) that don't exist at InkFlow's scale or usage pattern.
**Alternative considered:** Cursor-based (keyset) pagination — rejected as unneeded complexity here; revisit only if a specific list endpoint's row count genuinely becomes a performance problem.

---

## Open Items Carried Forward

- **PR/issue template content** — Deliverable 7 (still pending, not forgotten — running after this batch).

---

*Next: Deliverable 10 — Development Environment.*
