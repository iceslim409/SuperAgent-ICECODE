"""Pipeline executor — agents run sequentially, output feeds next agent."""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, Dict, List, Any

from .worker import SwarmWorker


async def run_pipeline(
    stages: List[Dict[str, Any]],
    initial_input: str,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Run agents as a sequential pipeline.

    stages: [
        {"role": "researcher", "model": "qwen2.5:7b", "task": "Research {input}"},
        {"role": "writer",     "model": "qwen2.5:7b", "task": "Write a report based on {context}"},
        {"role": "reviewer",   "model": "qwen2.5:7b", "task": "Review and improve: {context}"},
    ]
    """
    context = initial_input
    total = len(stages)

    for i, stage in enumerate(stages):
        role = stage.get("role", f"agent_{i}")
        task_template = stage.get("task", "{input}")

        task = task_template.replace("{input}", initial_input).replace("{context}", context)

        yield {
            "type": "pipeline_stage",
            "stage": i + 1,
            "total_stages": total,
            "role": role,
        }

        worker = SwarmWorker(
            role=role,
            model=stage.get("model", ""),
            provider=stage.get("provider", "ollama"),
            base_url=stage.get("base_url"),
            system_extra=stage.get("system_extra", ""),
            max_iterations=stage.get("max_iterations", 8),
        )

        async for chunk in worker.run(task, context="" if i == 0 else ""):
            yield chunk

        context = worker.last_output

        yield {
            "type": "pipeline_stage_done",
            "stage": i + 1,
            "role": role,
            "output_length": len(context),
        }

    yield {"type": "pipeline_done", "total_stages": total, "final_output": context}
