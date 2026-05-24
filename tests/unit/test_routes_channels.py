"""Tests for /api/channels routes."""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


_CHANNELS = [
    {"id": "ch1", "platform": "telegram", "name": "Bot1", "config": {}, "enabled": True},
    {"id": "ch2", "platform": "discord", "name": "Bot2", "config": {}, "enabled": False},
]


class TestListChannels:
    def test_returns_200(self, client):
        with patch("icecode_server.routes.channels._load_channels", return_value=_CHANNELS):
            r = client.get("/api/channels/")
        assert r.status_code == 200

    def test_returns_list(self, client):
        with patch("icecode_server.routes.channels._load_channels", return_value=_CHANNELS):
            data = client.get("/api/channels/").json()
        assert isinstance(data, list)
        assert len(data) == 2


class TestListPlatforms:
    def test_returns_200(self, client):
        r = client.get("/api/channels/platforms")
        assert r.status_code == 200

    def test_has_telegram(self, client):
        data = client.get("/api/channels/platforms").json()
        platforms = data if isinstance(data, list) else data.get("platforms", [])
        assert "telegram" in platforms

    def test_has_discord(self, client):
        data = client.get("/api/channels/platforms").json()
        platforms = data if isinstance(data, list) else data.get("platforms", [])
        assert "discord" in platforms


class TestCreateChannel:
    def test_returns_200(self, client):
        with patch("icecode_server.routes.channels._load_channels", return_value=[]), \
             patch("icecode_server.routes.channels._save_channels"):
            r = client.post("/api/channels/", json={"platform": "telegram", "name": "MyBot"})
        assert r.status_code == 200

    def test_returns_channel_with_id(self, client):
        with patch("icecode_server.routes.channels._load_channels", return_value=[]), \
             patch("icecode_server.routes.channels._save_channels"):
            data = client.post("/api/channels/", json={"platform": "telegram", "name": "MyBot"}).json()
        assert "id" in data

    def test_stores_platform(self, client):
        with patch("icecode_server.routes.channels._load_channels", return_value=[]), \
             patch("icecode_server.routes.channels._save_channels"):
            data = client.post("/api/channels/", json={"platform": "discord", "name": "D"}).json()
        assert data.get("platform") == "discord"

    def test_calls_save(self, client):
        with patch("icecode_server.routes.channels._load_channels", return_value=[]), \
             patch("icecode_server.routes.channels._save_channels") as mock_save:
            client.post("/api/channels/", json={"platform": "slack", "name": "S"})
        mock_save.assert_called_once()


class TestUpdateChannel:
    def test_update_returns_200(self, client):
        channels = [{"id": "ch1", "platform": "telegram", "name": "Old", "config": {}, "enabled": True}]
        with patch("icecode_server.routes.channels._load_channels", return_value=channels), \
             patch("icecode_server.routes.channels._save_channels"):
            r = client.put("/api/channels/ch1", json={"name": "New"})
        assert r.status_code == 200

    def test_update_nonexistent_returns_404(self, client):
        with patch("icecode_server.routes.channels._load_channels", return_value=[]):
            r = client.put("/api/channels/missing", json={"name": "X"})
        assert r.status_code == 404


class TestDeleteChannel:
    def test_delete_returns_200(self, client):
        channels = [{"id": "ch1", "platform": "telegram", "name": "B", "config": {}, "enabled": True}]
        with patch("icecode_server.routes.channels._load_channels", return_value=channels), \
             patch("icecode_server.routes.channels._save_channels"):
            r = client.delete("/api/channels/ch1")
        assert r.status_code == 200

    def test_delete_nonexistent_returns_200(self, client):
        with patch("icecode_server.routes.channels._load_channels", return_value=[]), \
             patch("icecode_server.routes.channels._save_channels"):
            r = client.delete("/api/channels/ghost")
        assert r.status_code == 200
