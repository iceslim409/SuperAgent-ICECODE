#!/usr/bin/env bash
# Start ICECODE TUI (33 themes, dialog system)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Starting ICECODE TUI..."
cd "$ROOT_DIR/packages/cli"
pnpm tui
