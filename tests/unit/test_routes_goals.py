"""Unit tests for icecode_server.routes.goals

Tests goal CRUD, subgoal creation, completion, active-prompt.
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


_EMPTY_GOALS: list = []

_SAMPLE_GOALS = [
    {
        "id": "goal_aaa",
        "text": "Ship the product",
        "priority": "high",
        "completed": False,
        "subgoals": [
            {"id": "sg_001", "text": "Write tests", "completed": False},
            {"id": "sg_002", "text": "Fix CI", "completed": True},
        ],
        "created_at": "2025-01-01T10:00:00",
    },
    {
        "id": "goal_bbb",
        "text": "Reduce latency",
        "priority": "medium",
        "completed": True,
        "completed_at": "2025-01-05T00:00:00",
        "subgoals": [],
        "created_at": "2025-01-02T08:00:00",
    },
]


@pytest.fixture()
def empty_goals():
    store = [deepcopy(_EMPTY_GOALS)]
    with patch("icecode_server.routes.goals._load", return_value=deepcopy(_EMPTY_GOALS)), \
         patch("icecode_server.routes.goals._save", side_effect=lambda d: store.__setitem__(0, d)) as mock_save:
        yield mock_save


@pytest.fixture()
def sample_goals():
    with patch("icecode_server.routes.goals._load", return_value=deepcopy(_SAMPLE_GOALS)), \
         patch("icecode_server.routes.goals._save"):
        yield


# ---------------------------------------------------------------------------
# GET /api/goals/
# ---------------------------------------------------------------------------

class TestListGoals:
    def test_list_goals_returns_200(self, client, sample_goals):
        resp = client.get("/api/goals/")
        assert resp.status_code == 200

    def test_list_goals_returns_list(self, client, sample_goals):
        data = client.get("/api/goals/").json()
        assert isinstance(data, list)

    def test_list_goals_count(self, client, sample_goals):
        data = client.get("/api/goals/").json()
        assert len(data) == 2

    def test_list_empty_returns_empty(self, client, empty_goals):
        data = client.get("/api/goals/").json()
        assert data == []


# ---------------------------------------------------------------------------
# GET /api/goals/active-prompt
# ---------------------------------------------------------------------------

class TestActivePrompt:
    def test_active_prompt_returns_200(self, client, sample_goals):
        resp = client.get("/api/goals/active-prompt")
        assert resp.status_code == 200

    def test_active_prompt_has_prompt_key(self, client, sample_goals):
        data = client.get("/api/goals/active-prompt").json()
        assert "prompt" in data

    def test_active_prompt_contains_active_goal_text(self, client, sample_goals):
        data = client.get("/api/goals/active-prompt").json()
        assert "Ship the product" in data["prompt"]

    def test_active_prompt_excludes_completed_goals(self, client, sample_goals):
        data = client.get("/api/goals/active-prompt").json()
        assert "Reduce latency" not in data["prompt"]

    def test_active_prompt_empty_returns_empty_string(self, client, empty_goals):
        data = client.get("/api/goals/active-prompt").json()
        assert data["prompt"] == ""


# ---------------------------------------------------------------------------
# POST /api/goals/
# ---------------------------------------------------------------------------

class TestCreateGoal:
    def test_create_goal_returns_200(self, client, empty_goals):
        resp = client.post("/api/goals/", json={"text": "New goal"})
        assert resp.status_code == 200

    def test_create_goal_has_id(self, client, empty_goals):
        data = client.post("/api/goals/", json={"text": "Test"}).json()
        assert "id" in data
        assert data["id"].startswith("goal_")

    def test_create_goal_not_completed(self, client, empty_goals):
        data = client.post("/api/goals/", json={"text": "Active goal"}).json()
        assert data["completed"] is False

    def test_create_goal_with_subgoals(self, client, empty_goals):
        data = client.post("/api/goals/", json={
            "text": "Build feature",
            "subgoals": ["Step 1", "Step 2"],
        }).json()
        assert len(data["subgoals"]) == 2

    def test_create_goal_calls_save(self, client, empty_goals):
        client.post("/api/goals/", json={"text": "Trigger save"})
        empty_goals.assert_called()


# ---------------------------------------------------------------------------
# POST /api/goals/{goal_id}/subgoal
# ---------------------------------------------------------------------------

class TestAddSubgoal:
    def test_add_subgoal_returns_200(self, client, sample_goals):
        resp = client.post("/api/goals/goal_aaa/subgoal", json={"text": "New step"})
        assert resp.status_code == 200

    def test_add_subgoal_appended(self, client, sample_goals):
        data = client.post("/api/goals/goal_aaa/subgoal", json={"text": "Extra"}).json()
        texts = [s["text"] for s in data["subgoals"]]
        assert "Extra" in texts

    def test_add_subgoal_nonexistent_goal_returns_404(self, client, sample_goals):
        resp = client.post("/api/goals/ghost/subgoal", json={"text": "X"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/goals/{goal_id}/complete
# ---------------------------------------------------------------------------

class TestCompleteGoal:
    def test_complete_goal_returns_200(self, client, sample_goals):
        resp = client.post("/api/goals/goal_aaa/complete")
        assert resp.status_code == 200

    def test_complete_sets_completed_true(self, client, sample_goals):
        data = client.post("/api/goals/goal_aaa/complete").json()
        assert data["completed"] is True

    def test_complete_adds_completed_at(self, client, sample_goals):
        data = client.post("/api/goals/goal_aaa/complete").json()
        assert "completed_at" in data

    def test_complete_nonexistent_returns_404(self, client, sample_goals):
        resp = client.post("/api/goals/ghost/complete")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/goals/{goal_id}
# ---------------------------------------------------------------------------

class TestDeleteGoal:
    def test_delete_goal_returns_200(self, client, sample_goals):
        resp = client.delete("/api/goals/goal_aaa")
        assert resp.status_code == 200

    def test_delete_returns_ok(self, client, sample_goals):
        data = client.delete("/api/goals/goal_bbb").json()
        assert data.get("ok") is True

    def test_delete_nonexistent_still_ok(self, client, sample_goals):
        # Delete is idempotent — filtering a non-existent id just returns same list
        resp = client.delete("/api/goals/ghost")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# DELETE /api/goals/ (clear completed)
# ---------------------------------------------------------------------------

class TestClearCompleted:
    def test_clear_completed_returns_200(self, client, sample_goals):
        resp = client.delete("/api/goals/")
        assert resp.status_code == 200

    def test_clear_completed_returns_ok(self, client, sample_goals):
        data = client.delete("/api/goals/").json()
        assert data.get("ok") is True

    def test_clear_completed_remaining_count(self, client, sample_goals):
        data = client.delete("/api/goals/").json()
        # 1 active goal remains (goal_bbb is completed)
        assert data["remaining"] == 1
