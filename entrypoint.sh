#!/bin/sh
set -eu

if [ "${INIT_DB:-false}" = "true" ]; then
  echo ">>> INIT_DB=true, initializing database..."
  python scripts/init_db.py
fi

GUNICORN_WORKERS="${GUNICORN_WORKERS:-1}"
echo ">>> Starting gunicorn with workers=${GUNICORN_WORKERS}..."

exec gunicorn app.main:app \
  -w "${GUNICORN_WORKERS}" \
  -k uvicorn.workers.UvicornWorker \
  -b "0.0.0.0:${PORT:-8000}" \
  --access-logfile - \
  --error-logfile -

