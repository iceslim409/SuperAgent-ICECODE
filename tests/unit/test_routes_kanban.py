"""Unit tests for icecode_server.routes.kanban

Tests boards, tasks CRUD, stats.
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


_EMPTY_DATA = {"boards": {"default": {"tasks": []}}}

_SAMPLE_DATA = {
    "boards": {
        "default": {
            "tasks": [
                {
                    "id": "task_aaa",
                    "title": "Write tests",
                    "description": "Add unit tests",
                    "status": "in_progress",
                    "priority": "high",
                    "agent_id": None,
                    "board": "default",
                    "tags": ["testing"],
                    "due_date": None,
                    "created_at": "2025-01-01T10:00:00",
                    "updated_at": "2025-01-01T10:00:00",
                },
                {
                    "id": "task_bbb",
                    "title": "Fix bug",
                    "description": "",
                    "status": "todo",
                    "priority": "urgent",
                    "agent_id": "agent-1",
                    "board": "default",
                    "tags": [],
                    "due_date": "2025-02-01",
                    "created_at": "2025-01-02T09:00:00",
                    "updated_at": "2025-01-02T09:00:00",
                },
            ]
        },
        "backend": {"tasks": []},
    }
}


@pytest.fixture()
def empty_data():
    store = [deepcopy(_EMPTY_DATA)]
    with patch("icecode_server.routes.kanban._load", return_value=deepcopy(_EMPTY_DATA)), \
         patch("icecode_server.routes.kanban._save", side_effect=lambda d: store.__setitem__(0, d)) as mock_save:
        yield mock_save


@pytest.fixture()
def sample_data():
    with patch("icecode_server.routes.kanban._load", return_value=deepcopy(_SAMPLE_DATA)), \
         patch("icecode_server.routes.kanban._save"):
        yield


# ---------------------------------------------------------------------------
# GET /api/kanban/boards
# ---------------------------------------------------------------------------

class TestListBoards:
    def test_list_boards_returns_200(self, client, sample_data):
        resp = client.get("/api/kanban/boards")
        assert resp.status_code == 200

    def test_list_boards_returns_list(self, client, sample_data):
        data = client.get("/api/kanban/boards").json()
        assert isinstance(data, list)

    def test_list_boards_count(self, client, sample_data):
        data = client.get("/api/kanban/boards").json()
        assert len(data) == 2

    def test_each_board_has_name(self, client, sample_data):
        data = client.get("/api/kanban/boards").json()
        for b in data:
            assert "name" in b

    def test_board_task_count(self, client, sample_data):
        data = client.get("/api/kanban/boards").json()
        default = next(b for b in data if b["name"] == "default")
        assert default["task_count"] == 2

    def test_empty_board_returns_empty_list(self, client, empty_data):
        data = client.get("/api/kanban/boards").json()
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# GET /api/kanban/tasks
# ---------------------------------------------------------------------------

class TestListTasks:
    def test_list_tasks_returns_200(self, client, sample_data):
        resp = client.get("/api/kanban/tasks")
        assert resp.status_code == 200

    def test_list_tasks_returns_all(self, client, sample_data):
        data = client.get("/api/kanban/tasks").json()
        assert len(data) == 2

    def test_list_tasks_filter_by_status(self, client, sample_data):
        data = client.get("/api/kanban/tasks?status=todo").json()
        assert len(data) == 1
        assert data[0]["status"] == "todo"

    def test_list_tasks_empty_board_other(self, client, sample_data):
        data = client.get("/api/kanban/tasks?board=backend").json()
        assert data == []

    def test_list_tasks_sorted_by_priority(self, client, sample_data):
        data = client.get("/api/kanban/tasks").json()
        # urgent (0) should come before high (1)
        priorities = [t["priority"] for t in data]
        assert priorities[0] == "urgent"


# ---------------------------------------------------------------------------
# POST /api/kanban/tasks
# ---------------------------------------------------------------------------

class TestCreateTask:
    def test_create_task_returns_200(self, client, empty_data):
        resp = client.post("/api/kanban/tasks", json={"title": "New task"})
        assert resp.status_code == 200

    def test_create_task_has_id(self, client, empty_data):
        data = client.post("/api/kanban/tasks", json={"title": "Task X"}).json()
        assert "id" in data
        assert data["id"].startswith("task_")

    def test_create_task_defaults(self, client, empty_data):
        data = client.post("/api/kanban/tasks", json={"title": "Defaults"}).json()
        assert data["status"] == "todo"
        assert data["priority"] == "medium"

    def test_create_task_invalid_status_returns_400(self, client, empty_data):
        resp = client.post("/api/kanban/tasks", json={"title": "T", "status": "invalid"})
        assert resp.status_code == 400

    def test_create_task_invalid_priority_returns_400(self, client, empty_data):
        resp = client.post("/api/kanban/tasks", json={"title": "T", "priority": "critical"})
        assert resp.status_code == 400

    def test_create_task_calls_save(self, client, empty_data):
        client.post("/api/kanban/tasks", json={"title": "Save test"})
        empty_data.assert_called()


# ---------------------------------------------------------------------------
# GET /api/kanban/tasks/{task_id}
# ---------------------------------------------------------------------------

class TestGetTask:
    def test_get_existing_task_returns_200(self, client, sample_data):
        resp = client.get("/api/kanban/tasks/task_aaa")
        assert resp.status_code == 200

    def test_get_task_returns_correct_title(self, client, sample_data):
        data = client.get("/api/kanban/tasks/task_aaa").json()
        assert data["title"] == "Write tests"

    def test_get_nonexistent_task_returns_404(self, client, sample_data):
        resp = client.get("/api/kanban/tasks/does-not-exist")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/kanban/tasks/{task_id}
# ---------------------------------------------------------------------------

class TestUpdateTask:
    def test_update_task_returns_200(self, client, sample_data):
        resp = client.patch("/api/kanban/tasks/task_aaa", json={"status": "done"})
        assert resp.status_code == 200

    def test_update_task_status_changes(self, client, sample_data):
        data = client.patch("/api/kanban/tasks/task_aaa", json={"status": "done"}).json()
        assert data["status"] == "done"

    def test_update_nonexistent_task_returns_404(self, client, sample_data):
        resp = client.patch("/api/kanban/tasks/ghost", json={"title": "X"})
        assert resp.status_code == 404

    def test_update_invalid_status_returns_400(self, client, sample_data):
        resp = client.patch("/api/kanban/tasks/task_aaa", json={"status": "invalid"})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /api/kanban/tasks/{task_id}
# ---------------------------------------------------------------------------

class TestDeleteTask:
    def test_delete_existing_task_returns_200(self, client, sample_data):
        resp = client.delete("/api/kanban/tasks/task_aaa")
        assert resp.status_code == 200

    def test_delete_returns_ok(self, client, sample_data):
        data = client.delete("/api/kanban/tasks/task_aaa").json()
        assert data.get("ok") is True

    def test_delete_nonexistent_returns_404(self, client, sample_data):
        resp = client.delete("/api/kanban/tasks/ghost")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/kanban/stats
# ---------------------------------------------------------------------------

class TestKanbanStats:
    def test_stats_returns_200(self, client, sample_data):
        resp = client.get("/api/kanban/stats")
        assert resp.status_code == 200

    def test_stats_has_total(self, client, sample_data):
        data = client.get("/api/kanban/stats").json()
        assert "total" in data
        assert data["total"] == 2

    def test_stats_has_by_status(self, client, sample_data):
        data = client.get("/api/kanban/stats").json()
        assert "by_status" in data
        assert isinstance(data["by_status"], dict)

    def test_stats_has_by_priority(self, client, sample_data):
        data = client.get("/api/kanban/stats").json()
        assert "by_priority" in data

    def test_stats_board_count(self, client, sample_data):
        data = client.get("/api/kanban/stats").json()
        assert data["boards"] == 2

    def test_stats_empty_returns_zero(self, client, empty_data):
        data = client.get("/api/kanban/stats").json()
        assert data["total"] == 0
