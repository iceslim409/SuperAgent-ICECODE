"""Integration tests for ICECODE FastAPI server."""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "core"))
sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "server"))

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


class TestHealth:
    def test_health_endpoint(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"
        assert "version" in data


class TestUsageAPI:
    def test_get_usage(self, client):
        r = client.get("/api/usage/")
        assert r.status_code == 200
        data = r.json()
        assert "total_tokens" in data
        assert "total_sessions" in data

    def test_get_session_usage(self, client):
        r = client.get("/api/usage/sessions")
        assert r.status_code == 200
        data = r.json()
        assert "sessions" in data


class TestProvidersAPI:
    def test_catalog_returns_providers(self, client):
        r = client.get("/api/providers/catalog")
        assert r.status_code == 200
        data = r.json()
        assert "providers" in data
        provider_ids = [p["id"] for p in data["providers"]]
        assert "ollama" in provider_ids

    def test_list_configured(self, client):
        r = client.get("/api/providers/")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestKnowledgeAPI:
    def test_knowledge_stats(self, client):
        r = client.get("/api/knowledge/stats")
        assert r.status_code == 200
        data = r.json()
        assert "rag_available" in data

    def test_knowledge_sources_empty(self, client):
        r = client.get("/api/knowledge/sources")
        assert r.status_code == 200
        data = r.json()
        assert "sources" in data


class TestSwarmAPI:
    def test_list_templates(self, client):
        r = client.get("/api/swarm/templates")
        assert r.status_code == 200
        data = r.json()
        assert "templates" in data
        template_ids = [t["id"] for t in data["templates"]]
        assert "research_write" in template_ids
        assert "brainstorm" in template_ids

    def test_get_template_detail(self, client):
        r = client.get("/api/swarm/templates/brainstorm")
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "parallel"

    def test_get_nonexistent_template(self, client):
        r = client.get("/api/swarm/templates/does_not_exist")
        assert r.status_code == 404


class TestSessionsAPI:
    def test_list_sessions(self, client):
        r = client.get("/api/chat/sessions")
        assert r.status_code == 200

    def test_get_nonexistent_session(self, client):
        r = client.get("/api/chat/sessions/nonexistent_session_xyz")
        assert r.status_code == 404
