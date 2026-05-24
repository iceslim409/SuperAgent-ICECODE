"""Unit tests for icecode_server.routes.agents

Tests agent CRUD, auto-models, reload-defaults, generate.
Patches _load_agents/_save_agents/_get_ollama_models so no disk/HTTP needed.
"""
from __future__ import annotations

import sys
from copy import deepcopy
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


_SAMPLE_AGENTS = [
    {
        "id": "agent_abc",
        "name": "Coder",
        "description": "Writes code",
        "model": "qwen2.5-coder:7b",
        "provider": "ollama",
        "tools": ["read_file", "write_file"],
        "system_prompt": None,
        "channel_ids": [],
        "enabled": True,
        "mode": None,
        "enable_computer": False,
        "source": "default",
        "created_at": "2025-01-01T10:00:00",
    },
    {
        "id": "agent_xyz",
        "name": "Researcher",
        "description": "Searches the web",
        "model": "qwen2.5:7b",
        "provider": "ollama",
        "tools": ["search_web"],
        "system_prompt": None,
        "channel_ids": [],
        "enabled": False,
        "mode": None,
        "enable_computer": False,
        "source": "user",
        "created_at": "2025-01-02T08:00:00",
    },
]

_FAKE_MODELS = ["qwen2.5-coder:7b", "qwen2.5:7b", "phi4-mini:latest"]


@pytest.fixture()
def mock_agents():
    store = [deepcopy(_SAMPLE_AGENTS)]
    with patch("icecode_server.routes.agents._load_agents", return_value=deepcopy(_SAMPLE_AGENTS)), \
         patch("icecode_server.routes.agents._save_agents", side_effect=lambda a: store.__setitem__(0, a)) as mock_save, \
         patch("icecode_server.routes.agents._get_ollama_models", return_value=_FAKE_MODELS):
        yield mock_save


@pytest.fixture()
def empty_agents():
    store = [[]]
    with patch("icecode_server.routes.agents._load_agents", return_value=[]), \
         patch("icecode_server.routes.agents._save_agents", side_effect=lambda a: store.__setitem__(0, a)) as mock_save, \
         patch("icecode_server.routes.agents._get_ollama_models", return_value=_FAKE_MODELS):
        yield mock_save


# ---------------------------------------------------------------------------
# GET /api/agents/
# ---------------------------------------------------------------------------

class TestListAgents:
    def test_list_returns_200(self, client, mock_agents):
        resp = client.get("/api/agents/")
        assert resp.status_code == 200

    def test_list_returns_list(self, client, mock_agents):
        data = client.get("/api/agents/").json()
        assert isinstance(data, list)

    def test_list_count(self, client, mock_agents):
        data = client.get("/api/agents/").json()
        assert len(data) == 2

    def test_each_agent_has_id(self, client, mock_agents):
        data = client.get("/api/agents/").json()
        for a in data:
            assert "id" in a

    def test_list_empty_returns_empty(self, client, empty_agents):
        data = client.get("/api/agents/").json()
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# GET /api/agents/auto-models
# ---------------------------------------------------------------------------

class TestAutoModels:
    def test_auto_models_returns_200(self, client, mock_agents):
        resp = client.get("/api/agents/auto-models")
        assert resp.status_code == 200

    def test_auto_models_has_installed(self, client, mock_agents):
        data = client.get("/api/agents/auto-models").json()
        assert "installed" in data
        assert isinstance(data["installed"], list)

    def test_auto_models_has_auto_selected(self, client, mock_agents):
        data = client.get("/api/agents/auto-models").json()
        assert "auto_selected" in data

    def test_auto_models_total_count(self, client, mock_agents):
        data = client.get("/api/agents/auto-models").json()
        assert data["total_installed"] == len(_FAKE_MODELS)


# ---------------------------------------------------------------------------
# POST /api/agents/reload-defaults
# ---------------------------------------------------------------------------

class TestReloadDefaults:
    def test_reload_defaults_returns_200(self, client, mock_agents):
        resp = client.post("/api/agents/reload-defaults")
        assert resp.status_code == 200

    def test_reload_defaults_returns_ok(self, client, mock_agents):
        data = client.post("/api/agents/reload-defaults").json()
        assert data.get("ok") is True

    def test_reload_defaults_has_count(self, client, mock_agents):
        data = client.post("/api/agents/reload-defaults").json()
        assert "count" in data
        assert data["count"] > 0


# ---------------------------------------------------------------------------
# POST /api/agents/
# ---------------------------------------------------------------------------

class TestCreateAgent:
    def test_create_returns_200(self, client, mock_agents):
        resp = client.post("/api/agents/", json={"name": "New Agent"})
        assert resp.status_code == 200

    def test_create_has_id(self, client, mock_agents):
        data = client.post("/api/agents/", json={"name": "Test"}).json()
        assert "id" in data
        assert data["id"].startswith("agent_")

    def test_create_stores_name(self, client, mock_agents):
        data = client.post("/api/agents/", json={"name": "My Agent"}).json()
        assert data["name"] == "My Agent"

    def test_create_with_explicit_model(self, client, mock_agents):
        data = client.post("/api/agents/", json={
            "name": "Explicit", "model": "phi4-mini:latest"
        }).json()
        assert data["model"] == "phi4-mini:latest"

    def test_create_auto_model_resolves(self, client, mock_agents):
        data = client.post("/api/agents/", json={
            "name": "Auto", "model": "auto"
        }).json()
        assert data["model"] != "auto"

    def test_create_calls_save(self, client, mock_agents):
        client.post("/api/agents/", json={"name": "Save test"})
        mock_agents.assert_called()


# ---------------------------------------------------------------------------
# PUT /api/agents/{agent_id}
# ---------------------------------------------------------------------------

class TestUpdateAgent:
    def test_update_returns_200(self, client, mock_agents):
        resp = client.put("/api/agents/agent_abc", json={"name": "Updated"})
        assert resp.status_code == 200

    def test_update_changes_name(self, client, mock_agents):
        data = client.put("/api/agents/agent_abc", json={"name": "Renamed"}).json()
        assert data["name"] == "Renamed"

    def test_update_nonexistent_returns_404(self, client, mock_agents):
        resp = client.put("/api/agents/ghost", json={"name": "X"})
        assert resp.status_code == 404

    def test_update_enabled_flag(self, client, mock_agents):
        data = client.put("/api/agents/agent_xyz", json={"enabled": True}).json()
        assert data["enabled"] is True


# ---------------------------------------------------------------------------
# DELETE /api/agents/{agent_id}
# ---------------------------------------------------------------------------

class TestDeleteAgent:
    def test_delete_returns_200(self, client, mock_agents):
        resp = client.delete("/api/agents/agent_abc")
        assert resp.status_code == 200

    def test_delete_returns_ok(self, client, mock_agents):
        data = client.delete("/api/agents/agent_abc").json()
        assert data.get("ok") is True

    def test_delete_nonexistent_still_ok(self, client, mock_agents):
        # filter-based delete is idempotent
        resp = client.delete("/api/agents/ghost")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/agents/generate
# ---------------------------------------------------------------------------

class TestGenerateAgent:
    def test_generate_returns_200(self, client, mock_agents):
        resp = client.post("/api/agents/generate", json={
            "description": "An agent that searches the web and summarizes articles"
        })
        assert resp.status_code == 200

    def test_generate_returns_ok(self, client, mock_agents):
        data = client.post("/api/agents/generate", json={
            "description": "Coding assistant for Python"
        }).json()
        assert data.get("ok") is True

    def test_generate_has_agent_key(self, client, mock_agents):
        data = client.post("/api/agents/generate", json={
            "description": "Reads and writes files"
        }).json()
        assert "agent" in data

    def test_generate_agent_has_name(self, client, mock_agents):
        data = client.post("/api/agents/generate", json={
            "description": "Web search assistant"
        }).json()
        agent = data.get("agent", data)
        assert "name" in agent

    def test_generate_agent_has_tools(self, client, mock_agents):
        data = client.post("/api/agents/generate", json={
            "description": "Reads and writes files"
        }).json()
        agent = data.get("agent", data)
        assert "tools" in agent
