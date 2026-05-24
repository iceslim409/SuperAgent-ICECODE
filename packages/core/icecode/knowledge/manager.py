"""KnowledgeManager — singleton that coordinates indexing and retrieval."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import List, Dict, Any, Optional

from loguru import logger
from .store import VectorStore
from .indexer import DocumentIndexer
from .retriever import RAGRetriever, check_embedder_available


class KnowledgeManager:
    """Thread-safe singleton for local knowledge base operations."""

    _instance: Optional["KnowledgeManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._store = VectorStore(dim=768)  # nomic-embed-text / MiniLM-L12
        self._indexer = DocumentIndexer()
        self._retriever = RAGRetriever(self._store)
        self._embedder_ok: Optional[bool] = None  # cached after first check

    @classmethod
    def instance(cls) -> "KnowledgeManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def available(self) -> bool:
        """True if FAISS and Ollama embedder are both ready."""
        if not self._store.available:
            return False
        # Only cache True — always retry if previously unavailable so that
        # starting Ollama after server startup is picked up automatically.
        if not self._embedder_ok:
            ok = check_embedder_available()
            if ok:
                self._embedder_ok = True
            else:
                logger.warning(
                    "Knowledge base embedder unavailable — "
                    f"ensure Ollama is running and '{self._retriever.embed_model}' is pulled. "
                    f"Run: ollama pull {self._retriever.embed_model}"
                )
        return bool(self._embedder_ok)

    def _unavailable_msg(self) -> str:
        return (
            f"Knowledge base unavailable. "
            f"Ensure Ollama is running and run: ollama pull {self._retriever.embed_model}"
        )

    def index_file(self, path: str) -> Dict[str, Any]:
        """Index a single file. Returns stats."""
        if not self.available:
            return {"error": self._unavailable_msg()}
        chunks = self._indexer.index_file(path)
        if not chunks:
            return {"indexed": 0, "source": path, "error": "No content extracted"}
        self._retriever.embed_chunks_and_store(chunks, path)
        return {"indexed": len(chunks), "source": path}

    def index_directory(self, path: str, recursive: bool = True) -> Dict[str, Any]:
        """Index all supported files in a directory. Returns stats."""
        if not self.available:
            return {"error": self._unavailable_msg()}
        chunks = self._indexer.index_directory(path, recursive=recursive)
        if not chunks:
            return {"indexed": 0, "source": path, "error": "No content extracted"}

        from collections import defaultdict
        by_source: Dict[str, List] = defaultdict(list)
        for c in chunks:
            by_source[c["source"]].append(c)

        total = 0
        for src, src_chunks in by_source.items():
            self._retriever.embed_chunks_and_store(src_chunks, src)
            total += len(src_chunks)

        return {"indexed": total, "sources": len(by_source), "base": path}

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Semantic search in the knowledge base."""
        if not self.available:
            return []
        return self._retriever.search(query, k=k)

    def list_sources(self) -> List[Dict[str, Any]]:
        return self._store.list_sources()

    def delete_source(self, path: str) -> int:
        return self._store.delete_by_source(path)

    def stats(self) -> Dict[str, Any]:
        s = self._store.stats()
        s["rag_available"] = self.available
        s["embed_model"] = self._retriever.embed_model
        return s
