# Contributing to InkFlow

## Branching

- `main` — production, always deployable. `develop` — staging integration branch.
- `feature/<module>-<short-description>` branched off `develop`, e.g. `feature/infra-repo-scaffold`.
- `hotfix/<short-description>` branched off `main` for urgent production fixes, back-merged to `develop`.
- No direct pushes to `main` or `develop` — everything goes through a PR.

Full model: `docs/handbook/deliverable-06-branching-strategy.md`.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/): `<type>(<scope>): <description>`, e.g. `feat(signing): add decline endpoint`. Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`.

## Pull requests

- CI (lint, type-check, tests) must pass before merge.
- Self/AI review against the Engineering Handbook §9 checklist before requesting merge — module boundaries respected, ADR alignment, input validated, errors handled, tests present.
- PRs touching shared module boundaries, auth/token/RLS code, or introducing a new dependency get an Architecture Reviewer pass.

Full process: `docs/handbook/deliverable-06-branching-strategy.md` §3.

## Code style

Ruff + mypy (Python), ESLint + Prettier (TypeScript) — enforced via pre-commit and CI. Run `pre-commit install` once (`scripts/setup.sh` does this for you). Full standards: `docs/handbook/deliverable-05-coding-standards.md`.
