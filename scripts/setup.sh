#!/usr/bin/env bash
# ICECODE Setup Script
set -e

echo "======================================================"
echo "  ICECODE Super-Agent Network — Setup"
echo "======================================================"

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "ERROR: Python 3.11+ required"
  exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "[✓] Python $PYTHON_VERSION"

# Check Node.js
if ! command -v node &>/dev/null; then
  echo "ERROR: Node.js 20+ required"
  exit 1
fi
echo "[✓] Node $(node --version)"

# Check pnpm
if ! command -v pnpm &>/dev/null; then
  echo "Installing pnpm..."
  npm install -g pnpm@9
fi
echo "[✓] pnpm $(pnpm --version)"

# Check uv (Python package manager)
if ! command -v uv &>/dev/null; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  source "$HOME/.cargo/env" 2>/dev/null || true
fi
echo "[✓] uv $(uv --version 2>/dev/null | head -1)"

# Create .env from example
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

if [ ! -f "$ROOT_DIR/.env" ]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  echo "[✓] Created .env from .env.example"
  echo "    >>> Edit $ROOT_DIR/.env and add your API keys <<<"
fi

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
cd "$ROOT_DIR"
uv venv --python 3.11 2>/dev/null || uv venv
uv pip install -e "packages/core[dev]" --quiet
echo "[✓] Python packages installed"

# Install Node.js dependencies
echo ""
echo "Installing Node.js dependencies..."
pnpm install --frozen-lockfile 2>/dev/null || pnpm install
echo "[✓] Node packages installed"

echo ""
echo "======================================================"
echo "  Setup complete!"
echo ""
echo "  Start the server:   ./scripts/start.sh"
echo "  Start desktop app:  ./scripts/start-desktop.sh"
echo "  Start TUI:          ./scripts/start-tui.sh"
echo "======================================================"
