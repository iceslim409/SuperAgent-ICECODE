"""RAGRetriever — embeds queries and retrieves relevant chunks."""
from __future__ import annotations

from typing import List, Dict, Any, Optional

import numpy as np
from loguru import logger


_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model (all-MiniLM-L6-v2)...")
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Embedding model ready.")
        except ImportError:
            logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
            raise
    return _embedder


class RAGRetriever:
    """Combines embedding generation with vector store search."""

    def __init__(self, store):
        self.store = store

    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for a list of texts."""
        model = _get_embedder()
        embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        return embeddings.astype("float32")

    def embed_chunks_and_store(self, chunks: List[Dict[str, Any]], source_path: str):
        """Embed chunks and add them to the vector store."""
        if not chunks:
            return
        texts = [c["text"] for c in chunks]
        embeddings = self.embed(texts)
        self.store.add(embeddings, chunks, source_path)
        logger.info(f"Stored {len(chunks)} chunks for {source_path}")

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant chunks by natural language query."""
        query_embedding = self.embed([query])[0]
        results = self.store.search(query_embedding, k=k)
        return results

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
