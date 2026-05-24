"""Unit tests for icecode_server.routes.diagnostics

Tests diagnostics summary, health, and run endpoints.
No heavy patching needed — all checks are read-only filesystem/import probes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
for _p in ("packages/core", "packages/server", "packages/tools"):
    sys.path.insert(0, str(ROOT / _p))

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/diagnostics/
# ---------------------------------------------------------------------------

class TestDiagnosticsSummary:
    def test_diagnostics_returns_200(self, client):
        resp = client.get("/api/diagnostics/")
        assert resp.status_code == 200

    def test_diagnostics_is_dict(self, client):
        data = client.get("/api/diagnostics/").json()
        assert isinstance(data, dict)

    def test_diagnostics_has_python(self, client):
        data = client.get("/api/diagnostics/").json()
        assert "python" in data

    def test_diagnostics_has_platform(self, client):
        data = client.get("/api/diagnostics/").json()
        assert "platform" in data

    def test_diagnostics_has_packages(self, client):
        data = client.get("/api/diagnostics/").json()
        assert "packages" in data
        assert isinstance(data["packages"], dict)

    def test_diagnostics_packages_has_fastapi(self, client):
        data = client.get("/api/diagnostics/").json()
        assert "fastapi" in data["packages"]


# ---------------------------------------------------------------------------
# GET /api/diagnostics/health
# ---------------------------------------------------------------------------

class TestDiagnosticsHealth:
    def test_health_returns_200(self, client):
        resp = client.get("/api/diagnostics/health")
        assert resp.status_code == 200

    def test_health_is_dict(self, client):
        data = client.get("/api/diagnostics/health").json()
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# GET /api/diagnostics/run
# ---------------------------------------------------------------------------

class TestDiagnosticsRun:
    def test_run_returns_200(self, client):
        resp = client.get("/api/diagnostics/run")
        assert resp.status_code == 200

    def test_run_returns_event_stream(self, client):
        resp = client.get("/api/diagnostics/run")
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_run_body_nonempty(self, client):
        resp = client.get("/api/diagnostics/run")
        assert len(resp.text) > 0

    def test_run_contains_start_event(self, client):
        resp = client.get("/api/diagnostics/run")
        assert "start" in resp.text or "section" in resp.text
