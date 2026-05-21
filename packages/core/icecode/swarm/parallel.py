"""Parallel executor — all agents run simultaneously on the same input."""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, Dict, List, Any

from .worker import SwarmWorker


async def run_parallel(
    agents: List[Dict[str, Any]],
    input_text: str,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Run multiple agents in parallel on the same input.

    agents: [
        {"role": "optimist",  "model": "qwen2.5:7b", "task": "Analyze benefits of: {input}"},
        {"role": "pessimist", "model": "qwen2.5:7b", "task": "Analyze risks of: {input}"},
        {"role": "realist",   "model": "qwen2.5:7b", "task": "Give balanced view of: {input}"},
    ]
    """
    queue: asyncio.Queue = asyncio.Queue()
    results: Dict[str, str] = {}

    async def worker_task(agent_cfg: Dict[str, Any]):
        role = agent_cfg.get("role", "agent")
        task_template = agent_cfg.get("task", "{input}")
        task = task_template.replace("{input}", input_text)

        worker = SwarmWorker(
            role=role,
            model=agent_cfg.get("model", ""),
            provider=agent_cfg.get("provider", "ollama"),
            base_url=agent_cfg.get("base_url"),
            system_extra=agent_cfg.get("system_extra", ""),
            max_iterations=agent_cfg.get("max_iterations", 8),
        )
        async for chunk in worker.run(task):
            await queue.put(chunk)

        results[role] = worker.last_output
        await queue.put({"type": "_worker_done", "role": role})

    tasks = [asyncio.create_task(worker_task(a)) for a in agents]
    done_count = 0
    total = len(agents)

    yield {"type": "parallel_start", "total_agents": total}

    while done_count < total:
        chunk = await queue.get()
        if chunk.get("type") == "_worker_done":
            done_count += 1
            yield {"type": "parallel_agent_done", "role": chunk["role"], "remaining": total - done_count}
        else:
            yield chunk

    await asyncio.gather(*tasks, return_exceptions=True)
    yield {"type": "parallel_done", "total_agents": total, "results": results}
