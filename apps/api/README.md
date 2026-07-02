# apps/api — InkFlow Backend

FastAPI modular monolith. Full local-environment rationale: `/docs/handbook/deliverable-10-development-environment.md`.

## Run locally

Requires a `.env` in the repo root (copy `.env.example`) pointing at a Supabase dev project (Card 2) — `SUPABASE_DB_URL` must be the session pooler string, see root README.

**Via Docker Compose (matches how Staging/Production actually run):**

```bash
docker compose up -d redis api worker
curl localhost:8000/health   # {"status":"ok","environment":"development","db":"ok"}
```

**Bare, without Docker:**

```bash
uv sync
uv run uvicorn src.main:app --reload
```

## Tests

```bash
uv run pytest
```

## Lint / type-check

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
```
