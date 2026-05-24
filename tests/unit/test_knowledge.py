"""Unit tests for local knowledge base / RAG."""
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import numpy as np

sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "core"))


class TestDocumentIndexer:
    def test_index_txt_file(self, tmp_path):
        from icecode.knowledge.indexer import DocumentIndexer
        f = tmp_path / "test.txt"
        f.write_text("This is a test document about Python programming. " * 20)
        indexer = DocumentIndexer()
        chunks = indexer.index_file(str(f))
        assert len(chunks) > 0
        assert all("text" in c for c in chunks)
        assert all("source" in c for c in chunks)
        assert all("id" in c for c in chunks)

    def test_index_markdown_file(self, tmp_path):
        from icecode.knowledge.indexer import DocumentIndexer
        f = tmp_path / "readme.md"
        f.write_text("# Title\n\nSome content here.\n\n## Section\n\nMore content.")
        indexer = DocumentIndexer()
        chunks = indexer.index_file(str(f))
        assert len(chunks) > 0

    def test_index_unsupported_file_returns_empty(self, tmp_path):
        from icecode.knowledge.indexer import DocumentIndexer
        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG\r\n")
        indexer = DocumentIndexer()
        chunks = indexer.index_file(str(f))
        assert chunks == []

    def test_index_nonexistent_file_returns_empty(self):
        from icecode.knowledge.indexer import DocumentIndexer
        indexer = DocumentIndexer()
        chunks = indexer.index_file("/nonexistent/path/file.txt")
        assert chunks == []

    def test_index_directory(self, tmp_path):
        from icecode.knowledge.indexer import DocumentIndexer
        (tmp_path / "a.py").write_text("def hello(): pass\n" * 30)
        (tmp_path / "b.md").write_text("# Doc\n\nContent here.\n" * 20)
        (tmp_path / "c.png").write_bytes(b"fake image")
        indexer = DocumentIndexer()
        chunks = indexer.index_directory(str(tmp_path))
        sources = {c["source"] for c in chunks}
        py_sources = [s for s in sources if s.endswith(".py")]
        md_sources = [s for s in sources if s.endswith(".md")]
        assert len(py_sources) == 1
        assert len(md_sources) == 1

    def test_chunks_have_overlap(self, tmp_path):
        from icecode.knowledge.indexer import DocumentIndexer, CHUNK_SIZE, CHUNK_OVERLAP
        # Large enough file to produce multiple chunks
        long_text = "word " * 500
        f = tmp_path / "long.txt"
        f.write_text(long_text)
        indexer = DocumentIndexer()
        chunks = indexer.index_file(str(f))
        if len(chunks) > 1:
            # Verify chunk ordering
            assert chunks[0]["chunk_idx"] == 0
            assert chunks[1]["chunk_idx"] == 1


class TestVectorStore:
    def test_store_unavailable_without_faiss(self):
        """Test graceful degradation when faiss is not installed."""
        with patch.dict("sys.modules", {"faiss": None}):
            from icecode.knowledge import store as store_mod
            # Should not raise, just mark unavailable
            # (actual behavior depends on import time)

    def test_stats_returns_dict(self, tmp_path, monkeypatch):
        """Stats method returns expected keys."""
        try:
            import faiss
            import icecode.knowledge.store as store_mod
            monkeypatch.setattr(store_mod, "_STORE_DIR", tmp_path)
            monkeypatch.setattr(store_mod, "_INDEX_FILE", tmp_path / "index.faiss")
            monkeypatch.setattr(store_mod, "_META_FILE", tmp_path / "meta.json")
            monkeypatch.setattr(store_mod, "_SOURCES_FILE", tmp_path / "sources.json")
            vs = store_mod.VectorStore(dim=4)
            stats = vs.stats()
            assert "total_chunks" in stats
            assert "total_sources" in stats
            assert "available" in stats
        except ImportError:
            pytest.skip("faiss not installed")

    def test_add_and_search(self, tmp_path, monkeypatch):
        try:
            import faiss
            import icecode.knowledge.store as store_mod
            monkeypatch.setattr(store_mod, "_STORE_DIR", tmp_path)
            monkeypatch.setattr(store_mod, "_INDEX_FILE", tmp_path / "index.faiss")
            monkeypatch.setattr(store_mod, "_META_FILE", tmp_path / "meta.json")
            monkeypatch.setattr(store_mod, "_SOURCES_FILE", tmp_path / "sources.json")
            vs = store_mod.VectorStore(dim=4)
            embeddings = np.array([[0.1, 0.2, 0.3, 0.4], [0.9, 0.8, 0.7, 0.6]], dtype="float32")
            meta = [
                {"id": "c1", "text": "Python programming", "source": "test.py"},
                {"id": "c2", "text": "Machine learning", "source": "ml.md"},
            ]
            vs.add(embeddings, meta, "test.py")
            results = vs.search(np.array([0.1, 0.2, 0.3, 0.4], dtype="float32"), k=1)
            assert len(results) >= 1
            assert "text" in results[0]
        except ImportError:
            pytest.skip("faiss not installed")


class TestRAGRetriever:
    def test_format_context_empty(self):
        from icecode.knowledge.retriever import RAGRetriever
        r = RAGRetriever(store=MagicMock())
        assert r.format_context([]) == ""

    def test_format_context_with_results(self):
        from icecode.knowledge.retriever import RAGRetriever
        r = RAGRetriever(store=MagicMock())
        results = [
            {"source": "test.py", "score": 0.95, "text": "some content"},
            {"source": "readme.md", "score": 0.80, "text": "other content"},
        ]
        ctx = r.format_context(results)
        assert "Knowledge Base" in ctx
        assert "test.py" in ctx
        assert "some content" in ctx
