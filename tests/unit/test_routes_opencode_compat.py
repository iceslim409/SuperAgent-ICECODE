"""Unit tests for icecode_server.routes.opencode_compat

Tests the OpenCode-compatible API layer.
Patches get_session_store so no real agent or disk is needed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).parents[2]
for _p in ("packages/core", "packages/server", "packages/tools"):
    sys.path.insert(0, str(ROOT / _p))

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


_SAMPLE_SESSION = {
    "id": "ses_abc123",
    "title": "Test session",
    "messages": [
        {"id": "msg_1", "role": "user", "content": "Hello"},
        {"id": "msg_2", "role": "assistant", "content": "Hi there"},
    ],
}


def _make_mock_store(session=None):
    store = MagicMock()
    store.list.return_value = [session] if session else []
    store.load.return_value = session
    store.delete.return_value = None
    return store


@pytest.fixture()
def mock_store():
    store = _make_mock_store(_SAMPLE_SESSION)
    with patch("icecode.agent.core.get_session_store", return_value=store):
        yield store


@pytest.fixture()
def empty_store():
    store = _make_mock_store(None)
    with patch("icecode.agent.core.get_session_store", return_value=store):
        yield store


# ---------------------------------------------------------------------------
# GET /session
# ---------------------------------------------------------------------------

class TestListSessions:
    def test_list_sessions_returns_200(self, client, mock_store):
        resp = client.get("/session")
        assert resp.status_code == 200

    def test_list_sessions_returns_list(self, client, mock_store):
        data = client.get("/session").json()
        assert isinstance(data, list)

    def test_list_sessions_empty(self, client, empty_store):
        data = client.get("/session").json()
        assert data == []


# ---------------------------------------------------------------------------
# POST /session
# ---------------------------------------------------------------------------

class TestCreateSession:
    def test_create_session_returns_200(self, client):
        resp = client.post("/session", json={})
        assert resp.status_code == 200

    def test_create_session_has_id(self, client):
        data = client.post("/session", json={}).json()
        assert "id" in data

    def test_create_session_has_projectID(self, client):
        data = client.post("/session", json={}).json()
        assert "projectID" in data

    def test_create_session_with_title(self, client):
        data = client.post("/session", json={"title": "My session"}).json()
        assert data.get("title") == "My session"

    def test_create_session_has_time(self, client):
        data = client.post("/session", json={}).json()
        assert "time" in data
        assert "created" in data["time"]


# ---------------------------------------------------------------------------
# GET /session/{session_id}
# ---------------------------------------------------------------------------

class TestGetSession:
    def test_get_existing_session_returns_200(self, client, mock_store):
        resp = client.get("/session/ses_abc123")
        assert resp.status_code == 200

    def test_get_session_has_id(self, client, mock_store):
        data = client.get("/session/ses_abc123").json()
        assert data.get("id") == "ses_abc123"

    def test_get_nonexistent_session_returns_404(self, client, empty_store):
        resp = client.get("/session/ghost")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /session/{session_id}
# ---------------------------------------------------------------------------

class TestDeleteSession:
    def test_delete_session_returns_200(self, client, mock_store):
        resp = client.delete("/session/ses_abc123")
        assert resp.status_code == 200

    def test_delete_session_returns_ok(self, client, mock_store):
        data = client.delete("/session/ses_abc123").json()
        assert data.get("ok") is True


# ---------------------------------------------------------------------------
# GET /session/{session_id}/message
# ---------------------------------------------------------------------------

class TestListMessages:
    def test_list_messages_returns_200(self, client, mock_store):
        resp = client.get("/session/ses_abc123/message")
        assert resp.status_code == 200

    def test_list_messages_returns_list(self, client, mock_store):
        data = client.get("/session/ses_abc123/message").json()
        assert isinstance(data, list)

    def test_list_messages_count(self, client, mock_store):
        data = client.get("/session/ses_abc123/message").json()
        assert len(data) == 2

    def test_messages_have_role(self, client, mock_store):
        data = client.get("/session/ses_abc123/message").json()
        for m in data:
            assert "role" in m

    def test_messages_have_parts(self, client, mock_store):
        data = client.get("/session/ses_abc123/message").json()
        for m in data:
            assert "parts" in m

    def test_messages_empty_session(self, client, empty_store):
        data = client.get("/session/ghost/message").json()
        assert data == []


# ---------------------------------------------------------------------------
# POST /session/{session_id}/message (SSE)
# ---------------------------------------------------------------------------

class TestSendMessage:
    def test_send_message_no_text_returns_400(self, client):
        resp = client.post("/session/ses_abc123/message", json={"parts": []})
        assert resp.status_code == 400

    def test_send_message_returns_event_stream(self, client, mock_store):
        async def _fake_stream(*a, **kw):
            yield {"type": "text", "text": "Hello"}
            yield {"type": "done"}

        with patch("icecode.agent.core.ICECodeAgent") as MockAgent:
            instance = MagicMock()
            instance.run_stream = _fake_stream
            MockAgent.return_value = instance
            resp = client.post("/session/ses_abc123/message", json={
                "parts": [{"type": "text", "text": "Hi"}]
            })
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_send_message_body_contains_done(self, client, mock_store):
        async def _fake_stream(*a, **kw):
            yield {"type": "done"}

        with patch("icecode.agent.core.ICECodeAgent") as MockAgent:
            instance = MagicMock()
            instance.run_stream = _fake_stream
            MockAgent.return_value = instance
            resp = client.post("/session/ses_abc123/message", json={
                "parts": [{"type": "text", "text": "Hi"}]
            })
        assert "[DONE]" in resp.text


# ---------------------------------------------------------------------------
# POST /session/{session_id}/abort
# ---------------------------------------------------------------------------

class TestAbortSession:
    def test_abort_returns_200(self, client):
        resp = client.post("/session/ses_abc123/abort")
        assert resp.status_code == 200

    def test_abort_returns_ok(self, client):
        data = client.post("/session/ses_abc123/abort").json()
        assert data.get("ok") is True


# ---------------------------------------------------------------------------
# GET /provider
# ---------------------------------------------------------------------------

class TestListProviders:
    def test_list_providers_returns_200(self, client):
        resp = client.get("/provider")
        assert resp.status_code == 200

    def test_list_providers_returns_list(self, client):
        data = client.get("/provider").json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_each_provider_has_id(self, client):
        data = client.get("/provider").json()
        for p in data:
            assert "id" in p

    def test_each_provider_has_models(self, client):
        data = client.get("/provider").json()
        for p in data:
            assert "models" in p
            assert isinstance(p["models"], list)

    def test_anthropic_provider_present(self, client):
        data = client.get("/provider").json()
        ids = [p["id"] for p in data]
        assert "anthropic" in ids


# ---------------------------------------------------------------------------
# GET /config
# ---------------------------------------------------------------------------

class TestGetConfig:
    def test_get_config_returns_200(self, client):
        resp = client.get("/config")
        assert resp.status_code == 200

    def test_get_config_has_version(self, client):
        data = client.get("/config").json()
        assert "version" in data

    def test_get_config_has_providers(self, client):
        data = client.get("/config").json()
        assert "providers" in data


# ---------------------------------------------------------------------------
# GET /agent
# ---------------------------------------------------------------------------

class TestListAgents:
    def test_list_agents_returns_200(self, client):
        resp = client.get("/agent")
        assert resp.status_code == 200

    def test_list_agents_returns_list(self, client):
        data = client.get("/agent").json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_agent_has_id(self, client):
        data = client.get("/agent").json()
        assert "id" in data[0]


# ---------------------------------------------------------------------------
# Misc endpoints
# ---------------------------------------------------------------------------

class TestMiscEndpoints:
    def test_log_returns_200(self, client):
        assert client.get("/log").status_code == 200

    def test_find_returns_200(self, client):
        assert client.get("/find").status_code == 200

    def test_find_file_returns_200(self, client):
        assert client.get("/find/file").status_code == 200

    def test_find_symbol_returns_200(self, client):
        assert client.get("/find/symbol").status_code == 200

    def test_project_returns_200(self, client):
        assert client.get("/project").status_code == 200

    def test_project_current_returns_200(self, client):
        assert client.get("/project/current").status_code == 200

    def test_path_returns_200(self, client):
        assert client.get("/path").status_code == 200

    def test_provider_auth_returns_200(self, client):
        assert client.get("/provider/auth").status_code == 200

    def test_config_providers_returns_200(self, client):
        assert client.get("/config/providers").status_code == 200
