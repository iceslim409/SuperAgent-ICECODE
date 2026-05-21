#!/bin/bash
# ICECODE Super-Agent Network — One-click installer
# Usage: bash install.sh

set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
RESET="\033[0m"

ok()   { echo -e "${GREEN}✓${RESET} $1"; }
info() { echo -e "${YELLOW}→${RESET} $1"; }
fail() { echo -e "${RED}✗${RESET} $1"; exit 1; }

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║       ICECODE Super-Agent Network — Installer        ║"
echo "║                    v1.0.0                            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${RESET}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── 1. Check Python ───────────────────────────────────────────────────────────
info "Checking Python version..."
if command -v python3 &>/dev/null; then
    PY=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    MAJOR=$(echo $PY | cut -d. -f1)
    MINOR=$(echo $PY | cut -d. -f2)
    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
        ok "Python $PY found"
    else
        fail "Python 3.10+ required. Found $PY"
    fi
else
    fail "Python 3 not found. Install from https://python.org"
fi

# ── 2. Create virtual environment ────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    info "Creating virtual environment..."
    python3 -m venv .venv
    ok "Virtual environment created at .venv/"
else
    ok "Virtual environment already exists"
fi

source .venv/bin/activate

# ── 3. Install Python dependencies ───────────────────────────────────────────
info "Installing Python dependencies..."
pip install --quiet --upgrade pip

# Core agent dependencies
pip install --quiet \
    openai>=1.30.0 \
    fastapi>=0.110.0 \
    uvicorn[standard]>=0.29.0 \
    httpx>=0.27.0 \
    loguru>=0.7.2 \
    pydantic>=2.0.0 \
    python-multipart>=0.0.9 \
    websockets>=12.0

ok "Core dependencies installed"

# RAG/Knowledge base dependencies
info "Installing RAG dependencies (sentence-transformers + faiss)..."
pip install --quiet \
    sentence-transformers>=2.7.0 \
    faiss-cpu>=1.8.0 \
    numpy>=1.24.0 \
    PyPDF2>=3.0.0 2>/dev/null || \
pip install --quiet \
    sentence-transformers \
    faiss-cpu \
    numpy \
    PyPDF2 && ok "RAG dependencies installed" || info "RAG deps partially installed (knowledge base may be limited)"

# Optional: pytest for tests
pip install --quiet pytest pytest-asyncio 2>/dev/null && ok "Test dependencies installed"

# Install ICECODE packages in development mode
info "Installing ICECODE packages..."
pip install --quiet -e packages/core 2>/dev/null && ok "packages/core installed" || \
  info "Note: packages/core pyproject.toml not found, using PYTHONPATH"

pip install --quiet -e packages/server 2>/dev/null || true

pip install --quiet --no-deps -e packages/cli 2>/dev/null && ok "packages/cli (icecode_cli) installed" || true

# ── 4. Create .env if missing ─────────────────────────────────────────────────
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    ok ".env created from .env.example"
    info "Edit .env to add API keys (optional — Ollama works without any key)"
elif [ ! -f ".env" ]; then
    cat > .env << 'EOF'
# ICECODE Configuration
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
HOST_API_PORT=13210
# Add cloud API keys below (all optional):
# ANTHROPIC_API_KEY=
# OPENAI_API_KEY=
# GOOGLE_API_KEY=
# DEEPSEEK_API_KEY=
EOF
    ok ".env created with defaults"
fi

# ── 5. Create required directories ───────────────────────────────────────────
mkdir -p ~/.icecode/data ~/.icecode/sessions ~/.icecode/skills ~/.icecode/logs
mkdir -p ~/.icecode/data/knowledge ~/.icecode/data/knowledge/uploads
ok "Directories created at ~/.icecode/"

# ── 6. Check Ollama ──────────────────────────────────────────────────────────
info "Checking Ollama..."
if command -v ollama &>/dev/null; then
    ok "Ollama found: $(ollama --version 2>/dev/null || echo 'installed')"
    if curl -s http://localhost:11434/api/tags &>/dev/null; then
        MODELS=$(curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; d=json.load(sys.stdin); print(', '.join(m['name'] for m in d.get('models',[])))" 2>/dev/null)
        if [ -n "$MODELS" ]; then
            ok "Ollama running with models: $MODELS"
        else
            info "Ollama running but no models installed. Run: ollama pull qwen2.5:7b"
        fi
    else
        info "Ollama not running. Start with: ollama serve"
    fi
else
    info "Ollama not installed. Install from https://ollama.com for local AI"
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}Installation complete!${RESET}"
echo ""
echo "  Start server:    make run   (or: bash start.sh)"
echo "  Run tests:       make test"
echo "  Open browser:    http://localhost:13210"
echo ""
echo "  Full docs:       cat README.md"
echo ""
