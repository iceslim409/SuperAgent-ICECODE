"""Unit tests for icecode_server.routes.knowledge

Tests knowledge base stats, auto-index config, manual index, search, sources.
Patches KnowledgeManager so no real FAISS or Ollama is needed.
"""
from __future__ import annotations

import json
import io
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).parents[2]
for _p in ("packages/core", "packages/server", "packages/tools"):
    sys.path.insert(0, str(ROOT / _p))

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


def _km_mock(
    stats=None,
    search_results=None,
    sources=None,
    index_result=None,
):
    km = MagicMock()
    km.stats.return_value = stats or {
        "rag_available": True,
        "total_chunks": 42,
        "total_sources": 3,
    }
    km.search.return_value = search_results or [
        {"text": "Python generators are lazy.", "source": "readme.md", "score": 0.95},
    ]
    km.list_sources.return_value = sources or [
        {"path": "/project/readme.md", "chunk_count": 12, "indexed_at": "2025-01-01"},
    ]
    km.index_file.return_value = index_result or {"indexed": 5, "skipped": 0}
    km.index_directory.return_value = index_result or {"indexed": 10, "skipped": 2}
    km.delete_source.return_value = 5
    return km


@pytest.fixture()
def mock_km():
    km = _km_mock()
    with patch("icecode.knowledge.manager.KnowledgeManager.instance", return_value=km):
        yield km


@pytest.fixture()
def mock_auto_cfg(tmp_path):
    cfg_file = tmp_path / "auto_config.json"
    with patch("icecode_server.routes.knowledge._AUTO_CFG", cfg_file), \
         patch("icecode_server.routes.knowledge._load_auto_cfg",
               return_value={"enabled": False, "path": "", "interval_minutes": 60,
                             "last_indexed": None, "last_chunks": 0, "status": "idle"}), \
         patch("icecode_server.routes.knowledge._save_auto_cfg") as mock_save:
        yield mock_save


# ---------------------------------------------------------------------------
# GET /api/knowledge/stats
# ---------------------------------------------------------------------------

class TestKnowledgeStats:
    def test_stats_returns_200(self, client, mock_km):
        resp = client.get("/api/knowledge/stats")
        assert resp.status_code == 200

    def test_stats_has_rag_available(self, client, mock_km):
        data = client.get("/api/knowledge/stats").json()
        assert "rag_available" in data

    def test_stats_has_chunk_count(self, client, mock_km):
        data = client.get("/api/knowledge/stats").json()
        assert "total_chunks" in data
        assert data["total_chunks"] == 42

    def test_stats_on_error_returns_unavailable(self, client):
        broken = MagicMock()
        broken.stats.side_effect = RuntimeError("FAISS not installed")
        with patch("icecode.knowledge.manager.KnowledgeManager.instance", return_value=broken):
            data = client.get("/api/knowledge/stats").json()
        assert data.get("rag_available") is False
        assert "error" in data


# ---------------------------------------------------------------------------
# GET/POST /api/knowledge/auto-index
# ---------------------------------------------------------------------------

class TestAutoIndex:
    def test_get_auto_index_returns_200(self, client, mock_auto_cfg):
        resp = client.get("/api/knowledge/auto-index")
        assert resp.status_code == 200

    def test_get_auto_index_has_enabled_field(self, client, mock_auto_cfg):
        data = client.get("/api/knowledge/auto-index").json()
        assert "enabled" in data
        assert isinstance(data["enabled"], bool)

    def test_post_auto_index_enable_with_path(self, client, mock_auto_cfg):
        resp = client.post("/api/knowledge/auto-index", json={
            "enabled": True,
            "path": "/home/user/project",
            "interval_minutes": 30,
        })
        assert resp.status_code == 200
        mock_auto_cfg.assert_called_once()

    def test_post_auto_index_enable_without_path_returns_400(self, client, mock_auto_cfg):
        resp = client.post("/api/knowledge/auto-index", json={
            "enabled": True,
            "path": "",
        })
        assert resp.status_code == 400

    def test_post_auto_index_disable_no_path_required(self, client, mock_auto_cfg):
        resp = client.post("/api/knowledge/auto-index", json={
            "enabled": False,
            "path": "",
        })
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/knowledge/index
# ---------------------------------------------------------------------------

class TestIndexPath:
    def test_index_existing_file(self, client, mock_km, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("Some content.")
        resp = client.post("/api/knowledge/index", json={"path": str(f)})
        assert resp.status_code == 200
        mock_km.index_file.assert_called_once()

    def test_index_existing_dir(self, client, mock_km, tmp_path):
        resp = client.post("/api/knowledge/index", json={"path": str(tmp_path), "recursive": True})
        assert resp.status_code == 200
        mock_km.index_directory.assert_called()

    def test_index_returns_indexed_count(self, client, mock_km, tmp_path):
        f = tmp_path / "doc2.txt"
        f.write_text("x")
        data = client.post("/api/knowledge/index", json={"path": str(f)}).json()
        assert "indexed" in data

    def test_index_nonexistent_path_returns_404(self, client, mock_km):
        resp = client.post("/api/knowledge/index", json={"path": "/absolutely/does/not/exist.txt"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/knowledge/upload
# ---------------------------------------------------------------------------

class TestUploadAndIndex:
    def test_upload_file_returns_200(self, client, mock_km, tmp_path):
        with patch("icecode_server.routes.knowledge._UPLOAD_DIR", tmp_path):
            resp = client.post(
                "/api/knowledge/upload",
                files={"file": ("test.txt", io.BytesIO(b"hello world"), "text/plain")},
            )
        assert resp.status_code == 200

    def test_upload_file_returns_filename(self, client, mock_km, tmp_path):
        with patch("icecode_server.routes.knowledge._UPLOAD_DIR", tmp_path):
            data = client.post(
                "/api/knowledge/upload",
                files={"file": ("myfile.txt", io.BytesIO(b"content"), "text/plain")},
            ).json()
        assert data.get("filename") == "myfile.txt"

    def test_upload_calls_index_file(self, client, mock_km, tmp_path):
        with patch("icecode_server.routes.knowledge._UPLOAD_DIR", tmp_path):
            client.post(
                "/api/knowledge/upload",
                files={"file": ("x.txt", io.BytesIO(b"x"), "text/plain")},
            )
        mock_km.index_file.assert_called()


# ---------------------------------------------------------------------------
# GET/POST /api/knowledge/search
# ---------------------------------------------------------------------------

class TestKnowledgeSearch:
    def test_search_get_returns_200(self, client, mock_km):
        resp = client.get("/api/knowledge/search?q=generators")
        assert resp.status_code == 200

    def test_search_get_has_results(self, client, mock_km):
        data = client.get("/api/knowledge/search?q=generators").json()
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_search_get_has_count(self, client, mock_km):
        data = client.get("/api/knowledge/search?q=test").json()
        assert "count" in data
        assert data["count"] == len(data["results"])

    def test_search_post_returns_200(self, client, mock_km):
        resp = client.post("/api/knowledge/search", json={"query": "generators", "k": 3})
        assert resp.status_code == 200

    def test_search_post_passes_k(self, client, mock_km):
        client.post("/api/knowledge/search", json={"query": "test", "k": 3})
        mock_km.search.assert_called_with("test", k=3)

    def test_search_result_has_text_and_score(self, client, mock_km):
        data = client.get("/api/knowledge/search?q=python").json()
        results = data["results"]
        if results:
            assert "text" in results[0]
            assert "score" in results[0]


# ---------------------------------------------------------------------------
# GET/DELETE /api/knowledge/sources
# ---------------------------------------------------------------------------

class TestKnowledgeSources:
    def test_list_sources_returns_200(self, client, mock_km):
        resp = client.get("/api/knowledge/sources")
        assert resp.status_code == 200

    def test_list_sources_has_sources_key(self, client, mock_km):
        data = client.get("/api/knowledge/sources").json()
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_list_sources_has_count(self, client, mock_km):
        data = client.get("/api/knowledge/sources").json()
        assert data["count"] == len(data["sources"])

    def test_delete_source_returns_deleted_path(self, client, mock_km):
        resp = client.delete("/api/knowledge/sources?path=/project/readme.md")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == "/project/readme.md"
        assert "chunks_removed" in data

    def test_delete_source_calls_manager(self, client, mock_km):
        client.delete("/api/knowledge/sources?path=/some/file.md")
        mock_km.delete_source.assert_called()
