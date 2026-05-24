"""Tests for /api/gateway routes."""
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


class TestGatewayStatus:
    def test_returns_200(self, client):
        r = client.get("/api/gateway/status")
        assert r.status_code == 200

    def test_has_state(self, client):
        data = client.get("/api/gateway/status").json()
        assert "state" in data

    def test_stopped_when_no_process(self, client):
        with patch("icecode_server.routes.gateway._gateway_process", None):
            data = client.get("/api/gateway/status").json()
        assert data["state"] == "stopped"


class TestGatewayStart:
    def test_start_returns_200(self, client):
        with patch("icecode_server.routes.gateway._gateway_process", None), \
             patch("icecode_server.routes.gateway.Path") as mock_path:
            mock_path.return_value.parents.__getitem__.return_value.__truediv__.return_value.__truediv__.return_value.exists.return_value = False
            r = client.post("/api/gateway/start")
        assert r.status_code == 200

    def test_already_running_no_new_process(self, client):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 9999
        with patch("icecode_server.routes.gateway._gateway_process", mock_proc):
            data = client.post("/api/gateway/start").json()
        assert data.get("ok") is True
        assert data.get("state") == "already_running"


class TestGatewayStop:
    def test_stop_when_running(self, client):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        with patch("icecode_server.routes.gateway._gateway_process", mock_proc):
            data = client.post("/api/gateway/stop").json()
        assert data.get("ok") is True

    def test_stop_when_already_stopped(self, client):
        with patch("icecode_server.routes.gateway._gateway_process", None):
            data = client.post("/api/gateway/stop").json()
        assert data.get("ok") is True
        assert data.get("state") == "already_stopped"
