"""Tests for /api/models routes."""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


_MODELS = ["llama3:8b", "qwen2.5:7b", "mistral:7b"]


class TestListModels:
    def test_returns_200(self, client):
        with patch("icecode_server.routes.models._get_ollama_models", return_value=_MODELS):
            r = client.get("/api/models/")
        assert r.status_code == 200

    def test_has_models_key(self, client):
        with patch("icecode_server.routes.models._get_ollama_models", return_value=_MODELS):
            data = client.get("/api/models/").json()
        assert "models" in data

    def test_ollama_present(self, client):
        with patch("icecode_server.routes.models._get_ollama_models", return_value=_MODELS):
            data = client.get("/api/models/").json()
        assert "ollama" in data["models"]

    def test_ollama_returns_list(self, client):
        with patch("icecode_server.routes.models._get_ollama_models", return_value=_MODELS):
            data = client.get("/api/models/").json()
        assert isinstance(data["models"]["ollama"], list)

    def test_empty_when_ollama_unavailable(self, client):
        with patch("icecode_server.routes.models._get_ollama_models", return_value=[]):
            data = client.get("/api/models/").json()
        assert data["models"]["ollama"] == []


class TestModelsForProvider:
    def test_ollama_provider_200(self, client):
        with patch("icecode_server.routes.models._get_ollama_models", return_value=_MODELS):
            r = client.get("/api/models/ollama")
        assert r.status_code == 200

    def test_ollama_has_models(self, client):
        with patch("icecode_server.routes.models._get_ollama_models", return_value=_MODELS):
            data = client.get("/api/models/ollama").json()
        assert data["models"] == _MODELS

    def test_unknown_provider_returns_empty(self, client):
        with patch("icecode_server.routes.models._get_ollama_models", return_value=[]):
            data = client.get("/api/models/anthropic").json()
        assert data["models"] == []

    def test_unknown_provider_has_provider_key(self, client):
        with patch("icecode_server.routes.models._get_ollama_models", return_value=[]):
            data = client.get("/api/models/openai").json()
        assert data["provider"] == "openai"
