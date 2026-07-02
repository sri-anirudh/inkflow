# InkFlow — Engineering Handbook

**Author:** Technical Architect
**Version:** 1.0
**Date:** 2026-06-30
**Status:** Draft — Awaiting Review
**Builds on:** Product Vision v1.3, Deliverable 2 (Architecture Diagrams, Batches 1–5)

---

## 1. Introduction & Purpose

This handbook is the front door to InkFlow's engineering practice. It doesn't contain the detailed rules themselves — those live in their own numbered deliverables, cross-referenced throughout this document — but it explains the *principles* those rules serve, so a new engineer (human or AI role) understands the "why" before they hit the "how."

**Who this is for:** every engineering role on the project — Backend, Frontend, Database, DevOps, Security, QA, Documentation — and every AI instance operating in one of those roles. If you're about to write code, review a PR, or make a design decision on InkFlow, this is the document to have read first.

**How to use it:** skim the section relevant to what you're doing right now. It's a reference, not a novel — you're not expected to read it linearly before every task.

---

## 2. Project Overview & Learning Philosophy

InkFlow is an educational project to build an enterprise-grade e-signature platform, inspired by DocuSign, at a scale realistic for a production SaaS serving ~1,000 users.

**The dual goal, stated precisely:** build a production-quality MVP as efficiently as possible, and learn by doing so — not by deliberately avoiding tools that would make the job faster. This is a real shift from how many "learning projects" are approached, and it has one concrete rule attached to it:

> **Use managed services and existing solutions wherever they save meaningful time on a solved problem.** Don't hand-build something just to learn its internals. The exception: anything so central to InkFlow's actual product that understanding it *is* the product — the signing flow, the audit trail, and PDF processing. Those stay custom-built, deliberately.

This rule already shaped real decisions you'll see referenced throughout this handbook: Supabase (Auth + Postgres + Storage) was adopted specifically *because* auth and file storage are solved problems (Deliverable 2, ADR-004); the signing token design, sequential-signing orchestration, and PDF assembly pipeline were built by hand *because* they're InkFlow-specific (ADR-013 through ADR-016).

**What's already locked in** (do not relitigate without a real reason):
- Product Vision v1.3 — features, business rules, and workflow are Product-owned and settled.
- Deliverable 2 — system architecture, data model, auth flow, and token design are approved (16 ADRs recorded).

---

## 3. Tech Stack Summary

This is a quick-reference table. The reasoning for each choice lives in Deliverable 2's ADRs — this handbook doesn't repeat it, only points to it.

| Layer | Choice | Reasoning |
|---|---|---|
| Backend | FastAPI (Python) | ADR-001 (modular monolith) |
| Frontend | Next.js (TypeScript) | Deliverable 2, Batch 1 |
| Database | Supabase (managed Postgres + RLS) | ADR-004, ADR-006 |
| Auth | Supabase Auth | ADR-004 |
| Object storage | Supabase Storage | ADR-004 |
| Cache / queue | Azure Cache for Redis | ADR-005 |
| Background jobs | RQ (Redis Queue) | ADR-002 |
| Compute | Azure Container Apps | ADR-005 |
| Frontend hosting | Vercel | Deliverable 2, Batch 1 |
| Transactional email | SendGrid | Deliverable 2, Batch 2 |
| PDF processing | pypdf + reportlab | ADR-014 |

**One thing worth stating plainly:** the original project instructions list AWS as the default cloud provider. That default was formally superseded during Deliverable 2 — Azure for compute (ADR-005) and Supabase for data/auth/storage (ADR-004) are the *approved* stack going forward. Flagging this explicitly so nobody building against an older mental model of the instructions gets confused later.

---

## 4. Modular Monolith Principles

InkFlow is one deployable (the FastAPI API), internally split into modules by business capability (ADR-001, ADR-003):

**Identity & Tenant · Envelope · Signing · Document Generation · Audit · Notification · Storage**

Two rules make this a *modular* monolith rather than a ball of mud:

1. **Modules talk to each other through service-layer function calls, never by importing another module's database models or repository directly.** If the Signing module needs envelope data, it calls `envelope_service.get_envelope(...)`, not `from envelope.models import Envelope`.
2. **Trust boundaries define module splits, not just convenience.** Envelope and Signing are separate modules specifically because one is session-authenticated and one is token-authenticated (ADR-003) — the boundary reflects a real security distinction, not an arbitrary one.

The concrete module map, responsibilities, and inter-module call graph are in Deliverable 2, Batch 1 (Component Diagram). This handbook just states the rule; that diagram is the source of truth for the map itself.

---

## 5. Coding Philosophy & Design Principles

These are values, not syntax — language-specific conventions (naming, formatting, linting) are Deliverable 5's job. This is what should guide a judgment call when the style guide doesn't cover it.

- **Simple and correct beats fast and clever.** We've already made this call explicitly once (ADR-008: a per-request DB lookup over a faster-but-stale custom JWT claim) — that's the standard to hold every similar trade-off to.
- **Explicit over implicit.** State assumptions in code comments and PR descriptions the same way we state them in ADRs. A silently-made assumption is a bug waiting to be discovered by someone else.
- **Validate at every trust boundary, never trust the caller.** This isn't optional at the API edge — Batch 3's server-side PDF validation (never trusting client-declared file type/size) is the pattern to follow anywhere external input enters a module.
- **Single responsibility, both at the module level and the function level.** If a function needs "and" in its description, it's probably two functions.
- **No premature optimization.** At ~1,000 users, correctness and readability win by default. Optimize only once a real bottleneck is measured, not anticipated.
- **Prefer composition over inheritance**, and prefer plain data structures over clever abstractions until a second real use case justifies the abstraction.

---

## 6. Observability & Error Handling Philosophy

Full tooling (log aggregation, monitoring stack, alerting) is Deliverable 11's job. The principles that should shape how code is *written* from day one, so that tooling has something useful to work with later:

- **Fail loud, not silent.** Never swallow an exception without logging it or re-raising something meaningful. A silently-caught error is a bug that will resurface as a much harder-to-diagnose problem later — usually in production.
- **Distinguish expected failures from unexpected ones.** A business-rule violation (e.g., a decline attempt against a voided envelope) is an expected 4xx with a clear, specific message — not a stack trace. An unexpected failure (a DB connection drop) is a 500, logged with full context, and it's fine for it to be loud.
- **Structured logging from the start, not bolted on later.** Log as JSON with consistent fields (timestamp, module, request_id, user_id/recipient context where relevant) even before any log aggregation tool is wired up in Deliverable 11 — retrofitting structure onto free-text logs later is far more painful than starting structured.
- **Every request should be traceable end-to-end.** A `request_id` generated at the API edge and threaded through logs, the audit trail, and any background job it enqueues means a support question ("why did this envelope's PDF generation fail?") can be answered by following one ID, not guessing at timestamps.
- **Instrument as you build.** Adding a log line or metric while writing the code it describes is nearly free. Adding it after the fact requires someone to first realize it's missing, usually while debugging something urgent.

---

## 7. Folder Ownership (Conceptual)

The actual directory tree is Deliverable 4's job. At a principle level: each backend module (Section 4's list) owns one folder, containing its own routes, service logic, and data-access code — no module's folder should be a dependency of another module's *internals*, only of its public service interface. Shared, cross-cutting code (e.g., the JWT verification middleware, the Supabase client wrapper) lives in a common/shared location, not duplicated per module.

---

## 8. Git Workflow Overview

Full branch naming, merge strategy, and release tagging are Deliverable 9's job. The principles that hold regardless of the exact model chosen:

- No direct commits to `main` (or whatever the protected branch ends up being called) — everything goes through a pull request.
- Commits should be small and focused — one logical change per commit, not a day's work squashed into one.
- A PR should be reviewable in one sitting. If it's not, it's probably doing too much at once.

---

## 9. Code Review Checklist

A practical checklist for this handbook specifically — *what* gets checked in detail (linting rules, formatting) is Deliverable 5's job; this is *how* a reviewer should think about a PR.

- [ ] Does this respect module boundaries (Section 4) — no direct cross-module model imports?
- [ ] Does this match an existing ADR? If it contradicts one, was that intentional and flagged, or accidental?
- [ ] Is external input (client data, uploaded files, query params) validated server-side, not just trusted?
- [ ] If this changes behavior tied to a specific Business Rule (BR-XX), is that rule referenced in the PR description or a code comment?
- [ ] Are errors handled per Section 6 (loud, structured, expected vs. unexpected distinguished)?
- [ ] Is there a test covering the new/changed behavior, especially for anything touching a concurrency-sensitive path (token consumption, sequential signing) or a known-fiddly one (coordinate conversion)?
- [ ] Does this need a new ADR? (Significant architecture/security/data-model decisions do — see Section 10.)
- [ ] No secrets, credentials, or API keys committed, including in test fixtures or example configs.
- [ ] Does documentation (README, docstrings, API docs) reflect the change, not just the code?

---

## 10. Documentation Expectations

Documentation is the shared source of truth across every AI role and every human contributor — there is no other shared memory across chats/sessions, so what isn't written down doesn't persist.

- **Documentation before implementation, architecture before code** — this isn't just a slogan, it's why Deliverable 2 exists before any backend code has been written.
- **Every significant decision gets an ADR.** "Significant" means: architecture, security, data model, or anything that would be expensive to reverse later. We've already produced sixteen of these across Deliverable 2 — that's the standard of rigor to keep, not an early-project anomaly to taper off from.
- **State assumptions explicitly, and flag them for review rather than silently deciding.** This has come up repeatedly already (e.g., the decline-resolution edit-in-place assumption that became BR-15c/BR-25a) — assumptions that touch product behavior get flagged to the PM; assumptions that are purely technical get documented and proceeded with.
- **A deliverable isn't done until it's handoff-ready** — readable by the next role without needing a live conversation to fill gaps.

---

## 11. Security-First Mindset

Detailed secrets management and infrastructure security are Deliverable 10/11's job. The standing principles:

- **Never trust client input.** Server-side validation is mandatory at every boundary — this is already precedent (PDF magic-byte/size validation in Deliverable 2, Batch 3), not a new rule.
- **Defense in depth, not a single point of failure.** RLS policies exist *in addition to* application-layer authorization checks (ADR-006) specifically so one layer's bug doesn't become a tenant-isolation breach — R-07 is flagged Critical-impact in the product doc for a reason.
- **Least privilege by default.** The API's service-role Supabase connection bypasses RLS for orchestration convenience, but that's a deliberate, narrow exception — not a reason to skip RLS everywhere else.
- **Hash, never store, anything secret-equivalent.** Passwords are Supabase's problem now, but the same principle governs our own token design (ADR-013: tokens stored as SHA-256 hashes, raw values never persisted).
- **Unauthenticated surfaces get extra scrutiny.** The Signing module is deliberately isolated (ADR-003) and rate-limited (ADR-013) precisely because it's the one part of the system reachable without any credential at all.

---

## 12. Testing Philosophy

Full tooling, coverage targets, and test types are Deliverable 12's job. The reasoning that should inform it:

- **Test pyramid, not test inversion.** Most coverage should come from fast, isolated unit tests; fewer integration tests; fewer still end-to-end tests. If the balance is inverted (mostly slow E2E tests), the suite becomes a bottleneck rather than a safety net.
- **"Done" means tested and documented, not just "works on my machine."** A feature without a test is an assumption, not a guarantee.
- **Concurrency-sensitive and fiddly logic get dedicated, isolated tests before integration.** Two examples already flagged during Deliverable 2 and worth remembering here: the atomic token-consumption guard behind sequential signing (ADR-013's `WHERE used_at IS NULL` pattern), and the coordinate-conversion math in PDF generation (Batch 4, Section 4) — both are exactly the kind of logic that looks obviously correct and is subtly not.
- **Test the business rule, not just the code path.** A test for decline handling should assert against BR-15a's actual behavior (envelope-wide pause, not just downstream-sequential), not just that the function returns 200.

---

## 13. AI Collaboration Guidelines

Multiple AI roles work on this project across separate chats with no shared runtime memory — documentation is genuinely the *only* thing that persists between them. That makes a few things non-negotiable:

- **Respect role boundaries.** A Technical Architect role doesn't redefine a business rule; a Backend Engineer role doesn't silently override an ADR. If a role's output implies a decision outside its charter, it gets flagged to the owning role, not decided unilaterally.
- **Every deliverable is a handoff artifact.** It should be readable and actionable by the next role with zero additional context beyond what's already documented — this handbook, every Deliverable 2 batch, and the Product Vision were all written with that standard.
- **Escalate only when it matters.** Per the project instructions: only pause for clarification when the answer would materially affect product scope, architecture, security, the data model, user workflows, or long-term maintainability. Everything else — pick the industry-standard approach, state the assumption, keep moving.
- **Flag assumptions instead of burying them.** State them in the deliverable itself (as this project has done consistently — the resend-to-different-signer assumption, the RLS/service-role trade-off, etc.), not just in conversation, so a future role picking up the document later sees the same reasoning you did.
- **When in doubt about scope, under-claim rather than over-claim.** It's cheaper to ask "is this mine to decide?" once than to have another role's decision silently overwritten.

---

## 14. Appendix

### 14.1 Glossary

| Term | Meaning |
|---|---|
| **Envelope** | The core unit of work — one document + its recipients + fields + lifecycle status |
| **Recipient** | Anyone assigned to an envelope as a Signer or CC; may or may not have a platform account |
| **Signer** | A Recipient who must sign for the envelope to complete |
| **CC** | A Recipient who receives the completed document but takes no action |
| **Company** | The tenant — one isolated account, one or more Profiles |
| **Profile** | A registered platform user's record, linked 1:1 to a Supabase `auth.users` row |
| **Signing token** | Single-use-until-consumed, 7-day-expiring opaque token granting a Recipient access to sign |
| **Download token** | Non-expiring, reusable opaque token granting a Recipient access to their completed document |
| **RLS** | Row-Level Security — Postgres-enforced tenant isolation, our defense-in-depth layer (ADR-006) |
| **ADR** | Architecture Decision Record — the format we use to capture and justify significant decisions |

### 14.2 "If You Need X, See Deliverable Y"

| Looking for... | Go to |
|---|---|
| System diagrams, data model, request flows, ADRs 001–016 | Deliverable 2 |
| Actual folder/directory tree | Deliverable 4 |
| Language-specific style rules, naming conventions | Deliverable 5 |
| README/ADR/Sprint-note templates | Deliverable 6 |
| REST API conventions (endpoints, status codes, pagination) | Deliverable 7 |
| Kanban setup, DoR/DoD, sprint cadence | Deliverable 8 |
| Branch names, merge strategy, release tagging | Deliverable 9 |
| Docker, local env setup, linting/formatting tools | Deliverable 10 |
| CI/CD pipeline, deployment environments, monitoring | Deliverable 11 |
| Test types, coverage targets, tooling | Deliverable 12 |

---

*This handbook should be revisited if any of its stated principles are contradicted by a later deliverable — that's a signal to reconcile, not to silently let one document win.*

*Next, pending your approval: Deliverable 4 — Repository Structure.*
