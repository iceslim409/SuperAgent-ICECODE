"""Unit tests for icecode_server.routes.local_models

Tests scan, models list, model info, routing config, setup, and chat.
Patches get_local_manager so no real Ollama server is needed.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).parents[2]
for _p in ("packages/core", "packages/server", "packages/tools"):
    sys.path.insert(0, str(ROOT / _p))

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


def _make_manager(models=None, ctx=8192, server_type="ollama"):
    mgr = MagicMock()
    mgr.scan_local_servers.return_value = {"ollama": "http://localhost:11434"}
    mgr.list_available_models.return_value = models or ["qwen2.5:7b", "phi4-mini:latest"]
    mgr.get_context_length.return_value = ctx
    mgr.get_server_type.return_value = server_type
    mgr.get_stream_timeout.return_value = 300
    mgr.get_client_config.return_value = {
        "context_length": ctx,
        "server_type": server_type,
        "ollama_num_ctx": ctx,
    }
    return mgr


@pytest.fixture()
def mock_manager():
    mgr = _make_manager()
    with patch("icecode.local_inference.manager.get_local_manager", return_value=mgr):
        yield mgr


# ---------------------------------------------------------------------------
# GET /api/local-models/scan
# ---------------------------------------------------------------------------

class TestScanLocalServers:
    def test_scan_returns_200(self, client, mock_manager):
        resp = client.get("/api/local-models/scan")
        assert resp.status_code == 200

    def test_scan_has_found(self, client, mock_manager):
        data = client.get("/api/local-models/scan").json()
        assert "found" in data

    def test_scan_has_servers(self, client, mock_manager):
        data = client.get("/api/local-models/scan").json()
        assert "servers" in data
        assert isinstance(data["servers"], dict)

    def test_scan_found_count(self, client, mock_manager):
        data = client.get("/api/local-models/scan").json()
        assert data["found"] >= 1

    def test_scan_error_still_200(self, client):
        with patch("icecode.local_inference.manager.get_local_manager", side_effect=Exception("no server")):
            resp = client.get("/api/local-models/scan")
        assert resp.status_code == 200
        assert resp.json()["found"] == 0


# ---------------------------------------------------------------------------
# GET /api/local-models/models
# ---------------------------------------------------------------------------

class TestListLocalModels:
    def test_models_returns_200(self, client, mock_manager):
        resp = client.get("/api/local-models/models")
        assert resp.status_code == 200

    def test_models_has_models_list(self, client, mock_manager):
        data = client.get("/api/local-models/models").json()
        assert "models" in data
        assert isinstance(data["models"], list)

    def test_models_count(self, client, mock_manager):
        data = client.get("/api/local-models/models").json()
        assert data["count"] == 2

    def test_models_error_returns_empty(self, client):
        with patch("icecode.local_inference.manager.get_local_manager", side_effect=Exception("offline")):
            data = client.get("/api/local-models/models").json()
        assert data["models"] == []
        assert "error" in data


# ---------------------------------------------------------------------------
# GET /api/local-models/info
# ---------------------------------------------------------------------------

class TestModelInfo:
    def test_info_returns_200(self, client, mock_manager):
        resp = client.get("/api/local-models/info?model=qwen2.5:7b")
        assert resp.status_code == 200

    def test_info_has_model(self, client, mock_manager):
        data = client.get("/api/local-models/info?model=qwen2.5:7b").json()
        assert data["model"] == "qwen2.5:7b"

    def test_info_has_context_length(self, client, mock_manager):
        data = client.get("/api/local-models/info?model=qwen2.5:7b").json()
        assert "context_length" in data
        assert data["context_length"] == 8192

    def test_info_has_server_type(self, client, mock_manager):
        data = client.get("/api/local-models/info?model=qwen2.5:7b").json()
        assert "server_type" in data

    def test_info_error_returns_error_field(self, client):
        with patch("icecode.local_inference.manager.get_local_manager", side_effect=Exception("fail")):
            data = client.get("/api/local-models/info?model=test").json()
        assert "error" in data


# ---------------------------------------------------------------------------
# GET /api/local-models/routing
# ---------------------------------------------------------------------------

class TestRoutingConfig:
    def test_routing_returns_200(self, client):
        mock_router = MagicMock()
        mock_router.report.return_value = {"main_model": "qwen2.5:7b", "routing": {}}
        with patch("icecode.local_inference.router.LocalModelRouter", return_value=mock_router):
            resp = client.get("/api/local-models/routing")
        assert resp.status_code == 200

    def test_routing_error_returns_200(self, client):
        with patch("icecode.local_inference.router.LocalModelRouter", side_effect=Exception("not configured")):
            resp = client.get("/api/local-models/routing")
        assert resp.status_code == 200
        assert "error" in resp.json()


# ---------------------------------------------------------------------------
# POST /api/local-models/setup
# ---------------------------------------------------------------------------

class TestSetupLocalRouting:
    def test_setup_returns_200(self, client, mock_manager, tmp_path):
        with patch("icecode.config.settings.ICECodeSettings") as MockSettings:
            cfg = MagicMock()
            cfg.home_dir = tmp_path
            MockSettings.return_value = cfg
            resp = client.post("/api/local-models/setup", json={
                "main_model": "qwen2.5:7b",
                "main_base_url": "http://localhost:11434",
            })
        assert resp.status_code == 200

    def test_setup_has_main_model(self, client, mock_manager, tmp_path):
        with patch("icecode.config.settings.ICECodeSettings") as MockSettings:
            cfg = MagicMock()
            cfg.home_dir = tmp_path
            MockSettings.return_value = cfg
            data = client.post("/api/local-models/setup", json={
                "main_model": "phi4-mini:latest",
            }).json()
        assert data.get("main_model") == "phi4-mini:latest"
