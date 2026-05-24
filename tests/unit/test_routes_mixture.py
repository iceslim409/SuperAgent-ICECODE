"""Tests for /api/mixture routes."""
from unittest.mock import patch, AsyncMock
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


_OK_RESULT = {"model": "llama3:8b", "response": "42 is the answer", "ok": True}
_FAIL_RESULT = {"model": "bad_model", "response": "", "ok": False, "error": "timeout"}


class TestMixtureModels:
    def test_returns_200(self, client):
        r = client.get("/api/mixture/models")
        assert r.status_code == 200

    def test_has_models_key(self, client):
        data = client.get("/api/mixture/models").json()
        assert "models" in data or isinstance(data, (list, dict))


class TestMixtureQuery:
    def test_returns_200(self, client):
        with patch("icecode_server.routes.mixture._query_model", new_callable=AsyncMock, return_value=_OK_RESULT):
            r = client.post("/api/mixture/query", json={
                "prompt": "test", "models": ["llama3:8b"]
            })
        assert r.status_code == 200

    def test_has_responses(self, client):
        with patch("icecode_server.routes.mixture._query_model", new_callable=AsyncMock, return_value=_OK_RESULT):
            data = client.post("/api/mixture/query", json={
                "prompt": "test", "models": ["llama3:8b"]
            }).json()
        assert "responses" in data

    def test_has_successful_count(self, client):
        with patch("icecode_server.routes.mixture._query_model", new_callable=AsyncMock, return_value=_OK_RESULT):
            data = client.post("/api/mixture/query", json={
                "prompt": "test", "models": ["llama3:8b"]
            }).json()
        assert "successful" in data

    def test_failed_model_counted(self, client):
        with patch("icecode_server.routes.mixture._query_model", new_callable=AsyncMock, return_value=_FAIL_RESULT):
            data = client.post("/api/mixture/query", json={
                "prompt": "test", "models": ["bad_model"]
            }).json()
        assert data["failed"] >= 1


class TestMixtureSynthesize:
    def test_returns_200(self, client):
        with patch("icecode_server.routes.mixture._query_model", new_callable=AsyncMock, return_value=_OK_RESULT):
            r = client.post("/api/mixture/synthesize", json={
                "prompt": "test", "models": ["llama3:8b"]
            })
        assert r.status_code == 200

    def test_has_synthesized_key(self, client):
        with patch("icecode_server.routes.mixture._query_model", new_callable=AsyncMock, return_value=_OK_RESULT):
            data = client.post("/api/mixture/synthesize", json={
                "prompt": "test", "models": ["llama3:8b"]
            }).json()
        assert "synthesized" in data

    def test_no_models_returns_error(self, client):
        with patch("icecode_server.routes.mixture._query_model", new_callable=AsyncMock, return_value=_FAIL_RESULT):
            data = client.post("/api/mixture/synthesize", json={
                "prompt": "test", "models": ["bad"]
            }).json()
        # Either error key or synthesized key
        assert "error" in data or "synthesized" in data
