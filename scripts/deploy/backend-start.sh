#!/usr/bin/env sh
set -eu

cd /app

python -m app.core.startup_preflight
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
