#!/usr/bin/env bash
# ICECODE Super-Agent Network — Start All Services
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV="$SCRIPT_DIR/.venv"
PID_DIR="$HOME/.icecode"
SERVER_PID_FILE="$PID_DIR/server.pid"
LOG_DIR="$PID_DIR/logs"
SERVER_LOG="$LOG_DIR/server.log"
PORT=13210
WEB_UI="$SCRIPT_DIR/packages/web-ui/index.html"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
fail() { echo -e "${RED}[✗]${NC} $*"; }

echo ""
echo "  ██╗ ██████╗███████╗ ██████╗ ██████╗ ██████╗ ███████╗"
echo "  ██║██╔════╝██╔════╝██╔════╝██╔═══██╗██╔══██╗██╔════╝"
echo "  ██║██║     █████╗  ██║     ██║   ██║██║  ██║█████╗  "
echo "  ██║██║     ██╔══╝  ██║     ██║   ██║██║  ██║██╔══╝  "
echo "  ██║╚██████╗███████╗╚██████╗╚██████╔╝██████╔╝███████╗"
echo "  ╚═╝ ╚═════╝╚══════╝ ╚═════╝ ╚═════╝ ╚═════╝╚══════╝"
echo "         Super-Agent Network v2.0.0 — Starting..."
echo ""

# ── Dirs ────────────────────────────────────────────────────────
mkdir -p "$PID_DIR/data" "$PID_DIR/logs"

# ── Already running? ────────────────────────────────────────────
if [ -f "$SERVER_PID_FILE" ]; then
    OLD_PID=$(cat "$SERVER_PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        warn "Server already running (PID $OLD_PID). Run ./stop.sh first."
        exit 0
    else
        rm -f "$SERVER_PID_FILE"
    fi
fi

# ── Python venv ──────────────────────────────────────────────────
if [ ! -f "$VENV/bin/python" ]; then
    warn "Virtual environment not found at $VENV"
    warn "Run ./scripts/setup.sh first (or: uv venv .venv --python 3.12)"
    exit 1
fi

PYTHON="$VENV/bin/python"
export PYTHONPATH="$SCRIPT_DIR/packages/core:$SCRIPT_DIR/packages/server:$SCRIPT_DIR/packages/tools"

# ── Load .env ────────────────────────────────────────────────────
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$SCRIPT_DIR/.env"
    set +a
    log ".env loaded"
else
    warn "No .env found — using defaults (copy .env.example to .env to configure)"
fi

# ── Ollama check ─────────────────────────────────────────────────
echo ""
echo "  Checking local AI servers..."
if curl -s --max-time 2 "http://localhost:11434/api/tags" > /dev/null 2>&1; then
    MODELS=$(curl -s "http://localhost:11434/api/tags" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | tr '\n' ', ' | sed 's/,$//')
    log "Ollama running — models: ${MODELS:-none pulled}"
else
    warn "Ollama not running on port 11434"
    warn "  To start: ollama serve  (then: ollama pull qwen2.5:7b)"
fi

# ── Start FastAPI server ─────────────────────────────────────────
echo ""
echo "  Starting ICECODE server on port $PORT..."

nohup "$PYTHON" -m uvicorn icecode_server.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --app-dir "$SCRIPT_DIR/packages/server" \
    --log-level info \
    > "$SERVER_LOG" 2>&1 &

SERVER_PID=$!
echo "$SERVER_PID" > "$SERVER_PID_FILE"
log "Server started (PID $SERVER_PID) — log: $SERVER_LOG"

# ── Wait for health ───────────────────────────────────────────────
echo ""
echo "  Waiting for server to be ready..."
MAX_WAIT=30
for i in $(seq 1 $MAX_WAIT); do
    if curl -s --max-time 1 "http://localhost:$PORT/health" > /dev/null 2>&1; then
        log "Server is healthy (took ${i}s)"
        break
    fi
    if [ "$i" -eq "$MAX_WAIT" ]; then
        fail "Server did not become healthy in ${MAX_WAIT}s"
        fail "Check log: tail -f $SERVER_LOG"
        exit 1
    fi
    sleep 1
    printf "."
done
echo ""

# ── Open terminal with live logs ──────────────────────────────────
echo ""
echo "  Opening log terminal..."
if command -v gnome-terminal &> /dev/null; then
    gnome-terminal \
        --title="ICECODE Server Logs" \
        -- bash -c "
            echo '';
            echo '  ICECODE Super-Agent Network — Live Logs';
            echo '  Server: http://localhost:$PORT';
            echo '  API:    http://localhost:$PORT/docs';
            echo '  PID:    $SERVER_PID';
            echo '';
            tail -f '$SERVER_LOG';
            read -rp 'Press Enter to close...'
        " &
    log "Log terminal opened"
elif command -v xterm &> /dev/null; then
    xterm -title "ICECODE Logs" -e "tail -f '$SERVER_LOG'" &
    log "Log terminal (xterm) opened"
elif command -v konsole &> /dev/null; then
    konsole --title "ICECODE Logs" -e "tail -f '$SERVER_LOG'" &
    log "Log terminal (konsole) opened"
else
    warn "No terminal emulator found — logs at: $SERVER_LOG"
fi

# ── Open web UI ───────────────────────────────────────────────────
echo ""
echo "  Opening web interface..."
sleep 1

BROWSER_URL="http://localhost:$PORT"
FILE_URL="file://$WEB_UI"

if command -v firefox &> /dev/null; then
    # Try to open the live server URL first; fallback to file
    if curl -s --max-time 1 "http://localhost:$PORT" > /dev/null 2>&1; then
        firefox "$BROWSER_URL" &
    else
        firefox "$FILE_URL" &
    fi
    log "Firefox opened at $BROWSER_URL"
elif command -v xdg-open &> /dev/null; then
    xdg-open "$BROWSER_URL" &
    log "Browser opened via xdg-open"
elif command -v google-chrome &> /dev/null; then
    google-chrome "$BROWSER_URL" &
    log "Chrome opened"
elif command -v chromium-browser &> /dev/null; then
    chromium-browser "$BROWSER_URL" &
    log "Chromium opened"
else
    warn "No browser found — open manually: $BROWSER_URL"
fi

# ── Start desktop app (optional) ─────────────────────────────────
DESKTOP_APP="$SCRIPT_DIR/packages/desktop-app"
ELECTRON_BIN="$DESKTOP_APP/node_modules/electron/dist/electron"
if [ -f "$ELECTRON_BIN" ]; then
    echo ""
    read -r -t 5 -p "  Start desktop app too? [y/N] (auto-skip in 5s): " LAUNCH_DESKTOP || true
    echo ""
    if [[ "${LAUNCH_DESKTOP:-N}" =~ ^[Yy]$ ]]; then
        cd "$DESKTOP_APP"
        # ELECTRON_RUN_AS_NODE must be unset so Electron starts with GUI (not Node.js mode)
        DISPLAY="${DISPLAY:-:1}" ELECTRON_RUN_AS_NODE='' "$ELECTRON_BIN" . --no-sandbox \
            > "$LOG_DIR/desktop.log" 2>&1 &
        echo "$!" > "$PID_DIR/desktop.pid"
        log "Desktop app launched (PID $!) — log: $LOG_DIR/desktop.log"
        cd "$SCRIPT_DIR"
    fi
fi

# ── Summary ───────────────────────────────────────────────────────
echo ""
echo "  ════════════════════════════════════════════════════"
echo "   ICECODE is running!"
echo ""
echo "   Web UI:     http://localhost:$PORT"
echo "   API docs:   http://localhost:$PORT/docs"
echo "   Health:     http://localhost:$PORT/health"
echo "   Server log: $SERVER_LOG"
echo "   Stop:       ./stop.sh"
echo "  ════════════════════════════════════════════════════"
echo ""
