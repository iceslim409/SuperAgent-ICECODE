"""Unit tests for icecode_server.routes.usage

Tests usage recording, retrieval, session log, reset, and cost calculation.
Patches _load/_save so no disk I/O is needed.
"""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parents[2]
for _p in ("packages/core", "packages/server", "packages/tools"):
    sys.path.insert(0, str(ROOT / _p))

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


_EMPTY_USAGE = {
    "total_prompt_tokens": 0,
    "total_completion_tokens": 0,
    "total_tokens": 0,
    "total_cost_usd": 0.0,
    "total_sessions": 0,
    "total_tool_calls": 0,
    "by_model": {},
    "by_day": {},
    "sessions": [],
}

_SAMPLE_USAGE = {
    "total_prompt_tokens": 5000,
    "total_completion_tokens": 2000,
    "total_tokens": 7000,
    "total_cost_usd": 0.05,
    "total_sessions": 3,
    "total_tool_calls": 12,
    "by_model": {
        "gpt-4o-mini": {
            "prompt": 5000, "completion": 2000,
            "total": 7000, "cost": 0.05, "sessions": 3,
        }
    },
    "by_day": {
        "2025-01-01": {"tokens": 7000, "cost": 0.05, "sessions": 3},
    },
    "sessions": [
        {
            "session_id": "s1", "model": "gpt-4o-mini", "provider": "openai",
            "prompt_t": 500, "completion_t": 200, "total_t": 700,
            "tool_calls": 2, "iterations": 3, "cost_usd": 0.001, "elapsed_s": 5.2,
            "at": "2025-01-01T10:00:00",
        },
    ],
}


@pytest.fixture()
def empty_usage():
    store = [deepcopy(_EMPTY_USAGE)]
    with patch("icecode_server.routes.usage._load", return_value=deepcopy(_EMPTY_USAGE)), \
         patch("icecode_server.routes.usage._save", side_effect=lambda d: store.__setitem__(0, d)) as mock_save:
        yield mock_save


@pytest.fixture()
def sample_usage():
    with patch("icecode_server.routes.usage._load", return_value=deepcopy(_SAMPLE_USAGE)), \
         patch("icecode_server.routes.usage._save"):
        yield


# ---------------------------------------------------------------------------
# GET /api/usage/
# ---------------------------------------------------------------------------

class TestGetUsage:
    def test_get_usage_returns_200(self, client, sample_usage):
        resp = client.get("/api/usage/")
        assert resp.status_code == 200

    def test_get_usage_has_total_tokens(self, client, sample_usage):
        data = client.get("/api/usage/").json()
        assert "total_tokens" in data
        assert data["total_tokens"] == 7000

    def test_get_usage_has_total_sessions(self, client, sample_usage):
        data = client.get("/api/usage/").json()
        assert "total_sessions" in data
        assert data["total_sessions"] == 3

    def test_get_usage_has_by_model(self, client, sample_usage):
        data = client.get("/api/usage/").json()
        assert "by_model" in data
        assert isinstance(data["by_model"], dict)

    def test_get_usage_has_today(self, client, sample_usage):
        data = client.get("/api/usage/").json()
        assert "today" in data

    def test_get_usage_has_last_7_days(self, client, sample_usage):
        data = client.get("/api/usage/").json()
        assert "last_7_days" in data
        assert len(data["last_7_days"]) == 7

    def test_get_usage_cost_usd_is_float(self, client, sample_usage):
        data = client.get("/api/usage/").json()
        assert isinstance(data["total_cost_usd"], float)

    def test_get_empty_usage_returns_zeros(self, client, empty_usage):
        data = client.get("/api/usage/").json()
        assert data["total_tokens"] == 0
        assert data["total_sessions"] == 0


# ---------------------------------------------------------------------------
# POST /api/usage/record
# ---------------------------------------------------------------------------

class TestRecordUsage:
    def test_record_returns_200(self, client, empty_usage):
        resp = client.post("/api/usage/record", json={
            "session_id": "test-sess-1",
            "model": "gpt-4o-mini",
            "provider": "openai",
            "prompt_tokens": 100,
            "completion_tokens": 50,
        })
        assert resp.status_code == 200

    def test_record_returns_ok(self, client, empty_usage):
        data = client.post("/api/usage/record", json={
            "session_id": "s",
            "model": "gpt-4o-mini",
            "prompt_tokens": 100,
            "completion_tokens": 50,
        }).json()
        assert data.get("ok") is True

    def test_record_returns_tokens(self, client, empty_usage):
        data = client.post("/api/usage/record", json={
            "session_id": "s",
            "model": "gpt-4o-mini",
            "prompt_tokens": 300,
            "completion_tokens": 100,
        }).json()
        assert data["tokens"] == 400

    def test_record_returns_cost_usd(self, client, empty_usage):
        data = client.post("/api/usage/record", json={
            "session_id": "s",
            "model": "gpt-4o-mini",
            "prompt_tokens": 1_000_000,
            "completion_tokens": 0,
        }).json()
        assert "cost_usd" in data
        assert data["cost_usd"] > 0  # gpt-4o-mini costs money

    def test_record_ollama_model_zero_cost(self, client, empty_usage):
        data = client.post("/api/usage/record", json={
            "session_id": "s",
            "model": "llama3.2",
            "provider": "ollama",
            "prompt_tokens": 10000,
            "completion_tokens": 5000,
        }).json()
        assert data["cost_usd"] == 0.0

    def test_record_calls_save(self, client, empty_usage):
        client.post("/api/usage/record", json={
            "session_id": "s",
            "model": "gpt-4o",
            "prompt_tokens": 50,
            "completion_tokens": 20,
        })
        empty_usage.assert_called()

    def test_record_minimal_fields(self, client, empty_usage):
        resp = client.post("/api/usage/record", json={"session_id": "minimal"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/usage/sessions
# ---------------------------------------------------------------------------

class TestGetSessionUsage:
    def test_sessions_returns_200(self, client, sample_usage):
        resp = client.get("/api/usage/sessions")
        assert resp.status_code == 200

    def test_sessions_has_sessions_key(self, client, sample_usage):
        data = client.get("/api/usage/sessions").json()
        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    def test_sessions_default_limit_50(self, client, sample_usage):
        data = client.get("/api/usage/sessions").json()
        assert len(data["sessions"]) <= 50

    def test_sessions_limit_param(self, client, sample_usage):
        data = client.get("/api/usage/sessions?limit=1").json()
        assert len(data["sessions"]) <= 1

    def test_sessions_have_model_field(self, client, sample_usage):
        data = client.get("/api/usage/sessions").json()
        if data["sessions"]:
            assert "model" in data["sessions"][0]


# ---------------------------------------------------------------------------
# DELETE /api/usage/ (reset)
# ---------------------------------------------------------------------------

class TestResetUsage:
    def test_reset_returns_200(self, client, empty_usage):
        resp = client.delete("/api/usage/")
        assert resp.status_code == 200

    def test_reset_returns_ok(self, client, empty_usage):
        data = client.delete("/api/usage/").json()
        assert data.get("ok") is True

    def test_reset_calls_save_with_zeros(self, client, empty_usage):
        client.delete("/api/usage/")
        saved = empty_usage.call_args[0][0]
        assert saved["total_tokens"] == 0
        assert saved["total_sessions"] == 0
        assert saved["by_model"] == {}


# ---------------------------------------------------------------------------
# Cost calculation
# ---------------------------------------------------------------------------

class TestCostCalculation:
    def test_gpt4o_has_cost(self, client, empty_usage):
        data = client.post("/api/usage/record", json={
            "session_id": "x",
            "model": "gpt-4o",
            "prompt_tokens": 1_000_000,
            "completion_tokens": 1_000_000,
        }).json()
        assert data["cost_usd"] == pytest.approx(12.50, abs=0.01)

    def test_claude_sonnet_has_cost(self, client, empty_usage):
        data = client.post("/api/usage/record", json={
            "session_id": "x",
            "model": "claude-sonnet-4",
            "prompt_tokens": 1_000_000,
            "completion_tokens": 0,
        }).json()
        assert data["cost_usd"] == pytest.approx(3.00, abs=0.01)

    def test_unknown_model_zero_cost(self, client, empty_usage):
        data = client.post("/api/usage/record", json={
            "session_id": "x",
            "model": "some-unknown-local-model",
            "prompt_tokens": 999999,
            "completion_tokens": 999999,
        }).json()
        assert data["cost_usd"] == 0.0
