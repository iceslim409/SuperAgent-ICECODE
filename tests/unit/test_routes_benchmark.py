"""Tests for /api/benchmark routes."""
import json
from unittest.mock import patch, AsyncMock
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


_RESULT = {"idx": 0, "provider": "ollama", "model": "llama3:8b", "text": "hi",
           "input_tokens": 5, "output_tokens": 3, "elapsed_ms": 42, "error": None}


class TestBenchmarkPresets:
    def test_returns_200(self, client):
        r = client.get("/api/benchmark/presets")
        assert r.status_code == 200

    def test_returns_list(self, client):
        data = client.get("/api/benchmark/presets").json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_each_has_label(self, client):
        data = client.get("/api/benchmark/presets").json()
        assert all("label" in p for p in data)

    def test_each_has_model(self, client):
        data = client.get("/api/benchmark/presets").json()
        assert all("model" in p for p in data)

    def test_has_ollama_preset(self, client):
        data = client.get("/api/benchmark/presets").json()
        providers = [p.get("provider") for p in data]
        assert "ollama" in providers


class TestBenchmarkRun:
    def test_run_returns_200(self, client):
        with patch("icecode_server.routes.benchmark._run_one", new_callable=AsyncMock, return_value=_RESULT):
            r = client.post("/api/benchmark/run", json={
                "prompt": "test",
                "models": [{"provider": "ollama", "model": "llama3:8b"}],
            })
        assert r.status_code == 200

    def test_run_returns_event_stream(self, client):
        with patch("icecode_server.routes.benchmark._run_one", new_callable=AsyncMock, return_value=_RESULT):
            r = client.post("/api/benchmark/run", json={
                "prompt": "test",
                "models": [{"provider": "ollama", "model": "llama3:8b"}],
            })
        assert "text/event-stream" in r.headers.get("content-type", "")

    def test_run_contains_start_event(self, client):
        with patch("icecode_server.routes.benchmark._run_one", new_callable=AsyncMock, return_value=_RESULT):
            r = client.post("/api/benchmark/run", json={
                "prompt": "test",
                "models": [{"provider": "ollama", "model": "llama3:8b"}],
            })
        lines = [l for l in r.text.split("\n") if l.startswith("data:")]
        events = [json.loads(l[5:]) for l in lines]
        assert any(e.get("event") == "start" for e in events)

    def test_run_contains_done_event(self, client):
        with patch("icecode_server.routes.benchmark._run_one", new_callable=AsyncMock, return_value=_RESULT):
            r = client.post("/api/benchmark/run", json={
                "prompt": "test",
                "models": [{"provider": "ollama", "model": "llama3:8b"}],
            })
        lines = [l for l in r.text.split("\n") if l.startswith("data:")]
        events = [json.loads(l[5:]) for l in lines]
        assert any(e.get("event") == "done" for e in events)

    def test_run_contains_result_event(self, client):
        with patch("icecode_server.routes.benchmark._run_one", new_callable=AsyncMock, return_value=_RESULT):
            r = client.post("/api/benchmark/run", json={
                "prompt": "test",
                "models": [{"provider": "ollama", "model": "llama3:8b"}],
            })
        lines = [l for l in r.text.split("\n") if l.startswith("data:")]
        events = [json.loads(l[5:]) for l in lines]
        assert any(e.get("event") == "result" for e in events)
