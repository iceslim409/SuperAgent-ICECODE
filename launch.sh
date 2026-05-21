#!/usr/bin/env bash
# ICECODE — One-click launcher: server + desktop app
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
DESKTOP="$SCRIPT_DIR/packages/desktop-app"
ELECTRON="$DESKTOP/node_modules/.bin/electron"
PID_DIR="$HOME/.icecode"
SERVER_PID_FILE="$PID_DIR/server.pid"
LOG_DIR="$PID_DIR/logs"
PORT=13210

mkdir -p "$PID_DIR/data" "$LOG_DIR"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }

echo ""
echo "  ██╗ ██████╗███████╗ ██████╗ ██████╗ ██████╗ ███████╗"
echo "  ██║██╔════╝██╔════╝██╔════╝██╔═══██╗██╔══██╗██╔════╝"
echo "  ██║██║     █████╗  ██║     ██║   ██║██║  ██║█████╗  "
echo "  ██║██║     ██╔══╝  ██║     ██║   ██║██║  ██║██╔══╝  "
echo "  ██║╚██████╗███████╗╚██████╗╚██████╔╝██████╔╝███████╗"
echo "  ╚═╝ ╚═════╝╚══════╝ ╚═════╝ ╚═════╝ ╚═════╝╚══════╝"
echo "         Super-Agent Network v1.0.0"
echo ""

# ── Server ───────────────────────────────────────────────────────────────────
SERVER_RUNNING=false
if [ -f "$SERVER_PID_FILE" ] && kill -0 "$(cat "$SERVER_PID_FILE")" 2>/dev/null; then
    log "Server already running (PID $(cat "$SERVER_PID_FILE"))"
    SERVER_RUNNING=true
elif curl -s --max-time 1 "http://localhost:$PORT/health" > /dev/null 2>&1; then
    log "Server already running on port $PORT"
    SERVER_RUNNING=true
fi

if [ "$SERVER_RUNNING" = false ]; then
    if [ ! -f "$VENV/bin/python" ]; then
        warn "Python venv not found at $VENV — run: uv venv .venv --python 3.12 && uv pip install -e packages/core -e packages/server"
        exit 1
    fi

    export PYTHONPATH="$SCRIPT_DIR/packages/core:$SCRIPT_DIR/packages/server:$SCRIPT_DIR/packages/tools"
    [ -f "$SCRIPT_DIR/.env" ] && { set -a; source "$SCRIPT_DIR/.env"; set +a; }

    echo "  Starting ICECODE server..."
    nohup "$VENV/bin/python" -m uvicorn icecode_server.main:app \
        --host 0.0.0.0 --port "$PORT" \
        --app-dir "$SCRIPT_DIR/packages/server" \
        --log-level warning \
        > "$LOG_DIR/server.log" 2>&1 &
    echo "$!" > "$SERVER_PID_FILE"
    log "Server started (PID $!) — log: $LOG_DIR/server.log"

    echo "  Waiting for server..."
    for i in $(seq 1 20); do
        curl -s --max-time 1 "http://localhost:$PORT/health" > /dev/null 2>&1 && break
        sleep 1; printf "."
    done
    echo ""
    log "Server is ready at http://localhost:$PORT"
fi

# ── Desktop app ───────────────────────────────────────────────────────────────
if [ ! -f "$ELECTRON" ]; then
    warn "Electron not found at $ELECTRON"
    warn "Run: cd packages/desktop-app && npm install electron"
    # Fallback: open in browser
    if command -v xdg-open &>/dev/null; then
        xdg-open "http://localhost:$PORT" &
        log "Opened in browser instead"
    fi
    exit 0
fi

echo "  Starting desktop app..."
# Unset ELECTRON_RUN_AS_NODE so Electron starts as GUI app, not Node.js
# Auto-detect display if not set
_DISPLAY="${DISPLAY:-$(who | awk '{print $5}' | grep -oE ':[0-9]+' | head -1)}"
_DISPLAY="${_DISPLAY:-:1}"
env -u ELECTRON_RUN_AS_NODE -u ELECTRON_NO_ATTACH_CONSOLE DISPLAY="$_DISPLAY" "$ELECTRON" "$DESKTOP" --no-sandbox 2>/dev/null &
DESKTOP_PID=$!
echo "$DESKTOP_PID" > "$PID_DIR/desktop.pid"
log "Desktop app launched (PID $DESKTOP_PID)"

echo ""
echo "  ═══════════════════════════════════════"
echo "   ICECODE is running!"
echo "   Web:  http://localhost:$PORT"
echo "   Docs: http://localhost:$PORT/docs"
echo "   Log:  $LOG_DIR/server.log"
echo "   Stop: ./stop.sh"
echo "  ═══════════════════════════════════════"
echo ""
