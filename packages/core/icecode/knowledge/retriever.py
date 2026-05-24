"""RAGRetriever — embeds queries and retrieves relevant chunks via Ollama."""
from __future__ import annotations

import os
from typing import List, Dict, Any

import httpx
import numpy as np
from loguru import logger

# Ollama embedding model — nomic-embed-text is 768-dim, fast, fully local
_EMBED_MODEL = os.environ.get("ICECODE_EMBED_MODEL", "nomic-embed-text")
_OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


def _embed_via_ollama(texts: List[str]) -> np.ndarray:
    """Call Ollama /api/embeddings for a batch of texts."""
    embeddings = []
    with httpx.Client(timeout=30) as client:
        for text in texts:
            try:
                resp = client.post(
                    f"{_OLLAMA_URL}/api/embeddings",
                    json={"model": _EMBED_MODEL, "prompt": text},
                )
                resp.raise_for_status()
                emb = resp.json().get("embedding", [])
                if not emb:
                    raise ValueError("Empty embedding returned")
                embeddings.append(emb)
            except Exception as e:
                logger.error(f"Ollama embed error: {e}")
                # Fallback: zero vector of correct dim (will score low in search)
                dim = embeddings[0] if embeddings else [0.0] * 768
                embeddings.append([0.0] * len(dim if isinstance(dim, list) else [0] * 768))
    return np.array(embeddings, dtype="float32")


class RAGRetriever:
    """Combines Ollama embedding generation with FAISS vector store search."""

    def __init__(self, store):
        self.store = store

    @property
    def embed_model(self) -> str:
        return _EMBED_MODEL

    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for a list of texts using Ollama."""
        return _embed_via_ollama(texts)

    def embed_chunks_and_store(self, chunks: List[Dict[str, Any]], source_path: str):
        """Embed chunks and add them to the vector store."""
        if not chunks:
            return
        texts = [c["text"] for c in chunks]
        logger.info(f"Embedding {len(chunks)} chunks via {_EMBED_MODEL}...")
        embeddings = self.embed(texts)
        self.store.add(embeddings, chunks, source_path)
        logger.info(f"Stored {len(chunks)} chunks for {source_path}")

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant chunks by natural language query."""
        query_emb = self.embed([query])[0]
        return self.store.search(query_emb, k=k)

    def format_context(self, results: List[Dict[str, Any]], max_chars: int = 3000) -> str:
        """Format search results as context text for the agent."""
        if not results:
            return ""
        parts = ["[Knowledge Base Results]"]
        total = 0
        for i, r in enumerate(results, 1):
            source = r.get("source", "unknown")
            score = r.get("score", 0)
            text = r.get("text", "")
            entry = f"\n[{i}] {source} (relevance: {score:.2f})\n{text}"
            if total + len(entry) > max_chars:
                break
            parts.append(entry)
            total += len(entry)
        return "\n".join(parts)


def check_embedder_available() -> bool:
    """Return True if Ollama embedding model is reachable."""
    try:
        resp = httpx.post(
            f"{_OLLAMA_URL}/api/embeddings",
            json={"model": _EMBED_MODEL, "prompt": "test"},
            timeout=5,
        )
        return resp.status_code == 200 and bool(resp.json().get("embedding"))
    except Exception:
        return False
