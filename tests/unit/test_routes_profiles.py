"""Tests for /api/profiles routes."""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


_PROFILES = [
    {"id": "default", "name": "Default", "model": "qwen2.5:7b", "provider": "ollama",
     "system_prompt": "", "max_iterations": 10, "tools": [], "active": True, "builtin": True},
    {"id": "coding", "name": "Coding", "model": "qwen2.5:7b", "provider": "ollama",
     "system_prompt": "You are an expert coder.", "max_iterations": 15, "tools": ["read_file"], "active": False, "builtin": True},
]


class TestListProfiles:
    def test_returns_200(self, client):
        with patch("icecode_server.routes.profiles._load", return_value=_PROFILES):
            r = client.get("/api/profiles/")
        assert r.status_code == 200

    def test_returns_list(self, client):
        with patch("icecode_server.routes.profiles._load", return_value=_PROFILES):
            data = client.get("/api/profiles/").json()
        assert isinstance(data, list)
        assert len(data) == 2


class TestGetActive:
    def test_returns_200(self, client):
        with patch("icecode_server.routes.profiles._load", return_value=_PROFILES):
            r = client.get("/api/profiles/active")
        assert r.status_code == 200

    def test_returns_active_profile(self, client):
        with patch("icecode_server.routes.profiles._load", return_value=_PROFILES):
            data = client.get("/api/profiles/active").json()
        assert data.get("id") == "default"

    def test_returns_first_when_none_active(self, client):
        profiles = [dict(p, active=False) for p in _PROFILES]
        with patch("icecode_server.routes.profiles._load", return_value=profiles):
            data = client.get("/api/profiles/active").json()
        assert data.get("id") == "default"


class TestActivateProfile:
    def test_activate_returns_200(self, client):
        with patch("icecode_server.routes.profiles._load", return_value=list(_PROFILES)), \
             patch("icecode_server.routes.profiles._save"):
            r = client.post("/api/profiles/coding/activate")
        assert r.status_code == 200

    def test_activate_returns_ok(self, client):
        with patch("icecode_server.routes.profiles._load", return_value=list(_PROFILES)), \
             patch("icecode_server.routes.profiles._save"):
            data = client.post("/api/profiles/coding/activate").json()
        assert data.get("ok") is True

    def test_activate_missing_404(self, client):
        with patch("icecode_server.routes.profiles._load", return_value=[]):
            r = client.post("/api/profiles/ghost/activate")
        assert r.status_code == 404


class TestCreateProfile:
    def test_create_returns_200(self, client):
        with patch("icecode_server.routes.profiles._load", return_value=[]), \
             patch("icecode_server.routes.profiles._save"):
            r = client.post("/api/profiles/", json={"name": "MyProfile"})
        assert r.status_code == 200

    def test_create_has_id(self, client):
        with patch("icecode_server.routes.profiles._load", return_value=[]), \
             patch("icecode_server.routes.profiles._save"):
            data = client.post("/api/profiles/", json={"name": "MyProfile"}).json()
        assert "id" in data

    def test_create_not_active(self, client):
        with patch("icecode_server.routes.profiles._load", return_value=[]), \
             patch("icecode_server.routes.profiles._save"):
            data = client.post("/api/profiles/", json={"name": "MyProfile"}).json()
        assert data.get("active") is False


class TestUpdateProfile:
    def test_patch_returns_200(self, client):
        profiles = [dict(_PROFILES[0])]
        with patch("icecode_server.routes.profiles._load", return_value=profiles), \
             patch("icecode_server.routes.profiles._save"):
            r = client.patch("/api/profiles/default", json={"name": "Updated"})
        assert r.status_code == 200

    def test_patch_nonexistent_404(self, client):
        with patch("icecode_server.routes.profiles._load", return_value=[]):
            r = client.patch("/api/profiles/ghost", json={"name": "X"})
        assert r.status_code == 404


class TestDeleteProfile:
    def test_delete_returns_200(self, client):
        profiles = [dict(_PROFILES[0], builtin=False)]
        with patch("icecode_server.routes.profiles._load", return_value=profiles), \
             patch("icecode_server.routes.profiles._save"):
            r = client.delete("/api/profiles/default")
        assert r.status_code == 200

    def test_cannot_delete_builtin(self, client):
        with patch("icecode_server.routes.profiles._load", return_value=list(_PROFILES)):
            r = client.delete("/api/profiles/default")
        assert r.status_code in (400, 403, 422)
