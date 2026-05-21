#!/usr/bin/env bash
# ICECODE Super-Agent Network — Stop All Services
set -euo pipefail

PID_DIR="$HOME/.icecode"
SERVER_PID_FILE="$PID_DIR/server.pid"
DESKTOP_PID_FILE="$PID_DIR/desktop.pid"
GATEWAY_PID_FILE="$PID_DIR/gateway.pid"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }

echo ""
echo "  ICECODE — Stopping all services..."
echo ""

kill_pid_file() {
    local pidfile="$1"
    local name="$2"
    if [ -f "$pidfile" ]; then
        PID=$(cat "$pidfile")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null && log "$name stopped (PID $PID)" || warn "Could not stop $name (PID $PID)"
            # Give it 3s to shut down gracefully, then force kill
            local waited=0
            while kill -0 "$PID" 2>/dev/null && [ $waited -lt 3 ]; do
                sleep 1
                ((waited++))
            done
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID" 2>/dev/null
                warn "$name force-killed"
            fi
        else
            warn "$name PID $PID no longer running"
        fi
        rm -f "$pidfile"
    else
        warn "$name PID file not found — skipping"
    fi
}

# ── Stop server ───────────────────────────────────────────────────
kill_pid_file "$SERVER_PID_FILE" "ICECODE server"

# ── Stop gateway ─────────────────────────────────────────────────
kill_pid_file "$GATEWAY_PID_FILE" "Gateway process"

# ── Stop desktop app ─────────────────────────────────────────────
kill_pid_file "$DESKTOP_PID_FILE" "Desktop app"

# ── Kill any orphaned uvicorn on port 13210 ───────────────────────
ORPHAN=$(lsof -ti :13210 2>/dev/null || true)
if [ -n "$ORPHAN" ]; then
    echo "$ORPHAN" | xargs kill -9 2>/dev/null && warn "Killed orphaned process on port 13210 (PID $ORPHAN)"
fi

echo ""
echo "  ICECODE stopped. Run ./start.sh to restart."
echo ""
