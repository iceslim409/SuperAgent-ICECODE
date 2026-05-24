"""Unit tests for icecode_server.routes.swarm

Tests swarm run (SSE streaming), template listing, and template get.
Patches SwarmCoordinator so no real LLM is needed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

ROOT = Path(__file__).parents[2]
for _p in ("packages/core", "packages/server", "packages/tools"):
    sys.path.insert(0, str(ROOT / _p))

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


_FAKE_TEMPLATES = {
    "research_write": {
        "name": "Research & Write",
        "description": "Research a topic then write a document",
        "mode": "pipeline",
        "stages": [
            {"role": "researcher", "task": "Research: {input}"},
            {"role": "writer",     "task": "Write based on: {input}"},
        ],
    },
    "code_review": {
        "name": "Code Review",
        "description": "Parallel review from multiple perspectives",
        "mode": "parallel",
        "agents": [
            {"role": "security_reviewer", "task": "Security review: {input}"},
            {"role": "performance_reviewer", "task": "Performance review: {input}"},
        ],
    },
}


async def _fake_stream(*args, **kwargs):
    events = [
        {"type": "agent_start",  "agent": "researcher", "task": "Research: hello"},
        {"type": "text",         "agent": "researcher", "content": "Found info."},
        {"type": "agent_done",   "agent": "researcher"},
        {"type": "swarm_done",   "output": "Final result."},
    ]
    for e in events:
        yield e


@pytest.fixture()
def mock_coordinator():
    coord = MagicMock()
    coord.run = _fake_stream
    with patch("icecode.swarm.coordinator.SwarmCoordinator", return_value=coord) as cls_mock, \
         patch("icecode.swarm.coordinator.TEMPLATES", _FAKE_TEMPLATES):
        cls_mock.return_value = coord
        cls_mock.run_template = _fake_stream
        yield coord


@pytest.fixture()
def mock_templates():
    with patch("icecode.swarm.coordinator.TEMPLATES", _FAKE_TEMPLATES):
        yield _FAKE_TEMPLATES


# ---------------------------------------------------------------------------
# POST /api/swarm/run
# ---------------------------------------------------------------------------

class TestSwarmRun:
    def test_run_returns_200(self, client, mock_coordinator):
        resp = client.post("/api/swarm/run", json={
            "input": "Hello world",
            "mode": "pipeline",
            "agents": [{"role": "assistant", "task": "Help with: {input}"}],
        })
        assert resp.status_code == 200

    def test_run_returns_event_stream(self, client, mock_coordinator):
        resp = client.post("/api/swarm/run", json={
            "input": "test",
            "mode": "pipeline",
            "agents": [{"role": "helper"}],
        })
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_run_body_nonempty(self, client, mock_coordinator):
        resp = client.post("/api/swarm/run", json={
            "input": "test input",
            "mode": "parallel",
            "agents": [{"role": "a"}, {"role": "b"}],
        })
        assert len(resp.text) > 0

    def test_run_with_template(self, client, mock_coordinator):
        with patch("icecode.swarm.coordinator.TEMPLATES", _FAKE_TEMPLATES):
            resp = client.post("/api/swarm/run", json={
                "input": "test",
                "template": "research_write",
            })
        assert resp.status_code == 200

    def test_run_minimal_request(self, client, mock_coordinator):
        resp = client.post("/api/swarm/run", json={"input": "hello"})
        assert resp.status_code == 200

    def test_run_missing_input_returns_error(self, client):
        resp = client.post("/api/swarm/run", json={})
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# GET /api/swarm/templates
# ---------------------------------------------------------------------------

class TestSwarmTemplates:
    def test_list_templates_returns_200(self, client, mock_templates):
        resp = client.get("/api/swarm/templates")
        assert resp.status_code == 200

    def test_list_templates_has_templates_key(self, client, mock_templates):
        data = client.get("/api/swarm/templates").json()
        assert "templates" in data
        assert isinstance(data["templates"], list)

    def test_list_templates_count_matches(self, client, mock_templates):
        data = client.get("/api/swarm/templates").json()
        assert len(data["templates"]) == len(_FAKE_TEMPLATES)

    def test_each_template_has_id(self, client, mock_templates):
        data = client.get("/api/swarm/templates").json()
        for t in data["templates"]:
            assert "id" in t

    def test_each_template_has_mode(self, client, mock_templates):
        data = client.get("/api/swarm/templates").json()
        for t in data["templates"]:
            assert "mode" in t
            assert t["mode"] in ("pipeline", "parallel")

    def test_each_template_has_num_agents(self, client, mock_templates):
        data = client.get("/api/swarm/templates").json()
        for t in data["templates"]:
            assert "num_agents" in t
            assert t["num_agents"] > 0


# ---------------------------------------------------------------------------
# GET /api/swarm/templates/{template_id}
# ---------------------------------------------------------------------------

class TestGetTemplate:
    def test_get_existing_template_returns_200(self, client, mock_templates):
        resp = client.get("/api/swarm/templates/research_write")
        assert resp.status_code == 200

    def test_get_template_has_id(self, client, mock_templates):
        data = client.get("/api/swarm/templates/research_write").json()
        assert data.get("id") == "research_write"

    def test_get_template_has_name(self, client, mock_templates):
        data = client.get("/api/swarm/templates/research_write").json()
        assert "name" in data

    def test_get_template_pipeline_has_stages(self, client, mock_templates):
        data = client.get("/api/swarm/templates/research_write").json()
        assert "stages" in data
        assert len(data["stages"]) == 2

    def test_get_template_parallel_has_agents(self, client, mock_templates):
        data = client.get("/api/swarm/templates/code_review").json()
        assert "agents" in data

    def test_get_nonexistent_template_returns_404(self, client, mock_templates):
        resp = client.get("/api/swarm/templates/does-not-exist")
        assert resp.status_code == 404
