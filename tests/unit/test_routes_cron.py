"""Tests for /api/cron routes."""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


_JOBS = [
    {"id": "j1", "name": "Daily Report", "schedule": "0 9 * * *", "command": "summarize today", "enabled": True},
    {"id": "j2", "name": "Cleanup", "schedule": "every 1h", "command": "clean cache", "enabled": False},
]


class TestListJobs:
    def test_returns_200(self, client):
        with patch("icecode_server.routes.cron._load_jobs", return_value=_JOBS):
            r = client.get("/api/cron/")
        assert r.status_code == 200

    def test_returns_list(self, client):
        with patch("icecode_server.routes.cron._load_jobs", return_value=_JOBS):
            data = client.get("/api/cron/").json()
        assert isinstance(data, list)
        assert len(data) == 2


class TestCreateJob:
    def test_returns_200(self, client):
        with patch("icecode_server.routes.cron._load_jobs", return_value=[]), \
             patch("icecode_server.routes.cron._save_jobs"):
            r = client.post("/api/cron/", json={"name": "Job1", "schedule": "daily at 9am", "command": "run task"})
        assert r.status_code == 200

    def test_has_id(self, client):
        with patch("icecode_server.routes.cron._load_jobs", return_value=[]), \
             patch("icecode_server.routes.cron._save_jobs"):
            data = client.post("/api/cron/", json={"name": "Job1", "schedule": "daily at 9am", "command": "task"}).json()
        assert "id" in data

    def test_stores_name(self, client):
        with patch("icecode_server.routes.cron._load_jobs", return_value=[]), \
             patch("icecode_server.routes.cron._save_jobs"):
            data = client.post("/api/cron/", json={"name": "Hourly", "schedule": "every 1h", "command": "ping"}).json()
        assert data.get("name") == "Hourly"

    def test_calls_save(self, client):
        with patch("icecode_server.routes.cron._load_jobs", return_value=[]), \
             patch("icecode_server.routes.cron._save_jobs") as mock_save:
            client.post("/api/cron/", json={"name": "J", "schedule": "daily", "command": "x"})
        mock_save.assert_called_once()


class TestUpdateJob:
    def test_update_returns_200(self, client):
        jobs = [{"id": "j1", "name": "Old", "schedule": "daily", "command": "x", "enabled": True}]
        with patch("icecode_server.routes.cron._load_jobs", return_value=jobs), \
             patch("icecode_server.routes.cron._save_jobs"):
            r = client.put("/api/cron/j1", json={"name": "New"})
        assert r.status_code == 200

    def test_update_nonexistent_404(self, client):
        with patch("icecode_server.routes.cron._load_jobs", return_value=[]):
            r = client.put("/api/cron/ghost", json={"name": "X"})
        assert r.status_code == 404


class TestDeleteJob:
    def test_delete_returns_200(self, client):
        jobs = [{"id": "j1", "name": "J", "schedule": "daily", "command": "x", "enabled": True}]
        with patch("icecode_server.routes.cron._load_jobs", return_value=jobs), \
             patch("icecode_server.routes.cron._save_jobs"):
            r = client.delete("/api/cron/j1")
        assert r.status_code == 200

    def test_delete_nonexistent_returns_200(self, client):
        with patch("icecode_server.routes.cron._load_jobs", return_value=[]), \
             patch("icecode_server.routes.cron._save_jobs"):
            r = client.delete("/api/cron/ghost")
        assert r.status_code == 200


class TestTriggerJob:
    def test_trigger_returns_200(self, client):
        jobs = [{"id": "j1", "name": "J", "schedule": "daily", "command": "echo hi", "enabled": True}]
        with patch("icecode_server.routes.cron._load_jobs", return_value=jobs):
            r = client.post("/api/cron/j1/trigger")
        assert r.status_code == 200

    def test_trigger_nonexistent_404(self, client):
        with patch("icecode_server.routes.cron._load_jobs", return_value=[]):
            r = client.post("/api/cron/ghost/trigger")
        assert r.status_code == 404
