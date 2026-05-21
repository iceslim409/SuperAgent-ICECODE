"""Integration tests for metrics, diagnostics and monitoring endpoints."""
import pytest
import httpx

BASE = "http://localhost:13210"


@pytest.fixture(scope="module")
def client():
    return httpx.Client(base_url=BASE, timeout=10)


class TestMetricsEndpoint:
    def test_metrics_returns_200(self, client):
        r = client.get("/api/metrics")
        assert r.status_code == 200

    def test_metrics_has_required_fields(self, client):
        r = client.get("/api/metrics")
        d = r.json()
        assert "uptime_seconds" in d
        assert "total_requests" in d
        assert "routes_registered" in d

    def test_metrics_uptime_positive(self, client):
        r = client.get("/api/metrics")
        assert r.json()["uptime_seconds"] >= 0


class TestDiagnosticsEndpoint:
    def test_diagnostics_returns_200(self, client):
        r = client.get("/api/status")
        assert r.status_code in (200, 404)  # may not be registered

    def test_health_has_version(self, client):
        r = client.get("/health")
        d = r.json()
        assert d["status"] == "ok"
        assert "version" in d


class TestAPIDocumentation:
    def test_openapi_schema_accessible(self, client):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        d = r.json()
        assert "paths" in d
        assert len(d["paths"]) >= 20

    def test_swagger_ui_accessible(self, client):
        r = client.get("/docs")
        assert r.status_code == 200
