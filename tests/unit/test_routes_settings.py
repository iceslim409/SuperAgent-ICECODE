"""Tests for /api/settings routes."""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


def _mk_settings(data=None):
    return data or {"theme": "dark", "language": "en"}


class TestGetSettings:
    def test_returns_200(self, client):
        with patch("icecode_server.routes.settings._load", return_value=_mk_settings()):
            r = client.get("/api/settings/")
        assert r.status_code == 200

    def test_returns_dict(self, client):
        s = {"theme": "light", "max_tokens": 4096}
        with patch("icecode_server.routes.settings._load", return_value=s):
            data = client.get("/api/settings/").json()
        assert isinstance(data, dict)

    def test_returns_stored_values(self, client):
        s = {"theme": "dark", "lang": "ro"}
        with patch("icecode_server.routes.settings._load", return_value=s):
            data = client.get("/api/settings/").json()
        assert data["theme"] == "dark"
        assert data["lang"] == "ro"

    def test_empty_returns_empty_dict(self, client):
        with patch("icecode_server.routes.settings._load", return_value={}):
            data = client.get("/api/settings/").json()
        assert data == {}


class TestPatchSettings:
    def test_patch_returns_200(self, client):
        with patch("icecode_server.routes.settings._load", return_value={}), \
             patch("icecode_server.routes.settings._save"):
            r = client.patch("/api/settings/", json={"data": {"theme": "dark"}})
        assert r.status_code == 200

    def test_patch_merges_data(self, client):
        existing = {"a": 1, "b": 2}
        with patch("icecode_server.routes.settings._load", return_value=existing.copy()), \
             patch("icecode_server.routes.settings._save") as mock_save:
            r = client.patch("/api/settings/", json={"data": {"c": 3}})
        assert r.status_code == 200
        saved = mock_save.call_args[0][0]
        assert saved["a"] == 1
        assert saved["c"] == 3

    def test_patch_overwrites_key(self, client):
        existing = {"theme": "light"}
        with patch("icecode_server.routes.settings._load", return_value=existing.copy()), \
             patch("icecode_server.routes.settings._save") as mock_save:
            client.patch("/api/settings/", json={"data": {"theme": "dark"}})
        saved = mock_save.call_args[0][0]
        assert saved["theme"] == "dark"

    def test_patch_returns_merged(self, client):
        existing = {"x": 10}
        with patch("icecode_server.routes.settings._load", return_value=existing.copy()), \
             patch("icecode_server.routes.settings._save"):
            data = client.patch("/api/settings/", json={"data": {"y": 20}}).json()
        assert data["x"] == 10
        assert data["y"] == 20
