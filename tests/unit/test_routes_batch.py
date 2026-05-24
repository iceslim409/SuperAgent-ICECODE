"""Unit tests for icecode_server.routes.batch

Tests batch run (SSE) and templates.
Patches _run_item so no real LLM calls are made.
"""
from __future__ import annotations

import json
import sys
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


_FAKE_RESULT = {
    "idx": 0,
    "label": "test.py",
    "text": "No issues found.",
    "elapsed_ms": 42,
    "tokens": 100,
    "error": None,
}


@pytest.fixture()
def mock_run_item():
    async def _fake(*args, **kwargs):
        return {**_FAKE_RESULT, "idx": args[0], "label": args[1]}
    with patch("icecode_server.routes.batch._run_item", side_effect=_fake):
        yield


# ---------------------------------------------------------------------------
# GET /api/batch/templates
# ---------------------------------------------------------------------------

class TestBatchTemplates:
    def test_templates_returns_200(self, client):
        resp = client.get("/api/batch/templates")
        assert resp.status_code == 200

    def test_templates_is_list(self, client):
        data = client.get("/api/batch/templates").json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_each_template_has_id(self, client):
        data = client.get("/api/batch/templates").json()
        for t in data:
            assert "id" in t

    def test_each_template_has_prompt(self, client):
        data = client.get("/api/batch/templates").json()
        for t in data:
            assert "prompt" in t
            assert len(t["prompt"]) > 0

    def test_code_review_template_exists(self, client):
        data = client.get("/api/batch/templates").json()
        ids = [t["id"] for t in data]
        assert "code_review" in ids


# ---------------------------------------------------------------------------
# POST /api/batch/run
# ---------------------------------------------------------------------------

class TestBatchRun:
    def test_run_no_files_no_prompts_still_streams(self, client):
        resp = client.post("/api/batch/run", json={"prompt": "test"})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_run_with_prompts_returns_event_stream(self, client, mock_run_item):
        resp = client.post("/api/batch/run", json={
            "prompt": "ignored",
            "prompts": ["Hello", "World"],
        })
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_run_with_prompts_contains_start_event(self, client, mock_run_item):
        resp = client.post("/api/batch/run", json={
            "prompt": "x",
            "prompts": ["Hello"],
        })
        assert "start" in resp.text

    def test_run_with_prompts_contains_done_event(self, client, mock_run_item):
        resp = client.post("/api/batch/run", json={
            "prompt": "x",
            "prompts": ["Hello"],
        })
        assert "done" in resp.text

    def test_run_with_prompts_item_count_matches(self, client, mock_run_item):
        resp = client.post("/api/batch/run", json={
            "prompt": "x",
            "prompts": ["A", "B", "C"],
        })
        # Should have 3 item_done events
        item_done_count = resp.text.count('"item_done"')
        assert item_done_count == 3

    def test_run_missing_prompt_returns_422(self, client):
        resp = client.post("/api/batch/run", json={})
        assert resp.status_code == 422
