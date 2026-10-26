#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -d "${REPO_DIR}/backend/.venv" ]; then
  echo "Error: Virtual environment not found at ${REPO_DIR}/backend/.venv. Run scripts/setup_env.sh first." >&2
  exit 1
fi

# Configure PYTHONPATH so app.main resolves cleanly whether backend code lives at
# repo root or in backend/ subdirectory
export PYTHONPATH="${REPO_DIR}/backend:${REPO_DIR}:${PYTHONPATH:-}"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

echo "==> Starting backend server on http://${HOST}:${PORT}"
exec "${REPO_DIR}/backend/.venv/bin/uvicorn" app.main:app --reload --host "$HOST" --port "$PORT"
