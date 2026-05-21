"""KnowledgeManager — singleton that coordinates indexing and retrieval."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import List, Dict, Any, Optional

from loguru import logger
from .store import VectorStore
from .indexer import DocumentIndexer
from .retriever import RAGRetriever


class KnowledgeManager:
    """Thread-safe singleton for local knowledge base operations."""

    _instance: Optional["KnowledgeManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._store = VectorStore(dim=384)
        self._indexer = DocumentIndexer()
        self._retriever = RAGRetriever(self._store)

    @classmethod
    def instance(cls) -> "KnowledgeManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def available(self) -> bool:
        try:
            import faiss
            import sentence_transformers
            return True
        except ImportError:
            return False

    def index_file(self, path: str) -> Dict[str, Any]:
        """Index a single file. Returns stats."""
        if not self.available:
            return {"error": "RAG not available. Install: pip install sentence-transformers faiss-cpu"}
        chunks = self._indexer.index_file(path)
        if not chunks:
            return {"indexed": 0, "source": path, "error": "No content extracted"}
        self._retriever.embed_chunks_and_store(chunks, path)
        return {"indexed": len(chunks), "source": path}

    def index_directory(self, path: str, recursive: bool = True) -> Dict[str, Any]:
        """Index all supported files in a directory. Returns stats."""
        if not self.available:
            return {"error": "RAG not available. Install: pip install sentence-transformers faiss-cpu"}
        chunks = self._indexer.index_directory(path, recursive=recursive)
        if not chunks:
            return {"indexed": 0, "source": path, "error": "No content extracted"}

        # Group by source for efficient storage
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
        return s
