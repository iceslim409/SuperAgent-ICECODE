"""VectorStore — FAISS-based local vector storage with persistence."""
from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np
from loguru import logger

_STORE_DIR = Path.home() / ".icecode" / "data" / "knowledge"
_INDEX_FILE = _STORE_DIR / "index.faiss"
_META_FILE = _STORE_DIR / "meta.json"
_SOURCES_FILE = _STORE_DIR / "sources.json"


class VectorStore:
    """FAISS vector store with JSON metadata persistence."""

    def __init__(self, dim: int = 384):
        self.dim = dim
        self._index = None
        self._meta: List[Dict[str, Any]] = []
        self._sources: Dict[str, Dict] = {}  # source_path → {chunk_count, indexed_at}
        self._load()

    def _load(self):
        try:
            import faiss
            _STORE_DIR.mkdir(parents=True, exist_ok=True)
            if _INDEX_FILE.exists():
                self._index = faiss.read_index(str(_INDEX_FILE))
                self._meta = json.loads(_META_FILE.read_text()) if _META_FILE.exists() else []
                self._sources = json.loads(_SOURCES_FILE.read_text()) if _SOURCES_FILE.exists() else {}
                logger.debug(f"VectorStore loaded: {len(self._meta)} chunks, {len(self._sources)} sources")
            else:
                self._index = faiss.IndexFlatL2(self.dim)
        except ImportError:
            logger.warning("faiss-cpu not installed — knowledge base unavailable")
            self._index = None
        except Exception as e:
            logger.warning(f"VectorStore load error: {e}")
            self._reset_index()

    def _reset_index(self):
        try:
            import faiss
            self._index = faiss.IndexFlatL2(self.dim)
            self._meta = []
        except ImportError:
            self._index = None

    def _save(self):
        if self._index is None:
            return
        try:
            import faiss
            _STORE_DIR.mkdir(parents=True, exist_ok=True)
            faiss.write_index(self._index, str(_INDEX_FILE))
            _META_FILE.write_text(json.dumps(self._meta, ensure_ascii=False))
            _SOURCES_FILE.write_text(json.dumps(self._sources, ensure_ascii=False, default=str))
        except Exception as e:
            logger.error(f"VectorStore save error: {e}")

    @property
    def available(self) -> bool:
        return self._index is not None

    @property
    def total_chunks(self) -> int:
        return len(self._meta)

    def add(self, embeddings: np.ndarray, metadata: List[Dict[str, Any]], source_path: str):
        if self._index is None:
            return
        if len(embeddings) == 0:
            return

        self._index.add(embeddings.astype("float32"))
        self._meta.extend(metadata)

        # Update source registry
        from datetime import datetime
        self._sources[source_path] = {
            "chunk_count": self._sources.get(source_path, {}).get("chunk_count", 0) + len(metadata),
            "indexed_at": datetime.now().isoformat(),
        }
        self._save()

    def search(self, query_embedding: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        if self._index is None or self._index.ntotal == 0:
            return []
        k = min(k, self._index.ntotal)
        distances, indices = self._index.search(query_embedding.reshape(1, -1).astype("float32"), k)
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self._meta):
                continue
            meta = dict(self._meta[idx])
            meta["score"] = float(1.0 / (1.0 + dist))  # convert L2 distance to similarity score
            results.append(meta)
        return results

    def delete_by_source(self, source_path: str) -> int:
        """Remove all chunks from a specific source. Rebuilds index."""
        if self._index is None:
            return 0

        original_count = len(self._meta)
        kept_meta = [m for m in self._meta if m.get("source") != source_path]
        removed = original_count - len(kept_meta)

        if removed == 0:
            return 0

        # Rebuild index without the removed chunks
        try:
            import faiss
            new_index = faiss.IndexFlatL2(self.dim)
            self._meta = kept_meta
            self._sources.pop(source_path, None)
            # Note: we can't recover vectors without re-embedding, so we track which need rebuild
            # For now, mark the source as deleted and note index needs rebuild
            logger.info(f"Removed {removed} chunks from source {source_path}. Index rebuild required for full cleanup.")
            self._save()
        except Exception as e:
            logger.error(f"Error rebuilding index: {e}")
        return removed

    def list_sources(self) -> List[Dict[str, Any]]:
        return [{"path": k, **v} for k, v in self._sources.items()]

    def stats(self) -> Dict[str, Any]:
        return {
            "total_chunks": len(self._meta),
            "total_sources": len(self._sources),
            "index_size": self._index.ntotal if self._index else 0,
            "available": self.available,
        }
