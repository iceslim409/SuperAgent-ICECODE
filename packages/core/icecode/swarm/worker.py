"""SwarmWorker — wraps ICECodeAgent with a specific role for swarm execution."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional, Any

sys.path.insert(0, str(Path(__file__).parents[4]))

from loguru import logger


class SwarmWorker:
    """Single agent worker inside a swarm."""

    def __init__(
        self,
        role: str,
        model: str = "",
        provider: str = "ollama",
        base_url: Optional[str] = None,
        system_extra: str = "",
        max_iterations: int = 8,
    ):
        self.role = role
        self.model = model
        self.provider = provider
        self.base_url = base_url
        self.system_extra = system_extra
        self.max_iterations = max_iterations

    async def run(self, task: str, context: str = "") -> AsyncIterator[Dict[str, Any]]:
        """Stream events while executing a task."""
        from icecode.agent.core import ICECodeAgent

        full_input = task
        if context:
            full_input = f"[Context from previous step]\n{context}\n\n[Your task]\n{task}"

        agent = ICECodeAgent(
            model=self.model,
            provider=self.provider,
            base_url=self.base_url,
            max_iterations=self.max_iterations,
            system_extra=f"Your role: {self.role}. {self.system_extra}",
        )

        final_text = []
        async for chunk in agent.stream(full_input):
            chunk["worker_role"] = self.role
            yield chunk
            if chunk.get("type") == "text":
                final_text.append(chunk.get("content", ""))

        self._last_output = "".join(final_text)

    @property
    def last_output(self) -> str:
        return getattr(self, "_last_output", "")
