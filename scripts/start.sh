#!/usr/bin/env bash
# Start ICECODE server (Python FastAPI on port 13210)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Activate venv if exists
if [ -d "$ROOT_DIR/.venv" ]; then
  source "$ROOT_DIR/.venv/bin/activate"
fi

# Load .env
if [ -f "$ROOT_DIR/.env" ]; then
  export $(grep -v '^#' "$ROOT_DIR/.env" | xargs -d '\n' 2>/dev/null) || \
  while IFS= read -r line; do
    [[ "$line" =~ ^#.*$ ]] || [[ -z "$line" ]] || export "$line"
  done < "$ROOT_DIR/.env"
fi

cd "$ROOT_DIR"

export PYTHONPATH="$ROOT_DIR/packages/core:$ROOT_DIR/packages/server:$ROOT_DIR/packages/tools:$PYTHONPATH"

echo "Starting ICECODE server on port ${HOST_API_PORT:-13210}..."
python3 -m uvicorn icecode_server.main:app \
  --host 0.0.0.0 \
  --port "${HOST_API_PORT:-13210}" \
  --reload \
  --app-dir "$ROOT_DIR/packages/server"
