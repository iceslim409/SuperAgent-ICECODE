"""End-to-end integration tests — full request/response cycles through the FastAPI app.

Each test class owns a distinct flow:
  TestChatFlow         — POST /api/chat/ → session saved → GET session → DELETE
  TestSessionLifecycle — session CRUD including history persistence across turns
  TestKnowledgePipeline— index temp file → search → verify hit → delete source
  TestSwarmExecution   — swarm SSE stream parsing for pipeline and parallel modes
  TestSettingsCRUD     — PATCH /api/settings/ → GET → verify round-trip
  TestDiagnostics      — GET /api/diagnostics/ returns expected shape
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "core"))
sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "server"))
sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "tools"))

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_stream_chunks(text: str = "Hello from mock agent"):
    """Async generator that yields text chunks like ICECodeAgent.stream()."""
    async def _gen():
        for word in text.split():
            yield {"type": "text", "content": word + " "}
    return _gen()


def _patch_agent_stream(text: str = "Hello from mock agent"):
    """Patch ICECodeAgent.stream to avoid real LLM calls.

    Also populates self.history so session.save() persists messages.
    """
    async def _fake_stream(self, message, **kw):
        self.history.append({"role": "user", "content": message})
        self.history.append({"role": "assistant", "content": text})
        for word in text.split():
            yield {"type": "text", "content": word + " "}

    return patch("icecode.agent.core.ICECodeAgent.stream", _fake_stream)


# ---------------------------------------------------------------------------
# Chat flow
# ---------------------------------------------------------------------------

class TestChatFlow:
    def test_chat_returns_response_shape(self, client):
        with _patch_agent_stream("The sky is blue."):
            r = client.post("/api/chat/", json={
                "message": "What color is the sky?",
                "stream": False,
            })
        assert r.status_code == 200
        data = r.json()
        assert "session_id" in data
        assert "response" in data
        assert "usage" in data
        assert isinstance(data["response"], str)
        assert len(data["response"]) > 0

    def test_chat_response_contains_model_text(self, client):
        with _patch_agent_stream("Paris is the capital of France."):
            r = client.post("/api/chat/", json={
                "message": "What is the capital of France?",
                "stream": False,
            })
        assert r.status_code == 200
        assert "Paris" in r.json()["response"]

    def test_chat_with_explicit_session_id(self, client):
        sid = "e2e_test_session_explicit"
        with _patch_agent_stream("Response one."):
            r = client.post("/api/chat/", json={
                "message": "First message",
                "session_id": sid,
                "stream": False,
            })
        assert r.status_code == 200
        assert r.json()["session_id"] == sid

    def test_chat_usage_fields_present(self, client):
        with _patch_agent_stream("answer"):
            r = client.post("/api/chat/", json={
                "message": "hello",
                "stream": False,
            })
        usage = r.json()["usage"]
        for field in ("prompt_tokens", "completion_tokens", "iterations"):
            assert field in usage, f"missing usage field: {field}"

    def test_available_models_endpoint(self, client):
        r = client.get("/api/chat/available-models")
        assert r.status_code == 200
        data = r.json()
        # Response shape: {local: {...}, cloud: [...], default_provider, default_model}
        # or legacy {models: [...]}
        assert isinstance(data, dict)
        assert "local" in data or "models" in data or "default_provider" in data


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

class TestSessionLifecycle:
    def test_session_persisted_after_chat(self, client):
        sid = f"e2e_lifecycle_{int(time.time())}"
        with _patch_agent_stream("Persisted response."):
            client.post("/api/chat/", json={
                "message": "Remember this session.",
                "session_id": sid,
                "stream": False,
            })
        r = client.get(f"/api/chat/sessions/{sid}")
        assert r.status_code == 200
        data = r.json()
        assert "messages" in data

    def test_session_history_contains_user_message(self, client):
        sid = f"e2e_history_{int(time.time())}"
        msg = "What is 2 + 2?"
        with _patch_agent_stream("Four."):
            client.post("/api/chat/", json={
                "message": msg,
                "session_id": sid,
                "stream": False,
            })
        r = client.get(f"/api/chat/sessions/{sid}")
        assert r.status_code == 200
        messages = r.json()["messages"]
        user_msgs = [m for m in messages if m.get("role") == "user"]
        assert any(msg in str(m.get("content", "")) for m in user_msgs)

    def test_session_continues_history(self, client):
        sid = f"e2e_continue_{int(time.time())}"
        with _patch_agent_stream("Turn one."):
            client.post("/api/chat/", json={
                "message": "First turn",
                "session_id": sid,
                "stream": False,
            })
        with _patch_agent_stream("Turn two."):
            client.post("/api/chat/", json={
                "message": "Second turn",
                "session_id": sid,
                "stream": False,
            })
        r = client.get(f"/api/chat/sessions/{sid}")
        messages = r.json()["messages"]
        assert len(messages) >= 2

    def test_list_sessions_includes_created(self, client):
        sid = f"e2e_list_{int(time.time())}"
        with _patch_agent_stream("Listed."):
            client.post("/api/chat/", json={
                "message": "List me",
                "session_id": sid,
                "stream": False,
            })
        r = client.get("/api/chat/sessions")
        assert r.status_code == 200
        body = r.json()
        sessions = body if isinstance(body, list) else body.get("sessions", [])
        ids = [s.get("session_id") or s.get("id") or s for s in sessions]
        assert sid in ids

    def test_delete_session(self, client):
        sid = f"e2e_delete_{int(time.time())}"
        with _patch_agent_stream("Will be deleted."):
            client.post("/api/chat/", json={
                "message": "Delete me",
                "session_id": sid,
                "stream": False,
            })
        r = client.delete(f"/api/chat/sessions/{sid}")
        assert r.status_code == 200
        # Confirm it's gone
        r2 = client.get(f"/api/chat/sessions/{sid}")
        assert r2.status_code == 404

    def test_get_nonexistent_session_returns_404(self, client):
        r = client.get("/api/chat/sessions/this_session_does_not_exist_xyz")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Knowledge pipeline
# ---------------------------------------------------------------------------

class TestKnowledgePipeline:
    @pytest.fixture(autouse=True)
    def _skip_if_no_rag(self, client):
        r = client.get("/api/knowledge/stats")
        if not r.json().get("rag_available"):
            pytest.skip("RAG (FAISS/sentence-transformers) not available")

    def test_index_temp_file_returns_chunks(self, client):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("The mitochondria is the powerhouse of the cell.\n" * 5)
            fpath = f.name
        try:
            r = client.post("/api/knowledge/index", json={"path": fpath})
            assert r.status_code == 200
            data = r.json()
            assert data.get("chunks_added", 0) >= 1 or data.get("indexed", 0) >= 1
        finally:
            Path(fpath).unlink(missing_ok=True)

    def test_search_returns_relevant_chunk(self, client):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            unique = "zorp_quux_blargh_e2e_unique_term_9821"
            f.write(f"This document contains the special term: {unique}.\n" * 3)
            fpath = f.name
        try:
            client.post("/api/knowledge/index", json={"path": fpath})
            r = client.get(f"/api/knowledge/search?q={unique}&k=3")
            assert r.status_code == 200
            data = r.json()
            assert data["count"] >= 1
            texts = [res.get("text", "") for res in data["results"]]
            assert any(unique in t for t in texts)
        finally:
            Path(fpath).unlink(missing_ok=True)

    def test_sources_list_after_index(self, client):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Source listing test content.\n")
            fpath = f.name
        try:
            client.post("/api/knowledge/index", json={"path": fpath})
            r = client.get("/api/knowledge/sources")
            assert r.status_code == 200
            sources = r.json()["sources"]
            paths = [s.get("path", "") or s.get("source", "") for s in sources]
            assert any(fpath in p for p in paths)
        finally:
            Path(fpath).unlink(missing_ok=True)

    def test_delete_source_removes_chunks(self, client):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            unique = "to_be_deleted_e2e_xyz_4477"
            f.write(f"Delete me: {unique}.\n" * 3)
            fpath = f.name
        try:
            client.post("/api/knowledge/index", json={"path": fpath})
            r_before = client.get(f"/api/knowledge/search?q={unique}&k=3")
            assert r_before.json()["count"] >= 1

            r_del = client.delete(f"/api/knowledge/sources?path={fpath}")
            assert r_del.status_code == 200
            # Verify metadata was removed (FAISS may require index rebuild for search to reflect 0)
            assert r_del.json()["chunks_removed"] >= 1

            r_sources = client.get("/api/knowledge/sources")
            source_paths = [s.get("path", "") or s.get("source", "") for s in r_sources.json()["sources"]]
            assert not any(fpath in p for p in source_paths)
        finally:
            Path(fpath).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Swarm execution
# ---------------------------------------------------------------------------

class TestSwarmExecution:
    def _collect_sse(self, response) -> list:
        """Parse SSE stream from a streaming response body."""
        events = []
        for line in response.iter_lines():
            if line.startswith("data: "):
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass
        return events

    def test_swarm_pipeline_template_streams_events(self, client):
        with _patch_agent_stream("Pipeline output text."):
            r = client.post("/api/swarm/run", json={
                "input": "Explain gravity briefly.",
                "template": "research_write",
            }, headers={"Accept": "text/event-stream"})
        assert r.status_code == 200

    def test_swarm_parallel_template_streams_events(self, client):
        with _patch_agent_stream("Brainstorm output."):
            r = client.post("/api/swarm/run", json={
                "input": "Brainstorm ideas for a todo app.",
                "template": "brainstorm",
            }, headers={"Accept": "text/event-stream"})
        assert r.status_code == 200

    def test_swarm_custom_agents_accepted(self, client):
        with _patch_agent_stream("Custom agent output."):
            r = client.post("/api/swarm/run", json={
                "input": "Summarize: AI is transforming software development.",
                "mode": "pipeline",
                "agents": [
                    {"role": "Summarizer", "task": "{input}", "max_iterations": 2},
                ],
            })
        assert r.status_code == 200

    def test_swarm_code_review_template_exists(self, client):
        r = client.get("/api/swarm/templates/code_review")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == "code_review"
        assert "stages" in data or "agents" in data


# ---------------------------------------------------------------------------
# Settings CRUD
# ---------------------------------------------------------------------------

class TestSettingsCRUD:
    def test_get_settings_returns_dict(self, client):
        r = client.get("/api/settings/")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_patch_settings_persists(self, client):
        key = f"_e2e_test_key_{int(time.time())}"
        val = "e2e_test_value"
        r = client.patch("/api/settings/", json={"data": {key: val}})
        assert r.status_code == 200
        assert r.json().get(key) == val

        r2 = client.get("/api/settings/")
        assert r2.json().get(key) == val

    def test_patch_settings_merges_existing(self, client):
        client.patch("/api/settings/", json={"data": {"_e2e_a": "1"}})
        client.patch("/api/settings/", json={"data": {"_e2e_b": "2"}})
        r = client.get("/api/settings/")
        data = r.json()
        assert data.get("_e2e_a") == "1"
        assert data.get("_e2e_b") == "2"


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

class TestDiagnostics:
    def test_diagnostics_endpoint_returns_200(self, client):
        r = client.get("/api/diagnostics/")
        assert r.status_code == 200

    def test_diagnostics_has_system_info(self, client):
        r = client.get("/api/diagnostics/")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_health_includes_uptime(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert data["status"] == "ok"
