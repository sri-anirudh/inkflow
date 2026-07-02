# apps/api — InkFlow Backend

FastAPI modular monolith. Full local-environment rationale: `/docs/handbook/deliverable-10-development-environment.md`.

## Run locally

```bash
uv sync
uv run uvicorn src.main:app --reload
```

Requires a `.env` in the repo root (copy `.env.example`) pointing at a Supabase dev project — see Card 2 (Sprint 1) for provisioning that project; there isn't one yet as of this scaffold.

## Tests

```bash
uv run pytest
```

## Lint / type-check

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```
