#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
#  ICECODE Auto-Debug — verifică starea reală a proiectului
#  Rulează: bash debug.sh  sau  make debug
# ═══════════════════════════════════════════════════════════
set -uo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ── Culori ────────────────────────────────────────────────
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

PASS=0; FAIL=0; WARN=0
ISSUES=()

ok()   { echo -e "  ${GREEN}✓${RESET} $1"; PASS=$((PASS+1)); }
fail() { echo -e "  ${RED}✗${RESET} $1"; FAIL=$((FAIL+1)); ISSUES+=("$1"); }
warn() { echo -e "  ${YELLOW}⚠${RESET} $1"; WARN=$((WARN+1)); }
section() { echo -e "\n${CYAN}${BOLD}══ $1 ══${RESET}"; }

echo -e "${BOLD}"
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   ICECODE Auto-Debug                     ║"
echo "  ║   $(date '+%Y-%m-%d %H:%M:%S')                    ║"
echo "  ╚══════════════════════════════════════════╝"
echo -e "${RESET}"

# ── 1. Python imports ─────────────────────────────────────
section "Python imports"
PYPATH="$ROOT/packages/core:$ROOT/packages/server:$ROOT/packages/tools:$ROOT/packages/cli"

if PYTHONPATH="$PYPATH" python3 -c "from icecode import ICECodeAgent" 2>/dev/null; then
  ok "from icecode import ICECodeAgent"
else
  fail "from icecode import ICECodeAgent"
fi

if PYTHONPATH="$PYPATH" python3 -c "from icecode_server.main import create_app" 2>/dev/null; then
  ok "from icecode_server.main import create_app"
else
  fail "from icecode_server.main import create_app"
fi

# ── 2. Pachete Python instalate ───────────────────────────
section "Pachete Python instalate"
# Verifică via pip SAU via import direct (PYTHONPATH e suficient)
_pycheck() {
  local pkg="$1" mod="$2"
  if pip show "$pkg" &>/dev/null 2>&1; then
    ok "$pkg (pip instalat)"
  elif PYTHONPATH="$PYPATH" python3 -c "import $mod" &>/dev/null 2>&1; then
    ok "$pkg (disponibil via PYTHONPATH)"
  else
    fail "$pkg LIPSEȘTE — rulează: pip install -e packages/$(echo $pkg | sed 's/icecode-//')"
  fi
}
_pycheck "icecode-core"   "icecode"
_pycheck "icecode-server" "icecode_server"
_pycheck "icecode-tools"  "icecode_tools"

# ── 3. Tools active ───────────────────────────────────────
section "Agent tools"
TOOL_COUNT=$(PYTHONPATH="$PYPATH" python3 -c "
import sys
from icecode.agent.core import TOOLS, _load_extended_tools
ext = _load_extended_tools()
base = {t['function']['name'] for t in TOOLS}
all_t = base | {t['function']['name'] for t in ext}
print(len(all_t))
" 2>/dev/null || echo "0")

if [ "$TOOL_COUNT" -ge 70 ]; then
  ok "$TOOL_COUNT tools active"
elif [ "$TOOL_COUNT" -ge 20 ]; then
  warn "$TOOL_COUNT tools active (așteptat 70+)"
else
  fail "Doar $TOOL_COUNT tools active — verifică _load_extended_tools()"
fi

# ── 4. Rute API ───────────────────────────────────────────
section "Rute API"
ROUTE_COUNT=$(PYTHONPATH="$PYPATH" python3 -c "
from icecode_server.main import create_app
app = create_app()
routes = [r for r in app.routes if hasattr(r,'methods')]
print(len(routes))
" 2>/dev/null || echo "0")

if [ "$ROUTE_COUNT" -ge 150 ]; then
  ok "$ROUTE_COUNT rute API înregistrate"
elif [ "$ROUTE_COUNT" -ge 50 ]; then
  warn "$ROUTE_COUNT rute API (așteptat 150+)"
else
  fail "Doar $ROUTE_COUNT rute API — verifică main.py"
fi

# ── 5. Symlink-uri sparte ─────────────────────────────────
section "Symlink-uri"
BROKEN=0
while IFS= read -r -d '' link; do
  target=$(readlink "$link")
  if [ ! -e "$link" ]; then
    fail "Symlink spart: $link → $target"
    ((BROKEN++))
  fi
done < <(find "$ROOT/packages" -maxdepth 5 -type l -print0 2>/dev/null)

if [ "$BROKEN" -eq 0 ]; then
  ok "Niciun symlink spart"
fi

# ── 6. Teste pytest ───────────────────────────────────────
section "Teste pytest"
if ! command -v python3 &>/dev/null; then
  warn "python3 negăsit — skip pytest"
else
  PYTEST_OUT=$(PYTHONPATH="$PYPATH" python3 -m pytest tests/ -q --tb=no 2>&1 | tail -3)
  PASSED=$(echo "$PYTEST_OUT" | grep -oP '\d+(?= passed)' || echo "0")
  FAILED=$(echo "$PYTEST_OUT" | grep -oP '\d+(?= failed)' || echo "0")

  if [ "$FAILED" -eq 0 ] && [ "$PASSED" -gt 0 ]; then
    ok "$PASSED teste trec, 0 eșuează"
  elif [ "$FAILED" -gt 0 ]; then
    fail "$FAILED teste eșuează din $PASSED+$FAILED total"
    # Arată care pică
    PYTHONPATH="$PYPATH" python3 -m pytest tests/ -q --tb=line 2>&1 | grep "FAILED" | while read line; do
      echo -e "    ${RED}→${RESET} $line"
    done
  else
    warn "Niciun test găsit sau pytest eșuat"
  fi
fi

# ── 7. Git status ─────────────────────────────────────────
section "Git repository"
if git rev-parse --git-dir &>/dev/null; then
  MODIFIED=$(git status --short | grep -c "^ M\| M" || true)
  UNTRACKED=$(git status --short | grep -c "^??" || true)
  BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
  COMMITS=$(git log --oneline 2>/dev/null | wc -l | tr -d ' ')

  ok "Branch: $BRANCH ($COMMITS commituri)"

  if [ "$MODIFIED" -eq 0 ] && [ "$UNTRACKED" -eq 0 ]; then
    ok "Working tree curat"
  else
    [ "$MODIFIED" -gt 0 ] && warn "$MODIFIED fișiere modificate necommitate"
    [ "$UNTRACKED" -gt 0 ] && warn "$UNTRACKED fișiere noi necommitate"
    echo -e "  ${YELLOW}→${RESET} Rulează: git status"
  fi

  # Verifică dacă e în sync cu remote
  git fetch origin --quiet 2>/dev/null || true
  AHEAD=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "0")
  BEHIND=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo "0")
  [ "$BEHIND" -gt 0 ] && warn "$BEHIND commituri nepusate pe remote"
  [ "$BEHIND" -eq 0 ] && ok "Sincronizat cu GitHub"
else
  warn "Nu e un repo git (nu se verifică git status)"
fi

# ── 8. Server health ──────────────────────────────────────
section "Server HTTP"
PORT="${ICECODE_PORT:-13210}"
if curl -sf "http://localhost:$PORT/health" -o /dev/null 2>/dev/null; then
  VERSION=$(curl -s "http://localhost:$PORT/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('version','?'))" 2>/dev/null || echo "?")
  ok "Server rulează pe :$PORT (v$VERSION)"

  # Verifică câte rute răspund
  STATUS=$(curl -s "http://localhost:$PORT/api/status" 2>/dev/null)
  [ -n "$STATUS" ] && ok "API /api/status OK"
else
  warn "Server nu rulează pe :$PORT — pornește cu: make run"
fi

# ── 9. Fișiere critice ────────────────────────────────────
section "Fișiere critice"
CRITICAL=(
  "packages/core/icecode/agent/core.py"
  "packages/server/icecode_server/main.py"
  "packages/web-ui/index.html"
  "packages/tools/icecode_tools/registry.py"
  "tests/conftest.py"
  ".env.example"
)
for f in "${CRITICAL[@]}"; do
  if [ -f "$ROOT/$f" ]; then
    ok "$f"
  else
    fail "$f LIPSEȘTE"
  fi
done

# ── 10. Sumar final ───────────────────────────────────────
echo -e "\n${BOLD}══════════════════════════════════════════${RESET}"
echo -e "${BOLD}  SUMAR FINAL${RESET}"
echo -e "  ${GREEN}✓ $PASS checks OK${RESET}"
[ "$WARN" -gt 0 ] && echo -e "  ${YELLOW}⚠ $WARN avertismente${RESET}"
[ "$FAIL" -gt 0 ] && echo -e "  ${RED}✗ $FAIL probleme găsite${RESET}"
echo ""

if [ "$FAIL" -eq 0 ] && [ "$WARN" -eq 0 ]; then
  echo -e "  ${GREEN}${BOLD}Proiectul e la 100% ✓${RESET}"
elif [ "$FAIL" -eq 0 ]; then
  echo -e "  ${YELLOW}${BOLD}Proiect funcțional cu $WARN avertismente minore${RESET}"
else
  echo -e "  ${RED}${BOLD}$FAIL probleme de rezolvat:${RESET}"
  for issue in "${ISSUES[@]}"; do
    echo -e "    ${RED}→${RESET} $issue"
  done
fi
echo ""

exit $FAIL
