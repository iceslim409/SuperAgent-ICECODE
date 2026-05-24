"""Tests for /api/mcp routes."""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


_SERVERS = [
    {"id": "mcp_abc123", "name": "FS", "transport": "stdio", "command": "npx", "args": [], "url": None,
     "env": {}, "enabled": True, "status": "disconnected", "tools": [], "tools_count": 0, "error": None},
]


class TestListServers:
    def test_returns_200(self, client):
        with patch("icecode_server.routes.mcp._load", return_value=_SERVERS):
            r = client.get("/api/mcp/")
        assert r.status_code == 200

    def test_returns_list(self, client):
        with patch("icecode_server.routes.mcp._load", return_value=_SERVERS):
            data = client.get("/api/mcp/").json()
        assert isinstance(data, list)

    def test_empty_list(self, client):
        with patch("icecode_server.routes.mcp._load", return_value=[]):
            data = client.get("/api/mcp/").json()
        assert data == []


class TestAddServer:
    def test_returns_200(self, client):
        with patch("icecode_server.routes.mcp._load", return_value=[]), \
             patch("icecode_server.routes.mcp._save"):
            r = client.post("/api/mcp/", json={"name": "FileSystem", "transport": "stdio", "command": "npx"})
        assert r.status_code == 200

    def test_has_id(self, client):
        with patch("icecode_server.routes.mcp._load", return_value=[]), \
             patch("icecode_server.routes.mcp._save"):
            data = client.post("/api/mcp/", json={"name": "FS", "transport": "stdio"}).json()
        assert "id" in data

    def test_status_is_disconnected(self, client):
        with patch("icecode_server.routes.mcp._load", return_value=[]), \
             patch("icecode_server.routes.mcp._save"):
            data = client.post("/api/mcp/", json={"name": "FS", "transport": "stdio"}).json()
        assert data.get("status") == "disconnected"

    def test_calls_save(self, client):
        with patch("icecode_server.routes.mcp._load", return_value=[]), \
             patch("icecode_server.routes.mcp._save") as mock_save:
            client.post("/api/mcp/", json={"name": "X"})
        mock_save.assert_called_once()


class TestRemoveServer:
    def test_returns_200(self, client):
        servers = list(_SERVERS)
        with patch("icecode_server.routes.mcp._load", return_value=servers), \
             patch("icecode_server.routes.mcp._save"):
            r = client.delete("/api/mcp/mcp_abc123")
        assert r.status_code == 200

    def test_returns_ok(self, client):
        with patch("icecode_server.routes.mcp._load", return_value=[]), \
             patch("icecode_server.routes.mcp._save"):
            data = client.delete("/api/mcp/any_id").json()
        assert data.get("ok") is True


class TestConnectServer:
    def test_connect_returns_200(self, client):
        servers = [dict(_SERVERS[0])]
        with patch("icecode_server.routes.mcp._load", return_value=servers), \
             patch("icecode_server.routes.mcp._save"), \
             patch("icecode_server.routes.mcp._connect_stdio", side_effect=RuntimeError("no cmd")):
            r = client.post("/api/mcp/mcp_abc123/connect")
        assert r.status_code == 200

    def test_connect_missing_server_404(self, client):
        with patch("icecode_server.routes.mcp._load", return_value=[]):
            r = client.post("/api/mcp/ghost/connect")
        assert r.status_code == 404

    def test_connect_error_sets_error_field(self, client):
        servers = [dict(_SERVERS[0])]
        with patch("icecode_server.routes.mcp._load", return_value=servers), \
             patch("icecode_server.routes.mcp._save"), \
             patch("icecode_server.routes.mcp._connect_stdio", side_effect=RuntimeError("test error")):
            data = client.post("/api/mcp/mcp_abc123/connect").json()
        assert data.get("ok") is False
        assert data.get("error") is not None
