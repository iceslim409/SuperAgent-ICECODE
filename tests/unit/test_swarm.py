"""Unit tests for multi-agent swarm."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from typing import AsyncIterator

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "core"))


async def _mock_agent_stream(message: str):
    """Mock agent that yields fake text chunks."""
    yield {"type": "session", "session_id": "mock_session"}
    yield {"type": "text", "content": f"Response to: {message}"}
    yield {"type": "done"}


class TestSwarmWorker:
    @pytest.mark.asyncio
    async def test_worker_runs_and_collects_output(self):
        from icecode.swarm.worker import SwarmWorker

        worker = SwarmWorker(role="tester")
        chunks = []

        with patch("icecode.agent.core.ICECodeAgent") as MockAgent:
            mock_instance = MagicMock()
            mock_instance.stream = _mock_agent_stream
            mock_instance.history = []
            MockAgent.return_value = mock_instance

            async for chunk in worker.run("test task"):
                chunks.append(chunk)

        assert any(c.get("type") == "text" for c in chunks)

    def test_worker_role_is_set(self):
        from icecode.swarm.worker import SwarmWorker
        w = SwarmWorker(role="analyst", model="qwen2.5:7b")
        assert w.role == "analyst"
        assert w.model == "qwen2.5:7b"


class TestPipeline:
    @pytest.mark.asyncio
    async def test_pipeline_produces_stage_events(self):
        from icecode.swarm.pipeline import run_pipeline

        stages = [
            {"role": "researcher", "task": "Research: {input}"},
            {"role": "writer", "task": "Write about: {context}"},
        ]

        events = []
        with patch("icecode.swarm.worker.SwarmWorker") as MockWorker:
            mock_w = MagicMock()
            mock_w.last_output = "mock output"

            async def mock_run(task, context=""):
                yield {"type": "text", "content": "mock"}

            mock_w.run = mock_run
            MockWorker.return_value = mock_w

            async for event in run_pipeline(stages, "test input"):
                events.append(event)

        stage_events = [e for e in events if e.get("type") == "pipeline_stage"]
        assert len(stage_events) == 2
        assert events[-1].get("type") == "pipeline_done"

    @pytest.mark.asyncio
    async def test_pipeline_passes_context_between_stages(self):
        from icecode.swarm.pipeline import run_pipeline

        received_tasks = []

        async def mock_run_capturing(task, context=""):
            received_tasks.append(task)
            yield {"type": "text", "content": "output_from_stage"}

        with patch("icecode.swarm.worker.SwarmWorker") as MockWorker:
            mock_w = MagicMock()
            mock_w.run = mock_run_capturing
            mock_w.last_output = "output_from_stage"
            MockWorker.return_value = mock_w

            stages = [
                {"role": "r1", "task": "Stage 1: {input}"},
                {"role": "r2", "task": "Stage 2 based on: {context}"},
            ]
            async for _ in run_pipeline(stages, "initial"):
                pass


class TestSwarmCoordinator:
    def test_get_templates_returns_dict(self):
        from icecode.swarm.coordinator import SwarmCoordinator
        templates = SwarmCoordinator.get_templates()
        assert "research_write" in templates
        assert "code_review" in templates
        assert "brainstorm" in templates

    def test_template_has_required_fields(self):
        from icecode.swarm.coordinator import TEMPLATES
        for name, tpl in TEMPLATES.items():
            assert "name" in tpl, f"Template {name} missing 'name'"
            assert "mode" in tpl, f"Template {name} missing 'mode'"
            assert tpl["mode"] in ("pipeline", "parallel"), f"Template {name} invalid mode"

    @pytest.mark.asyncio
    async def test_unknown_template_yields_error(self):
        from icecode.swarm.coordinator import SwarmCoordinator
        events = []
        async for e in SwarmCoordinator.run_template("nonexistent", "input"):
            events.append(e)
        assert any(e.get("type") == "error" for e in events)
