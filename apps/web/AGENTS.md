# AGENTS.md — apps/web

**Status:** Placeholder. Full template/content is Deliverable 7 (Documentation Templates) — not yet written.

## What this codebase is

The InkFlow frontend: a Next.js (App Router, TypeScript) app talking to `apps/api`.

## The one rule that must not be broken

**Don't reach past the API client.** Data access goes through `src/lib/` (Supabase client, API client wrapper) — components don't call `fetch`/Supabase directly. This mirrors the backend's module-boundary rule: one seam to change if the API contract or auth mechanism changes, not N call sites.

## Where the real documentation lives

- Root `/AGENTS.md` and `/docs/handbook/` — full engineering practice.
- `docs/handbook/deliverable-04-repository-structure.md` §3 — folder shape (`app/`, `components/`, `lib/`, `hooks/`, `styles/`).
- `docs/handbook/deliverable-05-coding-standards.md` §2 — TypeScript conventions (strict mode, naming, ESLint/Prettier).
