#!/usr/bin/env bash
# Start ICECODE Desktop app (Electron + React)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Starting ICECODE Desktop..."
cd "$ROOT_DIR/packages/desktop-app"
pnpm dev
