"""Unit tests for icecode_server.routes.sessions

Tests session list, search, get, delete, export.
Patches SessionStore so tests are hermetic.
"""
from __future__ import annotations

import json
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


_SAMPLE_SESSIONS = [
    {
        "session_id": "sess-aaa",
        "title": "Chat about Python",
        "preview": "Tell me about Python generators",
        "created_at": "2025-01-01T10:00:00",
        "updated_at": "2025-01-01T10:05:00",
        "messages": [
            {"role": "user", "content": "Tell me about Python generators"},
            {"role": "assistant", "content": "Generators are lazy iterators."},
        ],
        "metadata": {"model": "llama3.2", "provider": "ollama"},
    },
    {
        "session_id": "sess-bbb",
        "title": "Docker help",
        "preview": "How do I expose a port in Docker?",
        "created_at": "2025-01-02T12:00:00",
        "updated_at": "2025-01-02T12:10:00",
        "messages": [],
        "metadata": {},
    },
]


def _make_store(sessions=None):
    store = MagicMock()
    store.list_sessions.return_value = _SAMPLE_SESSIONS if sessions is None else sessions
    store.load.side_effect = lambda sid: next(
        (s for s in (sessions or _SAMPLE_SESSIONS) if s["session_id"] == sid), None
    )
    store.session_dir = Path("/tmp/fake_sessions")
    return store


@pytest.fixture()
def mock_store():
    store = _make_store()
    with patch("icecode_server.routes.sessions._store", return_value=store):
        yield store


@pytest.fixture()
def empty_store():
    store = _make_store([])
    with patch("icecode_server.routes.sessions._store", return_value=store):
        yield store


# ---------------------------------------------------------------------------
# GET /api/sessions/
# ---------------------------------------------------------------------------

class TestListSessions:
    def test_list_returns_200(self, client, mock_store):
        resp = client.get("/api/sessions/")
        assert resp.status_code == 200

    def test_list_returns_list(self, client, mock_store):
        data = client.get("/api/sessions/").json()
        assert isinstance(data, list)

    def test_list_returns_all_sessions(self, client, mock_store):
        data = client.get("/api/sessions/").json()
        assert len(data) == 2

    def test_list_sessions_have_session_id(self, client, mock_store):
        data = client.get("/api/sessions/").json()
        for s in data:
            assert "session_id" in s

    def test_list_empty_returns_empty_list(self, client, empty_store):
        data = client.get("/api/sessions/").json()
        assert data == []

    def test_list_returns_200_on_store_error(self, client):
        broken = MagicMock()
        broken.list_sessions.side_effect = RuntimeError("disk full")
        with patch("icecode_server.routes.sessions._store", return_value=broken):
            resp = client.get("/api/sessions/")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/sessions/search
# ---------------------------------------------------------------------------

class TestSearchSessions:
    def test_search_no_query_returns_all(self, client, mock_store):
        data = client.get("/api/sessions/search").json()
        assert len(data) == 2

    def test_search_by_title(self, client, mock_store):
        data = client.get("/api/sessions/search?q=Python").json()
        assert len(data) == 1
        assert data[0]["session_id"] == "sess-aaa"

    def test_search_by_preview(self, client, mock_store):
        data = client.get("/api/sessions/search?q=Docker").json()
        assert len(data) == 1
        assert data[0]["session_id"] == "sess-bbb"

    def test_search_case_insensitive(self, client, mock_store):
        data = client.get("/api/sessions/search?q=python").json()
        assert len(data) == 1

    def test_search_no_match_returns_empty(self, client, mock_store):
        data = client.get("/api/sessions/search?q=kubernetes").json()
        assert data == []


# ---------------------------------------------------------------------------
# GET /api/sessions/{session_id}
# ---------------------------------------------------------------------------

class TestGetSession:
    def test_get_existing_session_returns_200(self, client, mock_store):
        resp = client.get("/api/sessions/sess-aaa")
        assert resp.status_code == 200

    def test_get_session_returns_messages(self, client, mock_store):
        data = client.get("/api/sessions/sess-aaa").json()
        assert "messages" in data
        assert len(data["messages"]) == 2

    def test_get_session_returns_metadata(self, client, mock_store):
        data = client.get("/api/sessions/sess-aaa").json()
        assert data.get("session_id") == "sess-aaa"
        assert data.get("title") == "Chat about Python"

    def test_get_nonexistent_session_returns_404(self, client, mock_store):
        resp = client.get("/api/sessions/does-not-exist")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/sessions/{session_id}
# ---------------------------------------------------------------------------

class TestDeleteSession:
    def test_delete_nonexistent_returns_ok(self, client, mock_store, tmp_path):
        mock_store.session_dir = tmp_path
        resp = client.delete("/api/sessions/ghost-session")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_delete_existing_removes_file(self, client, mock_store, tmp_path):
        mock_store.session_dir = tmp_path
        fake_file = tmp_path / "sess-del.json"
        fake_file.write_text("{}")
        resp = client.delete("/api/sessions/sess-del")
        assert resp.status_code == 200
        assert not fake_file.exists()


# ---------------------------------------------------------------------------
# GET /api/sessions/{session_id}/export
# ---------------------------------------------------------------------------

class TestExportSession:
    def test_export_json_returns_200(self, client, mock_store):
        resp = client.get("/api/sessions/sess-aaa/export?format=json")
        assert resp.status_code == 200

    def test_export_json_content_type(self, client, mock_store):
        resp = client.get("/api/sessions/sess-aaa/export?format=json")
        assert "application/json" in resp.headers.get("content-type", "")

    def test_export_json_has_session_id(self, client, mock_store):
        resp = client.get("/api/sessions/sess-aaa/export?format=json")
        data = json.loads(resp.content)
        assert data.get("session_id") == "sess-aaa"

    def test_export_markdown_returns_200(self, client, mock_store):
        resp = client.get("/api/sessions/sess-aaa/export?format=markdown")
        assert resp.status_code == 200

    def test_export_markdown_content_type(self, client, mock_store):
        resp = client.get("/api/sessions/sess-aaa/export?format=markdown")
        assert "text/markdown" in resp.headers.get("content-type", "")

    def test_export_markdown_contains_title(self, client, mock_store):
        resp = client.get("/api/sessions/sess-aaa/export?format=markdown")
        assert "Chat about Python" in resp.text

    def test_export_nonexistent_returns_404(self, client, mock_store):
        resp = client.get("/api/sessions/ghost/export")
        assert resp.status_code == 404
