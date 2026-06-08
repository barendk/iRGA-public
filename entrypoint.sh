#!/bin/bash
# Docker entrypoint: wait for Postgres, run migrations, optionally seed, start app.

set -e

echo "Waiting for Postgres..."
# Extract host and port from DATABASE_URL (postgresql://user:pass@host:port/db)
DB_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:]*\):\([0-9]*\)/.*|\1|p')
DB_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:]*\):\([0-9]*\)/.*|\2|p')

until pg_isready -h "$DB_HOST" -p "$DB_PORT" -q; do
  echo "  Postgres not ready, retrying in 1s..."
  sleep 1
done
echo "Postgres is ready."

# Run Alembic migrations
echo "Running database migrations..."
alembic upgrade head

# Optionally seed demo data (set SEED_DATA=1 in docker-compose or env).
# The script is idempotent: it skips if data already exists.
if [ "${SEED_DATA}" = "1" ]; then
  python scripts/seed_dev.py
fi

echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
