"""Tests for /api/files routes."""
import tempfile
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from icecode_server.main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def tmp_icecode_dir(tmp_path_factory):
    """Create a temp dir under ~/.icecode that passes the sandbox check."""
    base = Path.home() / ".icecode"
    base.mkdir(parents=True, exist_ok=True)
    tmp = base / "_pytest_files_test"
    tmp.mkdir(exist_ok=True)
    yield tmp
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


class TestReadFile:
    def test_read_existing_file(self, client, tmp_icecode_dir):
        f = tmp_icecode_dir / "test_read.txt"
        f.write_text("hello world")
        r = client.get("/api/files/read", params={"path": str(f)})
        assert r.status_code == 200
        assert r.json()["content"] == "hello world"

    def test_read_returns_type_file(self, client, tmp_icecode_dir):
        f = tmp_icecode_dir / "test_type.txt"
        f.write_text("data")
        data = client.get("/api/files/read", params={"path": str(f)}).json()
        assert data["type"] == "file"

    def test_read_nonexistent_returns_404(self, client, tmp_icecode_dir):
        r = client.get("/api/files/read", params={"path": str(tmp_icecode_dir / "no_such_file.txt")})
        assert r.status_code == 404

    def test_read_directory_returns_entries(self, client, tmp_icecode_dir):
        data = client.get("/api/files/read", params={"path": str(tmp_icecode_dir)}).json()
        assert data["type"] == "dir"
        assert "entries" in data

    def test_read_outside_sandbox_returns_403(self, client):
        r = client.get("/api/files/read", params={"path": "/etc/passwd"})
        assert r.status_code == 403


class TestWriteFile:
    def test_write_creates_file(self, client, tmp_icecode_dir):
        f = str(tmp_icecode_dir / "written.txt")
        r = client.post("/api/files/write", json={"path": f, "content": "test content"})
        assert r.status_code == 200
        assert Path(f).read_text() == "test content"

    def test_write_returns_ok(self, client, tmp_icecode_dir):
        f = str(tmp_icecode_dir / "written2.txt")
        data = client.post("/api/files/write", json={"path": f, "content": "x"}).json()
        assert data["ok"] is True

    def test_write_outside_sandbox_returns_403(self, client):
        r = client.post("/api/files/write", json={"path": "/tmp/evil.txt", "content": "x"})
        assert r.status_code == 403
