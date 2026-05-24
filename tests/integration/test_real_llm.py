"""Real LLM integration tests — only run when a live endpoint is reachable.

These tests use an actual language model (Ollama by default) and make real HTTP
calls to the ICECODE server started in-process.  They are skipped automatically
when Ollama is not running, so CI stays green without a GPU.

Run manually:
    pytest tests/integration/test_real_llm.py -v -s

To target a different endpoint set env vars before running:
    ICECODE_TEST_BASE_URL=http://localhost:11434/v1  ICECODE_TEST_MODEL=llama3.2  pytest ...

To enable knowledge tests, pull the embedding model first:
    ollama pull nomic-embed-text
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).parents[2]
for _p in ("packages/core", "packages/server", "packages/tools"):
    _pp = str(ROOT / _p)
    if _pp not in sys.path:
        sys.path.insert(0, _pp)

# ---------------------------------------------------------------------------
# Skip guards
# ---------------------------------------------------------------------------

OLLAMA_BASE = os.environ.get("ICECODE_TEST_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.environ.get("ICECODE_TEST_MODEL", "llama3.2")
EMBED_MODEL = os.environ.get("ICECODE_EMBED_MODEL", "nomic-embed-text")


def _ollama_available() -> bool:
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _embed_model_available() -> bool:
    """Check if the Ollama embedding model is pulled."""
    try:
        r = httpx.post(
            "http://localhost:11434/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": "test"},
            timeout=5,
        )
        return r.status_code == 200
    except Exception:
        return False


requires_ollama = pytest.mark.skipif(
    not _ollama_available(),
    reason="Ollama not running — start with `ollama serve` to enable real LLM tests",
)

requires_embed = pytest.mark.skipif(
    not _embed_model_available(),
    reason=f"Embedding model '{EMBED_MODEL}' not pulled — run: ollama pull {EMBED_MODEL}",
)


@pytest.fixture(scope="module")
def live_client():
    """FastAPI TestClient wired to use Ollama as the LLM provider."""
    os.environ.setdefault("DEFAULT_PROVIDER", "ollama")
    os.environ.setdefault("OLLAMA_BASE_URL", OLLAMA_BASE)
    os.environ.setdefault("DEFAULT_MODEL", OLLAMA_MODEL)

    from icecode_server.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


# ---------------------------------------------------------------------------
# Real chat — single turn
# ---------------------------------------------------------------------------

@requires_ollama
class TestRealChat:
    def test_chat_returns_nonempty_text(self, live_client):
        """POST /api/chat/stream with a trivial prompt; expect a non-empty response."""
        resp = live_client.post(
            "/api/chat/stream",
            json={"message": "Reply with exactly the word: PONG", "session_id": None},
        )
        assert resp.status_code == 200
        assert len(resp.text) > 0, "Got empty response from real LLM"

    def test_chat_response_contains_text_event(self, live_client):
        """The SSE stream should contain at least one text/content chunk."""
        resp = live_client.post(
            "/api/chat/stream",
            json={"message": "What is 2+2? Answer with the number only.", "session_id": None},
        )
        assert resp.status_code == 200
        has_content = any(
            '"type": "text"' in line or '"content"' in line
            for line in resp.text.splitlines()
        )
        assert has_content, f"No text chunks in SSE stream. Body: {resp.text[:500]}"

    def test_chat_creates_retrievable_session(self, live_client):
        """A completed chat should be retrievable from GET /api/sessions/."""
        resp = live_client.post(
            "/api/chat/stream",
            json={"message": "Say the word: HELLO", "session_id": None},
        )
        assert resp.status_code == 200

        sessions = live_client.get("/api/sessions/").json()
        assert isinstance(sessions, list)
        assert len(sessions) > 0, (
            "No sessions found after real chat — check that chat route calls "
            "store.save() and sessions route uses get_session_store()"
        )

    def test_session_has_user_message(self, live_client):
        """Session history should contain the user message after chat."""
        resp = live_client.post(
            "/api/chat/stream",
            json={"message": "Unique marker ZXQWERTY_987", "session_id": None},
        )
        assert resp.status_code == 200

        sessions = live_client.get("/api/sessions/").json()
        assert sessions, "No sessions after chat"

        latest = sessions[0]
        session_id = latest["session_id"]
        detail = live_client.get(f"/api/sessions/{session_id}").json()

        messages = detail.get("messages", [])
        user_messages = [m for m in messages if m.get("role") == "user"]
        assert user_messages, f"No user messages in session history: {detail}"


# ---------------------------------------------------------------------------
# Real knowledge base round-trip
# ---------------------------------------------------------------------------

@requires_ollama
@requires_embed
class TestRealKnowledge:
    def test_index_and_search(self, live_client, tmp_path):
        """Index a small text file and verify semantic search returns it."""
        doc = tmp_path / "icecode_test_fact.txt"
        doc.write_text(
            "ICECODE uses FAISS for local vector search. "
            "The embedding model is nomic-embed-text from Ollama."
        )

        idx_resp = live_client.post("/api/knowledge/index", json={"path": str(doc)})
        assert idx_resp.status_code == 200
        data = idx_resp.json()
        assert "error" not in data, f"Index error: {data}"
        chunks = data.get("indexed", data.get("chunks_added", 0))
        assert chunks >= 1, f"No chunks indexed: {data}"

        search_resp = live_client.get(
            "/api/knowledge/search", params={"q": "FAISS vector search", "k": 3}
        )
        assert search_resp.status_code == 200
        body = search_resp.json()
        results = body.get("results", body) if isinstance(body, dict) else body
        assert len(results) >= 1, f"Search returned no results after indexing: {body}"

        texts = [
            r.get("text", r) if isinstance(r, dict) else str(r)
            for r in results
        ]
        assert any("FAISS" in t or "vector" in t or "nomic" in t for t in texts), (
            f"Expected relevant chunk in results, got: {texts}"
        )


# ---------------------------------------------------------------------------
# Real swarm — pipeline mode
# ---------------------------------------------------------------------------

@requires_ollama
class TestRealSwarm:
    def test_pipeline_swarm_streams(self, live_client):
        """POST /api/swarm/run in pipeline mode should return a non-empty response."""
        payload = {
            "mode": "pipeline",
            "input": "Write one sentence about the color blue.",
            "agents": [
                {"role": "writer", "task": "{input}", "model": OLLAMA_MODEL},
                {"role": "reviewer", "task": "Review this: {input}", "model": OLLAMA_MODEL},
            ],
        }
        resp = live_client.post("/api/swarm/run", json=payload)
        assert resp.status_code == 200
        assert len(resp.text) > 0, "Swarm pipeline returned empty body"

    def test_swarm_template_endpoint(self, live_client):
        """GET /api/swarm/templates should return a list of template names."""
        resp = live_client.get("/api/swarm/templates")
        assert resp.status_code == 200
        templates = resp.json()
        assert isinstance(templates, (list, dict)), f"Unexpected templates shape: {templates}"
