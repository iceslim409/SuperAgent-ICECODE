"""SwarmCoordinator — high-level API for multi-agent orchestration."""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, Dict, List, Optional, Any, Literal

from .pipeline import run_pipeline
from .parallel import run_parallel


# Built-in swarm templates
TEMPLATES = {
    "research_write": {
        "name": "Research & Write",
        "description": "One agent researches, the second writes a complete report",
        "mode": "pipeline",
        "stages": [
            {
                "role": "researcher",
                "task": "Research the following topic in detail. Gather facts, data, and multiple perspectives. Subject: {input}",
                "system_extra": "You are a meticulous researcher. Find precise information and document your sources.",
            },
            {
                "role": "writer",
                "task": "Based on the research below, write a well-structured report with titles, subtitles and clear conclusions.\n\nResearch:\n{context}",
                "system_extra": "You are a professional writer. Transform raw information into clear and well-organized content.",
            },
        ],
    },
    "code_review": {
        "name": "Code Review Pipeline",
        "description": "Analyze code, identify issues, propose improvements",
        "mode": "pipeline",
        "stages": [
            {
                "role": "security_analyst",
                "task": "Analyze the following code for security vulnerabilities and critical bugs:\n{input}",
                "system_extra": "You are a software security expert. Identify SQL injection, XSS, race conditions, memory leaks.",
            },
            {
                "role": "code_reviewer",
                "task": "Review code quality (clean code, SOLID, performance). Maintenance notes:\n{context}\n\nOriginal code:\n{input}",
                "system_extra": "You are a senior software engineer. Focus on readability, maintainability and performance.",
            },
            {
                "role": "refactoring_expert",
                "task": "Based on the analysis below, write the improved version of the code:\n{context}",
                "system_extra": "You are a refactoring expert. Write improved code, maintaining the original functionality.",
            },
        ],
    },
    "brainstorm": {
        "name": "Brainstorm 360°",
        "description": "3 agents analyze in parallel from different perspectives: opportunities, risks, implementation",
        "mode": "parallel",
        "agents": [
            {
                "role": "optimist",
                "task": "Analyze the opportunities and benefits for: {input}. Be constructive and creativ.",
                "system_extra": "You are an optimistic visionary. Identify the maximum potential.",
            },
            {
                "role": "critic",
                "task": "Analyze the risks, obstacles and potential problems for: {input}. Be realistic.",
                "system_extra": "You are a constructive critic. Identify everything that could go wrong.",
            },
            {
                "role": "strategist",
                "task": "Propose a concrete step-by-step implementation plan for: {input}",
                "system_extra": "You are a pragmatic strategist. Focus on concrete and measurable actions.",
            },
        ],
    },
    "multi_perspective": {
        "name": "Multi-Perspective Analysis",
        "description": "4 specialists analyze the same topic in parallel",
        "mode": "parallel",
        "agents": [
            {
                "role": "technical_expert",
                "task": "Analyze the technical aspects of: {input}",
                "system_extra": "You are a technical expert. Focus on implementation and architecture.",
            },
            {
                "role": "business_analyst",
                "task": "Analyze the business impact of: {input}",
                "system_extra": "You are a business analyst. Focus on ROI, costs, and market opportunities.",
            },
            {
                "role": "ux_designer",
                "task": "Analyze the user experience for: {input}",
                "system_extra": "You are a UX designer. Focus on usability and user satisfaction.",
            },
            {
                "role": "security_expert",
                "task": "Analyze the security and compliance implications for: {input}",
                "system_extra": "You are a security and compliance expert.",
            },
        ],
    },
}


class SwarmCoordinator:
    """Orchestrates multiple agents in pipeline or parallel mode."""

    def __init__(
        self,
        mode: Literal["pipeline", "parallel"] = "pipeline",
        model: str = "",
        provider: str = "ollama",
        base_url: Optional[str] = None,
    ):
        self.mode = mode
        self.default_model = model
        self.default_provider = provider
        self.default_base_url = base_url

    def _inject_defaults(self, agents: List[Dict]) -> List[Dict]:
        result = []
        for a in agents:
            merged = dict(a)
            if not merged.get("model"):
                merged["model"] = self.default_model
            if not merged.get("provider"):
                merged["provider"] = self.default_provider
            if not merged.get("base_url") and self.default_base_url:
                merged["base_url"] = self.default_base_url
            result.append(merged)
        return result

    async def run(
        self,
        input_text: str,
        stages_or_agents: List[Dict[str, Any]],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream events from the swarm execution."""
        items = self._inject_defaults(stages_or_agents)
        if self.mode == "pipeline":
            async for chunk in run_pipeline(items, input_text):
                yield chunk
        else:
            async for chunk in run_parallel(items, input_text):
                yield chunk

    @classmethod
    async def run_template(
        cls,
        template_name: str,
        input_text: str,
        model: str = "",
        provider: str = "ollama",
        base_url: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Run a built-in template by name."""
        tpl = TEMPLATES.get(template_name)
        if not tpl:
            yield {"type": "error", "content": f"Template '{template_name}' not found"}
            return

        mode = tpl["mode"]
        items = tpl.get("stages", tpl.get("agents", []))

        coord = cls(mode=mode, model=model, provider=provider, base_url=base_url)
        async for chunk in coord.run(input_text, items):
            yield chunk

    @staticmethod
    def get_templates() -> Dict[str, Any]:
        return {k: {kk: vv for kk, vv in v.items() if kk != "stages" and kk != "agents"}
                for k, v in TEMPLATES.items()}
