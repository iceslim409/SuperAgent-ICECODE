"""Unit tests for icecode_server.routes.providers

Tests provider CRUD: catalog, list, add, detect-models, delete.
Provider persistence uses ~/.icecode/data/providers.json — tests use a temp
file patched via _load_providers / _save_providers.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

ROOT = Path(__file__).parents[2]
for _p in ("packages/core", "packages/server", "packages/tools"):
    sys.path.insert(0, str(ROOT / _p))

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


@pytest.fixture()
def empty_providers(tmp_path):
    """Patch provider storage to use an empty temp file."""
    providers_file = tmp_path / "providers.json"
    providers_file.write_text("[]")
    with patch(
        "icecode_server.routes.providers._load_providers",
        return_value=[],
    ), patch(
        "icecode_server.routes.providers._save_providers",
    ) as mock_save:
        yield mock_save


@pytest.fixture()
def one_provider():
    """Patch with a single pre-configured provider."""
    providers = [{
        "id": "openai",
        "api_key": "sk-test-123",
        "base_url": "",
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o", "gpt-4o-mini"],
        "enabled": True,
    }]
    with patch(
        "icecode_server.routes.providers._load_providers",
        return_value=providers,
    ), patch("icecode_server.routes.providers._save_providers"):
        yield providers


# ---------------------------------------------------------------------------
# GET /api/providers/catalog
# ---------------------------------------------------------------------------

class TestProviderCatalog:
    def test_catalog_returns_200(self, client):
        resp = client.get("/api/providers/catalog")
        assert resp.status_code == 200

    def test_catalog_has_providers_key(self, client):
        data = client.get("/api/providers/catalog").json()
        assert "providers" in data

    def test_catalog_providers_is_list(self, client):
        data = client.get("/api/providers/catalog").json()
        assert isinstance(data["providers"], list)

    def test_catalog_providers_nonempty(self, client):
        data = client.get("/api/providers/catalog").json()
        assert len(data["providers"]) > 0

    def test_catalog_entry_has_id(self, client):
        data = client.get("/api/providers/catalog").json()
        for p in data["providers"]:
            assert "id" in p

    def test_catalog_entry_has_configured_flag(self, client):
        data = client.get("/api/providers/catalog").json()
        for p in data["providers"]:
            assert "configured" in p
            assert isinstance(p["configured"], bool)

    def test_known_providers_in_catalog(self, client):
        data = client.get("/api/providers/catalog").json()
        ids = {p["id"] for p in data["providers"]}
        # At minimum one well-known provider should be in catalog
        assert ids & {"openai", "anthropic", "ollama", "gemini", "groq"}


# ---------------------------------------------------------------------------
# GET /api/providers/
# ---------------------------------------------------------------------------

class TestListProviders:
    def test_list_returns_200(self, client):
        resp = client.get("/api/providers/")
        assert resp.status_code == 200

    def test_list_returns_list(self, client):
        data = client.get("/api/providers/").json()
        assert isinstance(data, list)

    def test_api_keys_are_redacted(self, client, one_provider):
        data = client.get("/api/providers/").json()
        for p in data:
            key = p.get("api_key", "")
            assert key != "sk-test-123", "Real API key leaked in response"
            if key:
                assert key == "***", f"Key not properly redacted: {key}"


# ---------------------------------------------------------------------------
# POST /api/providers/ (add)
# ---------------------------------------------------------------------------

class TestAddProvider:
    def test_add_provider_returns_200(self, client, empty_providers):
        with patch(
            "icecode_server.routes.providers._detect_models",
            new=AsyncMock(return_value=["gpt-4o", "gpt-4o-mini"]),
        ):
            resp = client.post("/api/providers/", json={
                "provider_id": "openai",
                "api_key": "sk-test-abc",
                "base_url": "",
                "default_model": "gpt-4o-mini",
            })
        assert resp.status_code == 200

    def test_add_provider_redacts_key_in_response(self, client, empty_providers):
        with patch(
            "icecode_server.routes.providers._detect_models",
            new=AsyncMock(return_value=["model-x"]),
        ):
            resp = client.post("/api/providers/", json={
                "provider_id": "test_prov",
                "api_key": "secret-key-99",
            })
        data = resp.json()
        assert data.get("api_key") != "secret-key-99"

    def test_add_provider_returns_models_found(self, client, empty_providers):
        with patch(
            "icecode_server.routes.providers._detect_models",
            new=AsyncMock(return_value=["m1", "m2", "m3"]),
        ):
            resp = client.post("/api/providers/", json={
                "provider_id": "groq",
                "api_key": "gsk-test",
            })
        data = resp.json()
        assert "models_found" in data
        assert data["models_found"] == 3

    def test_add_provider_calls_save(self, client, empty_providers):
        with patch(
            "icecode_server.routes.providers._detect_models",
            new=AsyncMock(return_value=[]),
        ):
            client.post("/api/providers/", json={
                "provider_id": "test_save",
                "api_key": "x",
            })
        empty_providers.assert_called()


# ---------------------------------------------------------------------------
# POST /api/providers/{id}/detect-models
# ---------------------------------------------------------------------------

class TestDetectModels:
    def test_detect_existing_provider(self, client, one_provider):
        with patch(
            "icecode_server.routes.providers._detect_models",
            new=AsyncMock(return_value=["gpt-4o", "o1"]),
        ):
            resp = client.post("/api/providers/openai/detect-models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "gpt-4o" in data["models"]

    def test_detect_nonexistent_provider_returns_404(self, client, empty_providers):
        resp = client.post("/api/providers/does-not-exist/detect-models")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/providers/{id}/models
# ---------------------------------------------------------------------------

class TestGetProviderModels:
    def test_get_models_existing(self, client, one_provider):
        resp = client.get("/api/providers/openai/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert isinstance(data["models"], list)

    def test_get_models_nonexistent_returns_404(self, client, empty_providers):
        resp = client.get("/api/providers/ghost/models")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/providers/{id}
# ---------------------------------------------------------------------------

class TestDeleteProvider:
    def test_delete_provider(self, client, one_provider):
        resp = client.delete("/api/providers/openai")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True

    def test_delete_nonexistent_still_200(self, client, empty_providers):
        # Idempotent delete — removing something not there should not 500
        resp = client.delete("/api/providers/ghost")
        assert resp.status_code in (200, 404)
