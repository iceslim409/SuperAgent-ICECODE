"""Tests for /api/cache routes."""
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


def _mk_cache(stats=None, get_result=None, cleared=0):
    c = MagicMock()
    c.stats.return_value = stats or {"size": 5, "hits": 10, "misses": 3}
    c.get.return_value = get_result
    c.clear.return_value = cleared
    return c


class TestCacheStats:
    def test_returns_200(self, client):
        with patch("icecode_server.routes.cache._get_cache", return_value=_mk_cache()):
            r = client.get("/api/cache/stats")
        assert r.status_code == 200

    def test_returns_dict(self, client):
        with patch("icecode_server.routes.cache._get_cache", return_value=_mk_cache()):
            data = client.get("/api/cache/stats").json()
        assert isinstance(data, dict)

    def test_has_size(self, client):
        with patch("icecode_server.routes.cache._get_cache", return_value=_mk_cache({"size": 7})):
            data = client.get("/api/cache/stats").json()
        assert data["size"] == 7


class TestCacheClear:
    def test_returns_200(self, client):
        with patch("icecode_server.routes.cache._get_cache", return_value=_mk_cache(cleared=3)):
            r = client.delete("/api/cache/clear")
        assert r.status_code == 200

    def test_returns_cleared_count(self, client):
        with patch("icecode_server.routes.cache._get_cache", return_value=_mk_cache(cleared=5)):
            data = client.delete("/api/cache/clear").json()
        assert data["cleared"] == 5

    def test_has_message(self, client):
        with patch("icecode_server.routes.cache._get_cache", return_value=_mk_cache(cleared=2)):
            data = client.delete("/api/cache/clear").json()
        assert "message" in data

    def test_zero_cleared(self, client):
        with patch("icecode_server.routes.cache._get_cache", return_value=_mk_cache(cleared=0)):
            data = client.delete("/api/cache/clear").json()
        assert data["cleared"] == 0


class TestCacheTest:
    def test_miss_returns_200(self, client):
        with patch("icecode_server.routes.cache._get_cache", return_value=_mk_cache(get_result=None)):
            r = client.post("/api/cache/test", json={"prompt": "hello"})
        assert r.status_code == 200

    def test_miss_has_hit_false(self, client):
        with patch("icecode_server.routes.cache._get_cache", return_value=_mk_cache(get_result=None)):
            data = client.post("/api/cache/test", json={"prompt": "hello"}).json()
        assert data["hit"] is False

    def test_hit_returns_true(self, client):
        with patch("icecode_server.routes.cache._get_cache", return_value=_mk_cache(get_result="cached response here")):
            data = client.post("/api/cache/test", json={"prompt": "hello"}).json()
        assert data["hit"] is True

    def test_hit_has_preview(self, client):
        with patch("icecode_server.routes.cache._get_cache", return_value=_mk_cache(get_result="cached answer")):
            data = client.post("/api/cache/test", json={"prompt": "hello"}).json()
        assert "response_preview" in data
