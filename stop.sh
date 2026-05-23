#!/usr/bin/env bash
# ICECODE Super-Agent Network — Stop All Services
# Kills everything: tracked PIDs, orphan processes, and optionally Ollama runners

PID_DIR="$HOME/.icecode"
SERVER_PID_FILE="$PID_DIR/server.pid"
DESKTOP_PID_FILE="$PID_DIR/desktop.pid"
GATEWAY_PID_FILE="$PID_DIR/gateway.pid"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
info() { echo -e "    $*"; }

echo ""
echo -e "${BOLD}  ICECODE — Stopping all services...${NC}"
echo ""

# ── Helper: kill by PID file ─────────────────────────────────────
kill_pid_file() {
    local pidfile="$1"
    local name="$2"
    if [ -f "$pidfile" ]; then
        local PID
        PID=$(cat "$pidfile" 2>/dev/null || true)
        if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
            kill -TERM "$PID" 2>/dev/null || true
            local waited=0
            while kill -0 "$PID" 2>/dev/null && [ $waited -lt 4 ]; do
                sleep 1; ((waited++))
            done
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID" 2>/dev/null || true
                warn "$name force-killed (PID $PID)"
            else
                log "$name stopped (PID $PID)"
            fi
        else
            [ -n "$PID" ] && info "$name was not running (PID $PID)"
        fi
        rm -f "$pidfile"
    fi
}

# ── Helper: kill all processes matching a pattern ────────────────
kill_pattern() {
    local pattern="$1"
    local name="$2"
    local MY_PID=$$
    local pids
    pids=$(pgrep -f "$pattern" 2>/dev/null | grep -v "^${MY_PID}$" | grep -v "^$(pgrep -f "stop.sh" | head -1)$" || true)
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill -TERM 2>/dev/null || true
        sleep 1
        local survivors
        survivors=$(echo "$pids" | while read -r p; do kill -0 "$p" 2>/dev/null && echo "$p"; done || true)
        if [ -n "$survivors" ]; then
            echo "$survivors" | xargs kill -9 2>/dev/null || true
            warn "$name force-killed (PIDs: $(echo $survivors | tr '\n' ' '))"
        else
            log "$name stopped"
        fi
        return 0
    fi
    return 1
}

# ── Helper: kill whatever is on a TCP port ───────────────────────
kill_port() {
    local port="$1"
    local pids
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill -9 2>/dev/null || true
        warn "Killed orphan on port $port (PID $pids)"
    fi
}

# ── 1. Stop tracked processes (PID files) ───────────────────────
kill_pid_file "$SERVER_PID_FILE"  "ICECODE server"
kill_pid_file "$DESKTOP_PID_FILE" "Desktop app"
kill_pid_file "$GATEWAY_PID_FILE" "Gateway"

# ── 2. Kill any remaining icecode Python processes ───────────────
kill_pattern "uvicorn icecode_server"           "uvicorn (icecode_server)"
kill_pattern "python.*icecode_server"           "Python icecode_server"
kill_pattern "icecode_server.main"              "icecode_server.main"

# ── 3. Kill Electron desktop app ────────────────────────────────
kill_pattern "electron.*desktop-app"            "Electron desktop-app"
kill_pattern "desktop-app.*electron"            "Electron desktop-app"

# ── 4. Kill any orphan on port 13210 ────────────────────────────
kill_port 13210

# ── 5. Unload stuck Ollama runners via API ───────────────────────
OLLAMA_RUNNERS=$(ps aux 2>/dev/null | grep "ollama runner" | grep -v grep | wc -l)
if [ "$OLLAMA_RUNNERS" -gt 0 ]; then
    echo ""
    warn "Found $OLLAMA_RUNNERS Ollama runner(s) in memory. Unloading..."
    # Ask Ollama to unload all loaded models
    loaded=$(curl -s http://localhost:11434/api/ps 2>/dev/null | grep -o '"name":"[^"]*"' | cut -d'"' -f4 || true)
    if [ -n "$loaded" ]; then
        while IFS= read -r model; do
            [ -z "$model" ] && continue
            curl -s -X POST http://localhost:11434/api/generate \
                -H 'Content-Type: application/json' \
                -d "{\"model\":\"${model}\",\"keep_alive\":0,\"prompt\":\"\"}" > /dev/null 2>&1 || true
            log "Unloaded Ollama model: $model"
        done <<< "$loaded"
    fi
    # Ollama runners run as root (snap) — can't kill directly, but unloading via API evicts them
    sleep 2
    REMAINING=$(ps aux 2>/dev/null | grep "ollama runner" | grep -v grep | wc -l)
    if [ "$REMAINING" -gt 0 ]; then
        warn "Ollama runners still running as root — use: sudo systemctl restart snap.ollama.ollama.service"
    else
        log "All Ollama models unloaded"
    fi
fi

# ── 6. Clean up log tail processes opened by start.sh ───────────
kill_pattern "tail -f.*icecode.*server.log"     "Log tail"  || true

# ── 7. Remove stale PID files ────────────────────────────────────
rm -f "$SERVER_PID_FILE" "$DESKTOP_PID_FILE" "$GATEWAY_PID_FILE" 2>/dev/null || true

echo ""
echo "  ICECODE stopped. Run ./start.sh to restart."
echo ""
