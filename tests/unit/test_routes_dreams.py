"""Tests for /api/dreams routes."""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


_MEMORIES = {"fact1": "Paris is in France", "fact2": "Water boils at 100C"}
_PHASES = {
    "light":  {"enabled": True,  "cron": "0 2 * * *",  "description": "Consolidare"},
    "rem":    {"enabled": True,  "cron": "0 3 * * *",  "description": "Associations"},
    "deep":   {"enabled": False, "cron": "0 4 * * sun", "description": "Promote"},
}


class TestDreamsStatus:
    def test_returns_200(self, client):
        with patch("icecode_server.routes.dreams._load_memories", return_value={}), \
             patch("icecode_server.routes.dreams._load_promoted", return_value=[]), \
             patch("icecode_server.routes.dreams._load_phases", return_value=_PHASES):
            r = client.get("/api/dreams/status")
        assert r.status_code == 200

    def test_has_enabled_key(self, client):
        with patch("icecode_server.routes.dreams._load_memories", return_value={}), \
             patch("icecode_server.routes.dreams._load_promoted", return_value=[]), \
             patch("icecode_server.routes.dreams._load_phases", return_value=_PHASES):
            data = client.get("/api/dreams/status").json()
        assert "enabled" in data

    def test_short_term_count(self, client):
        with patch("icecode_server.routes.dreams._load_memories", return_value=_MEMORIES), \
             patch("icecode_server.routes.dreams._load_promoted", return_value=[]), \
             patch("icecode_server.routes.dreams._load_phases", return_value=_PHASES):
            data = client.get("/api/dreams/status").json()
        assert data["short_term_count"] == 2

    def test_has_phases(self, client):
        with patch("icecode_server.routes.dreams._load_memories", return_value={}), \
             patch("icecode_server.routes.dreams._load_promoted", return_value=[]), \
             patch("icecode_server.routes.dreams._load_phases", return_value=_PHASES):
            data = client.get("/api/dreams/status").json()
        assert "phases" in data


class TestDreamsDiary:
    def test_get_diary_returns_200(self, client):
        with patch("icecode_server.routes.dreams._DIARY_FILE") as mock_file:
            mock_file.exists.return_value = False
            r = client.get("/api/dreams/diary")
        assert r.status_code == 200

    def test_get_diary_not_found(self, client):
        with patch("icecode_server.routes.dreams._DIARY_FILE") as mock_file:
            mock_file.exists.return_value = False
            data = client.get("/api/dreams/diary").json()
        assert data["found"] is False

    def test_post_diary_returns_200(self, client):
        with patch("icecode_server.routes.dreams._DIARY_FILE") as mock_file, \
             patch("builtins.open", create=True) as mock_open:
            mock_file.parent.mkdir = lambda **kw: None
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = lambda *a: False
            mock_open.return_value.write = lambda x: None
            r = client.post("/api/dreams/diary", json={"content": "Had a dream"})
        assert r.status_code == 200

    def test_post_diary_has_timestamp(self, client):
        with patch("icecode_server.routes.dreams._DIARY_FILE") as mock_file, \
             patch("builtins.open", create=True) as mock_open:
            mock_file.parent.mkdir = lambda **kw: None
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = lambda *a: False
            mock_open.return_value.write = lambda x: None
            data = client.post("/api/dreams/diary", json={"content": "Dream entry"}).json()
        assert "timestamp" in data


class TestDreamsPhases:
    def test_configure_light_phase(self, client):
        with patch("icecode_server.routes.dreams._load_phases", return_value=dict(_PHASES)), \
             patch("icecode_server.routes.dreams._save_json"):
            r = client.put("/api/dreams/phases/light", json={"enabled": False})
        assert r.status_code == 200

    def test_configure_invalid_phase(self, client):
        r = client.put("/api/dreams/phases/invalidphase", json={"enabled": True})
        assert r.status_code == 400

    def test_consolidate_light(self, client):
        with patch("icecode_server.routes.dreams._load_memories", return_value={}), \
             patch("icecode_server.routes.dreams._load_promoted", return_value=[]), \
             patch("icecode_server.routes.dreams._save_json"):
            r = client.post("/api/dreams/consolidate?phase=light")
        assert r.status_code == 200

    def test_consolidate_invalid_phase(self, client):
        r = client.post("/api/dreams/consolidate?phase=invalid")
        assert r.status_code == 400


class TestDreamsMemories:
    def test_delete_memory_key(self, client):
        with patch("icecode_server.routes.dreams._load_memories", return_value=dict(_MEMORIES)), \
             patch("icecode_server.routes.dreams._save_json"):
            r = client.delete("/api/dreams/memories/fact1")
        assert r.status_code == 200

    def test_delete_all_memories(self, client):
        with patch("icecode_server.routes.dreams._load_memories", return_value=dict(_MEMORIES)), \
             patch("icecode_server.routes.dreams._save_json"):
            r = client.delete("/api/dreams/memories")
        assert r.status_code == 200
