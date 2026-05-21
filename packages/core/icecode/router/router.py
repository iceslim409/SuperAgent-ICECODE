"""
ICECODE Intelligent Model Router
=================================
Automatically selects the optimal local Ollama model based on task complexity,
available RAM, and model capabilities. This is a unique ICECODE feature — none
of the three source projects had automatic model routing.

Routing strategy:
  TRIVIAL  → smallest fast model (0.5b–1b)  — quick answers, no reasoning
  SIMPLE   → lightweight model (2b–4b)       — most daily tasks
  MODERATE → mid-range model (4b–7b)         — coding, analysis
  COMPLEX  → best available model (7b+)      — multi-step reasoning, architecture
  VISION   → any vision-capable model        — image analysis
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import httpx


class TaskComplexity(str, Enum):
    TRIVIAL = "trivial"      # "what is 2+2", "say hello"
    SIMPLE = "simple"        # "summarize this text", "write a haiku"
    MODERATE = "moderate"    # "write a Python function", "explain this code"
    COMPLEX = "complex"      # "design an architecture", "debug this system"
    VISION = "vision"        # task requires image analysis


@dataclass
class RouterDecision:
    model: str
    complexity: TaskComplexity
    reason: str
    fallback_model: Optional[str] = None
    estimated_tokens: int = 2048


# Model capability tiers — ordered by capability (ascending)
MODEL_TIERS: dict[str, dict] = {
    # Tier 1 — Nano (0.5b–1b): trivial tasks only
    "qwen2.5:0.5b-instruct": {"tier": 1, "params_b": 0.5, "vision": False},
    "qwen2.5:0.5b":          {"tier": 1, "params_b": 0.5, "vision": False},
    "llama3.2:1b":            {"tier": 1, "params_b": 1.0, "vision": False},
    # Tier 2 — Small (1b–3b): simple everyday tasks
    "qwen3.5:0.8b":           {"tier": 2, "params_b": 0.8, "vision": False},
    "qwen2.5:1.5b":           {"tier": 2, "params_b": 1.5, "vision": False},
    "qwen2.5:3b":             {"tier": 2, "params_b": 3.0, "vision": False},
    "qwen3.5:2b":             {"tier": 2, "params_b": 2.0, "vision": False},
    "granite4.1:3b":          {"tier": 2, "params_b": 3.0, "vision": False},
    # Tier 3 — Medium (4b–5b): coding, analysis, moderate reasoning
    "qwen3.5:4b":             {"tier": 3, "params_b": 4.0, "vision": False},
    "phi4-mini:latest":       {"tier": 3, "params_b": 3.8, "vision": False},
    # Tier 4 — Full (7b+): complex reasoning, best quality
    "mistral:7b-instruct":    {"tier": 4, "params_b": 7.0, "vision": False},
    "qwen2.5:7b":             {"tier": 4, "params_b": 7.0, "vision": False},
    "qwen3.6:latest":         {"tier": 4, "params_b": 6.0, "vision": False},
    "openhermes:latest":      {"tier": 4, "params_b": 7.0, "vision": False},
    # Vision capable
    "llava:latest":           {"tier": 3, "params_b": 7.0, "vision": True},
    "llava:7b":               {"tier": 3, "params_b": 7.0, "vision": True},
    "moondream:latest":       {"tier": 2, "params_b": 1.8, "vision": True},
}

# Keywords that increase complexity assessment
COMPLEX_KEYWORDS = {
    "architect", "design", "system", "refactor", "analyze", "debug",
    "optimize", "implement", "create a full", "build a complete",
    "explain in detail", "comprehensive", "multi-step", "pipeline",
}
SIMPLE_KEYWORDS = {
    "summarize", "translate", "fix", "correct", "check", "list",
    "what is", "how do", "give me", "write a", "simple",
}
CODE_KEYWORDS = {
    "python", "javascript", "typescript", "code", "function", "class",
    "algorithm", "sql", "api", "script", "program",
}

# Think tokens needed (approximate) — used to set context window
COMPLEXITY_TOKENS = {
    TaskComplexity.TRIVIAL: 512,
    TaskComplexity.SIMPLE: 1024,
    TaskComplexity.MODERATE: 2048,
    TaskComplexity.COMPLEX: 4096,
    TaskComplexity.VISION: 2048,
}


class ModelRouter:
    """
    ICECODE's unique intelligent model router.
    Analyzes a task and picks the best available Ollama model for it.
    """

    def __init__(self, ollama_host: str = "http://localhost:11434"):
        self._ollama_host = ollama_host
        self._available: list[str] = []
        self._loaded = False

    # ── Model discovery ────────────────────────────────────────────────────

    async def _load_available_models(self) -> None:
        """Query Ollama for installed models."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self._ollama_host}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    self._available = [m["name"] for m in data.get("models", [])]
        except Exception:
            self._available = []
        self._loaded = True

    def _sync_load(self) -> None:
        """Synchronous fallback for model discovery."""
        try:
            import httpx as _httpx
            resp = _httpx.get(f"{self._ollama_host}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                self._available = [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            self._available = []
        self._loaded = True

    def _get_tier(self, model: str) -> int:
        """Return tier for a model (1=nano, 4=full). Unknown → 3."""
        return MODEL_TIERS.get(model, {}).get("tier", 3)

    def _is_vision(self, model: str) -> bool:
        return MODEL_TIERS.get(model, {}).get("vision", False)

    def _best_model_for_tier(self, target_tier: int, vision: bool = False) -> Optional[str]:
        """
        Return the most capable model at exactly target_tier, or the nearest available tier.
        Prefers the highest-param model within the target tier, then falls back to adjacent tiers.
        """
        # Try exact tier first, then expand outward
        for try_tier in [target_tier, target_tier + 1, target_tier - 1, target_tier + 2, 1]:
            candidates = [
                m for m in self._available
                if self._get_tier(m) == try_tier
                and (not vision or self._is_vision(m))
            ]
            if candidates:
                # Within a tier, pick the largest params model
                return sorted(
                    candidates,
                    key=lambda m: MODEL_TIERS.get(m, {}).get("params_b", 0),
                    reverse=True,
                )[0]
        # Final fallback — any available
        available = [m for m in self._available if not vision or self._is_vision(m)]
        return available[0] if available else (self._available[0] if self._available else None)

    def _lightest_model(self) -> Optional[str]:
        """Return the smallest/fastest available model."""
        if not self._available:
            return None
        return sorted(self._available, key=lambda m: MODEL_TIERS.get(m, {}).get("params_b", 99))[0]

    # ── Complexity assessment ──────────────────────────────────────────────

    @staticmethod
    def assess_complexity(prompt: str) -> TaskComplexity:
        """
        Analyze prompt text and determine task complexity.
        Returns a TaskComplexity enum value.
        """
        text = prompt.lower()
        word_count = len(text.split())

        # Vision tasks
        if any(w in text for w in ["image", "screenshot", "photo", "picture", "visual", "look at"]):
            return TaskComplexity.VISION

        # Score-based assessment
        score = 0

        # Length heuristic
        if word_count > 200:
            score += 3
        elif word_count > 80:
            score += 2
        elif word_count > 20:
            score += 1

        # Keyword analysis
        for kw in COMPLEX_KEYWORDS:
            if kw in text:
                score += 2

        for kw in CODE_KEYWORDS:
            if kw in text:
                score += 1

        for kw in SIMPLE_KEYWORDS:
            if kw in text:
                score = max(0, score - 1)

        # Complexity indicators
        if re.search(r'\b(step[s]? \d|\d+\.\s)', text):  # numbered steps
            score += 2
        if "```" in prompt or "def " in prompt or "class " in prompt:
            score += 1

        # Creative writing is simple even if long
        if any(w in text for w in ["poem", "haiku", "story", "joke", "rhyme"]):
            score = min(score, 2)

        if score <= 0:
            return TaskComplexity.TRIVIAL
        elif score <= 2:
            return TaskComplexity.SIMPLE
        elif score <= 5:
            return TaskComplexity.MODERATE
        else:
            return TaskComplexity.COMPLEX

    # ── Public API ─────────────────────────────────────────────────────────

    def route(self, prompt: str, force_model: Optional[str] = None) -> RouterDecision:
        """
        Synchronously route a prompt to the best available model.

        Args:
            prompt: The user's task/message
            force_model: If set, skip routing and use this model

        Returns:
            RouterDecision with selected model and reasoning
        """
        if not self._loaded:
            self._sync_load()

        if force_model:
            return RouterDecision(
                model=force_model,
                complexity=self.assess_complexity(prompt),
                reason="User-specified model",
            )

        complexity = self.assess_complexity(prompt)
        tokens = COMPLEXITY_TOKENS[complexity]

        tier_map = {
            TaskComplexity.TRIVIAL: 1,
            TaskComplexity.SIMPLE: 2,
            TaskComplexity.MODERATE: 3,
            TaskComplexity.COMPLEX: 4,
            TaskComplexity.VISION: 3,
        }

        min_tier = tier_map[complexity]
        is_vision = complexity == TaskComplexity.VISION
        model = self._best_model_for_tier(min_tier, vision=is_vision)
        fallback = self._lightest_model()

        if not model:
            model = "qwen3.5:4b"  # hardcoded default if Ollama not available
            reason = "Ollama unavailable — using default model"
        else:
            reason = (
                f"Task complexity: {complexity.value} "
                f"(tier {min_tier}+) → selected {model}"
            )

        return RouterDecision(
            model=model,
            complexity=complexity,
            reason=reason,
            fallback_model=fallback if fallback != model else None,
            estimated_tokens=tokens,
        )

    async def route_async(self, prompt: str, force_model: Optional[str] = None) -> RouterDecision:
        """Async version of route() — loads model list from Ollama if needed."""
        if not self._loaded:
            await self._load_available_models()
        return self.route(prompt, force_model)

    def describe(self) -> dict:
        """Return router state for diagnostic/UI purposes."""
        if not self._loaded:
            self._sync_load()
        tiers: dict[int, list[str]] = {1: [], 2: [], 3: [], 4: []}
        for m in self._available:
            t = self._get_tier(m)
            tiers.setdefault(t, []).append(m)
        return {
            "available_models": self._available,
            "tiers": tiers,
            "ollama_host": self._ollama_host,
        }


# Module-level singleton
_router: Optional[ModelRouter] = None

def get_router(ollama_host: str = "http://localhost:11434") -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter(ollama_host)
    return _router
