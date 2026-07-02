#!/usr/bin/env bash
set -e

cp .env.example .env                    # then fill in real values manually
uv sync --directory apps/api            # install Python deps
pre-commit install                      # install git hooks (Development Environment §8)
cd apps/web && npm install && cd ../..  # install frontend deps
supabase link --project-ref <dev-project-ref>
supabase db push                        # apply migrations to the dev project
docker compose up -d redis api worker
cd apps/web && npm run dev              # separate terminal, not backgrounded
