"""
ICECODE Cost-Aware Model Router
================================
Routes each prompt to the cheapest model capable of handling it.
Complexity score (1-10) → model tier → cheapest match.

Cost table is updated to current API pricing (May 2026).
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional

# Price per 1K tokens (USD) — input / output
COST_TABLE: dict[str, dict] = {
    # Anthropic
    "claude-opus-4-7":            {"input": 0.015,   "output": 0.075,  "tier": 4},
    "claude-opus-4-5":            {"input": 0.015,   "output": 0.075,  "tier": 4},
    "claude-sonnet-4-6":          {"input": 0.003,   "output": 0.015,  "tier": 3},
    "claude-sonnet-4-5":          {"input": 0.003,   "output": 0.015,  "tier": 3},
    "claude-haiku-4-5":           {"input": 0.00025, "output": 0.00125,"tier": 1},
    "claude-3-5-haiku-20241022":  {"input": 0.00025, "output": 0.00125,"tier": 1},
    "claude-3-haiku-20240307":    {"input": 0.00025, "output": 0.00125,"tier": 1},
    # OpenAI
    "gpt-4o":                     {"input": 0.0025,  "output": 0.01,   "tier": 3},
    "gpt-4o-mini":                {"input": 0.00015, "output": 0.0006, "tier": 1},
    "gpt-4-turbo":                {"input": 0.01,    "output": 0.03,   "tier": 4},
    "gpt-3.5-turbo":              {"input": 0.0005,  "output": 0.0015, "tier": 2},
    "o3-mini":                    {"input": 0.0011,  "output": 0.0044, "tier": 2},
    # Google
    "gemini-1.5-flash":           {"input": 0.000075,"output": 0.0003, "tier": 1},
    "gemini-1.5-pro":             {"input": 0.00125, "output": 0.005,  "tier": 3},
    "gemini-2.0-flash":           {"input": 0.0001,  "output": 0.0004, "tier": 2},
    # Mistral
    "mistral-small-latest":       {"input": 0.001,   "output": 0.003,  "tier": 2},
    "mistral-large-latest":       {"input": 0.003,   "output": 0.009,  "tier": 3},
    # xAI
    "grok-3-mini":                {"input": 0.0003,  "output": 0.0005, "tier": 1},
    "grok-3":                     {"input": 0.003,   "output": 0.015,  "tier": 3},
    # Local models — free
    "__local__":                  {"input": 0.0,     "output": 0.0,    "tier": 0},
}

# Complexity threshold → minimum tier required
_TIER_FOR_SCORE = {
    (1, 3):  0,   # trivial → local/free (tier 0) or cheapest (tier 1)
    (4, 6):  1,   # moderate → tier 1+
    (7, 8):  2,   # complex → tier 2+
    (9, 10): 3,   # expert → tier 3+
}

_COMPLEXITY_SIGNALS = {
    # +points for complex task (EN + RO)
    "high": [
        r'\b(architect|design|implement|refactor|optimize|analyze|compare|evaluate|debug|explain|prove|derive)\b',
        r'\b(step by step|multiple|comprehensive|detailed|in depth|thorough)\b',
        r'\b(implementeaz[aă]|explic[aă]|analizeaz[aă]|compar[aă]|optimizeaz[aă]|demonstreaz[aă]|arhitectur[aă])\b',
        r'\b(detaliu|detaliat|complet|complex|aprofundat|matematica|algoritm)\b',
        r'```',          # code blocks
        r'\$.*=|∫|∑|∏',  # math symbols
        r'\b(why|how does|what causes|trade.?off|cum functioneaz[aă]|de ce|cum se)\b',
    ],
    # +points moderate (EN + RO)
    "medium": [
        r'\b(write|create|build|make|generate|list|scrie|creeaz[aă]|construie[st]te|genereaz[aă])\b',
        r'\b(function|class|module|api|database|system|functie|clasa|modul|baza de date)\b',
        r'\b(cod|script|program|aplicatie|aplicație)\b',
    ],
    # -points for simple (EN + RO)
    "simple": [
        r'^.{0,50}$',  # very short message
        r'\b(hello|hi|thanks|salut|mersi|multumesc|mulțumesc)\b',
        r'^\s*(ce este|what is|ce e|who is|cine e)\s+\w+\s*\??$',  # "ce este X?"
    ],
}


@dataclass
class CostDecision:
    model: str
    score: int
    tier: int
    cost_per_1k_input: float
    cost_per_1k_output: float
    reason: str
    is_local: bool = False
    estimated_cost_usd: float = 0.0  # for ~500 input + ~300 output tokens


@dataclass
class CostRouter:
    preferred_models: list[str] = field(default_factory=list)
    _history: list[dict] = field(default_factory=list, repr=False)
    _total_saved_usd: float = 0.0
    _total_calls: int = 0

    def score_complexity(self, prompt: str) -> int:
        text = prompt.lower()
        score = 3  # baseline

        for pattern in _COMPLEXITY_SIGNALS["high"]:
            if re.search(pattern, text, re.I):
                score += 2

        for pattern in _COMPLEXITY_SIGNALS["medium"]:
            if re.search(pattern, text, re.I):
                score += 1

        for pattern in _COMPLEXITY_SIGNALS["simple"]:
            if re.search(pattern, text, re.I):
                score = max(1, score - 2)

        # Length bonus
        words = len(prompt.split())
        if words > 200:
            score += 2
        elif words > 80:
            score += 1

        return min(10, max(1, score))

    def _min_tier(self, score: int) -> int:
        for (lo, hi), tier in _TIER_FOR_SCORE.items():
            if lo <= score <= hi:
                return tier
        return 1

    def route(self, prompt: str, force_model: Optional[str] = None) -> CostDecision:
        if force_model:
            info = COST_TABLE.get(force_model, COST_TABLE["__local__"])
            return CostDecision(
                model=force_model, score=5, tier=info["tier"],
                cost_per_1k_input=info["input"], cost_per_1k_output=info["output"],
                reason="Manual override", is_local=info["input"] == 0,
            )

        score = self.score_complexity(prompt)
        min_tier = self._min_tier(score)

        # Check preferred models first, excluding the __local__ placeholder
        real_models = {k: v for k, v in COST_TABLE.items() if k != "__local__"}
        candidates = self.preferred_models if self.preferred_models else list(real_models.keys())

        best: Optional[tuple] = None  # (cost_per_1k, model, info)
        for model in candidates:
            info = COST_TABLE.get(model) or real_models.get(model)
            if info is None:
                continue
            if info["tier"] < min_tier:
                continue
            total_cost = info["input"] + info["output"]
            if best is None or total_cost < best[0]:
                best = (total_cost, model, info)

        if best is None:
            # Fallback: pick anything with matching tier
            for model, info in real_models.items():
                if info["tier"] >= min_tier:
                    best = (info["input"] + info["output"], model, info)
                    break

        if best is None:
            model, info = "gpt-4o-mini", COST_TABLE["gpt-4o-mini"]
        else:
            _, model, info = best

        estimated = (500 * info["input"] + 300 * info["output"]) / 1000

        self._total_calls += 1
        decision = CostDecision(
            model=model, score=score, tier=info["tier"],
            cost_per_1k_input=info["input"], cost_per_1k_output=info["output"],
            reason=f"complexity={score}/10, min_tier={min_tier}",
            is_local=info["input"] == 0,
            estimated_cost_usd=round(estimated, 6),
        )
        self._history.append({
            "ts": time.time(), "model": model, "score": score,
            "estimated_usd": estimated,
        })
        if len(self._history) > 1000:
            self._history = self._history[-1000:]
        return decision

    def record_actual_cost(self, model: str, input_tokens: int, output_tokens: int):
        info = COST_TABLE.get(model, COST_TABLE["__local__"])
        actual = (input_tokens * info["input"] + output_tokens * info["output"]) / 1000

        # Compare with what it would have cost on the most expensive model
        expensive = COST_TABLE.get("claude-opus-4-7", COST_TABLE["gpt-4-turbo"])
        max_cost = (input_tokens * expensive["input"] + output_tokens * expensive["output"]) / 1000
        saved = max(0.0, max_cost - actual)
        self._total_saved_usd += saved

    def stats(self) -> dict:
        return {
            "total_calls": self._total_calls,
            "total_saved_usd": round(self._total_saved_usd, 4),
            "recent_decisions": self._history[-20:],
            "cost_table_models": len(COST_TABLE) - 1,
        }


_router_instance: Optional[CostRouter] = None


def get_cost_router() -> CostRouter:
    global _router_instance
    if _router_instance is None:
        prefs_raw = os.getenv("PREFERRED_MODELS", "")
        prefs = [m.strip() for m in prefs_raw.split(",") if m.strip()]
        _router_instance = CostRouter(preferred_models=prefs)
    return _router_instance
