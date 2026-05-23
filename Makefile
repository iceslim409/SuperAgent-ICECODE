# ICECODE Super-Agent Network — Developer Makefile
# Usage: make <target>

PYTHON     = python3
VENV       = .venv
PY_VENV    = $(VENV)/bin/python
PIP_VENV   = $(VENV)/bin/pip
UVICORN    = $(VENV)/bin/uvicorn
PYTEST     = $(VENV)/bin/pytest
SERVER_DIR = packages/server
CORE_DIR   = packages/core
PORT       = 13210

PYTHONPATH_EXPORT = PYTHONPATH="$(shell pwd)/packages/core:$(shell pwd)/packages/server:$(shell pwd)/packages/tools"

.PHONY: help install run dev test test-unit test-integration clean stop logs debug docker-build docker-run docker-stop docker-logs docker-with-ollama

help:
	@echo ""
	@echo "  ICECODE Super-Agent Network"
	@echo "  ═══════════════════════════════"
	@echo "  make install        — First-time setup (install all deps)"
	@echo "  make run            — Start production server on port $(PORT)"
	@echo "  make dev            — Start server with hot-reload"
	@echo "  make test           — Run all tests"
	@echo "  make test-unit      — Run unit tests only"
	@echo "  make test-int       — Run integration tests only"
	@echo "  make debug          — Auto-debug: verifică tot proiectul"
	@echo "  make stop           — Kill running server"
	@echo "  make logs           — Tail server logs"
	@echo "  make clean          — Remove cache and build artifacts"
	@echo "  make docker-build   — Build Docker image"
	@echo "  make docker-run     — Start via Docker Compose"
	@echo "  make docker-stop    — Stop Docker containers"
	@echo ""

debug:
	@bash debug.sh

install:
	@bash install.sh

run:
	@echo "Starting ICECODE server on http://localhost:$(PORT)..."
	@$(PYTHONPATH_EXPORT) $(PY_VENV) -m uvicorn icecode_server.main:app \
		--host 0.0.0.0 --port $(PORT) \
		--workers 1 \
		2>&1 | tee ~/.icecode/logs/server.log

dev:
	@echo "Starting ICECODE in development mode (hot-reload)..."
	@$(PYTHONPATH_EXPORT) $(PY_VENV) -m uvicorn icecode_server.main:app \
		--host 0.0.0.0 --port $(PORT) \
		--reload \
		--reload-dir $(SERVER_DIR) \
		--reload-dir $(CORE_DIR)

test:
	@echo "Running all tests..."
	@$(PYTHONPATH_EXPORT) $(PYTEST) tests/ -v

test-unit:
	@echo "Running unit tests..."
	@$(PYTHONPATH_EXPORT) $(PYTEST) tests/unit/ -v

test-int:
	@echo "Running integration tests..."
	@$(PYTHONPATH_EXPORT) $(PYTEST) tests/integration/ -v

stop:
	@pkill -f "uvicorn icecode_server" 2>/dev/null && echo "Server stopped." || echo "No server running."

logs:
	@tail -f ~/.icecode/logs/server.log 2>/dev/null || echo "No logs found. Start server with: make run"

clean:
	@find . -type d -name "__pycache__" -not -path "*/node_modules/*" -not -path "*/.venv/*" | xargs rm -rf
	@find . -name "*.pyc" -not -path "*/.venv/*" -delete
	@find . -name ".pytest_cache" -type d | xargs rm -rf
	@echo "Cache cleared."

knowledge-index:
	@echo "Indexing current directory into knowledge base..."
	@curl -s -X POST http://localhost:$(PORT)/api/knowledge/index \
		-H "Content-Type: application/json" \
		-d '{"path": ".", "recursive": true}' | python3 -m json.tool

status:
	@curl -s http://localhost:$(PORT)/health | python3 -m json.tool 2>/dev/null || echo "Server not running."

docker-build:
	@echo "Building ICECODE Docker image..."
	docker build -t icecode:latest .

docker-run:
	@echo "Starting ICECODE via Docker Compose..."
	docker compose up -d icecode
	@echo "Server: http://localhost:$(PORT)"

docker-stop:
	docker compose down

docker-logs:
	docker compose logs -f icecode

docker-with-ollama:
	docker compose --profile with-ollama up -d
