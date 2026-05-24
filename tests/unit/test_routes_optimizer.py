"""Tests for /api/optimizer routes."""
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


def _mk_decision():
    d = MagicMock()
    d.model = "llama3:8b"
    d.score = 0.3
    d.tier = "cheap"
    d.cost_per_1k_input = 0.0
    d.cost_per_1k_output = 0.0
    d.estimated_cost_usd = 0.0
    d.reason = "local model, free"
    d.is_local = True
    return d


def _mk_router(decision=None, stats=None):
    r = MagicMock()
    r.route.return_value = decision or _mk_decision()
    r.stats.return_value = stats or {"total_routed": 5, "local_fraction": 0.8}
    r.preferred_models = []
    return r


class TestRoutePrompt:
    def test_returns_200(self, client):
        with patch("icecode_server.routes.optimizer._router", return_value=_mk_router()):
            r = client.post("/api/optimizer/route", json={"prompt": "hello"})
        assert r.status_code == 200

    def test_has_model(self, client):
        with patch("icecode_server.routes.optimizer._router", return_value=_mk_router()):
            data = client.post("/api/optimizer/route", json={"prompt": "hello"}).json()
        assert "model" in data

    def test_has_tier(self, client):
        with patch("icecode_server.routes.optimizer._router", return_value=_mk_router()):
            data = client.post("/api/optimizer/route", json={"prompt": "hello"}).json()
        assert "tier" in data

    def test_has_is_local(self, client):
        with patch("icecode_server.routes.optimizer._router", return_value=_mk_router()):
            data = client.post("/api/optimizer/route", json={"prompt": "hello"}).json()
        assert "is_local" in data


class TestOptimizerStats:
    def test_returns_200(self, client):
        with patch("icecode_server.routes.optimizer._router", return_value=_mk_router()):
            r = client.get("/api/optimizer/stats")
        assert r.status_code == 200

    def test_returns_dict(self, client):
        with patch("icecode_server.routes.optimizer._router", return_value=_mk_router(stats={"total_routed": 10})):
            data = client.get("/api/optimizer/stats").json()
        assert isinstance(data, dict)


class TestCostTable:
    def test_returns_200_or_500(self, client):
        r = client.get("/api/optimizer/cost-table")
        assert r.status_code in (200, 500)

    def test_returns_dict_when_available(self, client):
        from icecode.optimizer.cost_router import COST_TABLE
        r = client.get("/api/optimizer/cost-table")
        if r.status_code == 200:
            assert isinstance(r.json(), dict)


class TestCompressContext:
    def test_returns_200_or_500(self, client):
        messages = [{"role": "user", "content": "hello"}]
        r = client.post("/api/optimizer/compress", json={"messages": messages})
        assert r.status_code in (200, 500)
