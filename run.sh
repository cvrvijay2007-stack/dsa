#!/usr/bin/env bash
# Create a venv (first run only), install deps, and start the server.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements-dev.txt
fi
cd backend
exec ../.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port "${PORT:-8000}"
