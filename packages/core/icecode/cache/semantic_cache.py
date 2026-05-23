"""
ICECODE Semantic Response Cache
================================
Before every LLM API call, checks if a semantically similar question was already
answered. If similarity >= threshold → return cached response, 0 tokens spent.

Uses sentence-transformers (already installed for RAG) + a simple JSON store.
No FAISS needed — for cache sizes < 10k entries, linear search is fast enough.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from threading import Lock
from typing import Optional

from loguru import logger

_CACHE_DIR = Path(os.getenv("ICECODE_DATA_DIR", Path.home() / ".icecode" / "data")) / "semantic_cache"
_INDEX_FILE = _CACHE_DIR / "index.json"
_DEFAULT_THRESHOLD = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.92"))
_DEFAULT_TTL = int(os.getenv("CACHE_TTL_HOURS", "24")) * 3600
_ENABLED = os.getenv("SEMANTIC_CACHE_ENABLED", "true").lower() not in ("false", "0", "no")


class SemanticCache:
    def __init__(self, threshold: float = _DEFAULT_THRESHOLD, ttl_seconds: int = _DEFAULT_TTL):
        self.threshold = threshold
        self.ttl = ttl_seconds
        self._lock = Lock()
        self._entries: list[dict] = []
        self._embedder = None
        self._embedder_loading = False
        self._stats = {"hits": 0, "misses": 0, "tokens_saved": 0, "cost_saved_usd": 0.0}
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._load()
        # Pre-load embedder in background thread so first request isn't blocked
        self._start_background_load()

    def _start_background_load(self):
        import threading
        self._embedder_loading = True
        def _load():
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    from sentence_transformers import SentenceTransformer
                    self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
                    logger.debug("SemanticCache: embedder ready")
            except Exception as e:
                logger.warning(f"SemanticCache: embedder unavailable — {e}")
            finally:
                self._embedder_loading = False
        t = threading.Thread(target=_load, daemon=True)
        t.start()

    def _get_embedder(self):
        # Return None while loading to skip cache lookup (cache miss, not a block)
        if self._embedder_loading:
            return None
        return self._embedder

    def _embed(self, text: str):
        emb = self._get_embedder()
        if emb is None:
            return None
        return emb.encode(text, normalize_embeddings=True).tolist()

    def _cosine(self, a: list, b: list) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        return dot  # already normalized

    def _load(self):
        if _INDEX_FILE.exists():
            try:
                self._entries = json.loads(_INDEX_FILE.read_text())
            except Exception:
                self._entries = []

    def _save(self):
        try:
            _INDEX_FILE.write_text(json.dumps(self._entries))
        except Exception as e:
            logger.debug(f"Cache save error: {e}")

    def _prune_expired(self):
        now = time.time()
        self._entries = [e for e in self._entries if now - e["ts"] < self.ttl]

    def get(self, prompt: str, model: str = "") -> Optional[str]:
        if not _ENABLED:
            return None
        emb = self._embed(prompt)
        if emb is None:
            return None
        now = time.time()
        with self._lock:
            best_score = 0.0
            best_entry = None
            for entry in self._entries:
                if now - entry["ts"] > self.ttl:
                    continue
                score = self._cosine(emb, entry["emb"])
                if score > best_score:
                    best_score = score
                    best_entry = entry
            if best_entry and best_score >= self.threshold:
                self._stats["hits"] += 1
                self._stats["tokens_saved"] += best_entry.get("tokens", 0)
                self._stats["cost_saved_usd"] += best_entry.get("cost_usd", 0.0)
                logger.debug(f"Cache HIT (score={best_score:.3f})")
                return best_entry["response"]
            self._stats["misses"] += 1
            return None

    def set(self, prompt: str, response: str, model: str = "",
            tokens_used: int = 0, cost_usd: float = 0.0):
        if not _ENABLED:
            return
        emb = self._embed(prompt)
        if emb is None:
            return
        with self._lock:
            self._prune_expired()
            self._entries.append({
                "emb": emb,
                "response": response,
                "model": model,
                "tokens": tokens_used,
                "cost_usd": cost_usd,
                "ts": time.time(),
            })
            # Keep max 5000 entries
            if len(self._entries) > 5000:
                self._entries = self._entries[-5000:]
            self._save()

    def stats(self) -> dict:
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = round(self._stats["hits"] / total * 100, 1) if total else 0
            return {
                **self._stats,
                "hit_rate_pct": hit_rate,
                "total_requests": total,
                "entries": len(self._entries),
                "enabled": _ENABLED,
                "threshold": self.threshold,
                "ttl_hours": self.ttl // 3600,
            }

    def clear(self) -> int:
        with self._lock:
            n = len(self._entries)
            self._entries = []
            self._save()
            return n


_cache_instance: Optional[SemanticCache] = None


def get_cache() -> SemanticCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SemanticCache()
    return _cache_instance
