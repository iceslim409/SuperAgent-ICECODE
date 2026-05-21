"""Unit tests for ICECodeAgent core functionality."""
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "core"))


class TestUsageTracker:
    def test_initial_state(self):
        from icecode.agent.core import UsageTracker
        u = UsageTracker()
        assert u.prompt_tokens == 0
        assert u.completion_tokens == 0
        assert u.iterations == 0

    def test_update_from_object(self):
        from icecode.agent.core import UsageTracker
        u = UsageTracker()
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50
        u.update(mock_usage)
        assert u.prompt_tokens == 100
        assert u.completion_tokens == 50

    def test_to_dict(self):
        from icecode.agent.core import UsageTracker
        u = UsageTracker()
        u.prompt_tokens = 200
        u.completion_tokens = 100
        d = u.to_dict()
        assert d["prompt_tokens"] == 200
        assert d["completion_tokens"] == 100
        assert d["total_tokens"] == 300


class TestSessionStore:
    def test_save_and_load(self, tmp_path, monkeypatch):
        from icecode.agent.core import SessionStore
        monkeypatch.setenv("HOME", str(tmp_path))
        store = SessionStore()
        messages = [{"role": "user", "content": "hello"}]
        store.save("test_session", messages, {"model": "test"})
        loaded = store.load("test_session")
        assert loaded is not None
        assert loaded["messages"] == messages

    def test_load_missing_session(self, tmp_path, monkeypatch):
        from icecode.agent.core import SessionStore
        monkeypatch.setenv("HOME", str(tmp_path))
        store = SessionStore()
        assert store.load("nonexistent_xyz_abc") is None

    def test_list_sessions(self, tmp_path, monkeypatch):
        from icecode.agent.core import SessionStore
        monkeypatch.setenv("HOME", str(tmp_path))
        store = SessionStore()
        store.save("s_list_1", [{"role": "user", "content": "test1"}], {})
        store.save("s_list_2", [{"role": "user", "content": "test2"}], {})
        sessions = store.list_sessions()
        ids = [s.get("id") or s.get("session_id") for s in sessions]
        assert "s_list_1" in ids
        assert "s_list_2" in ids

    def test_session_title_generated(self, tmp_path, monkeypatch):
        from icecode.agent.core import SessionStore
        monkeypatch.setenv("HOME", str(tmp_path))
        store = SessionStore()
        messages = [{"role": "user", "content": "Cum functioneaza retelele neuronale?"}]
        store.save("s_title_test", messages, {})
        loaded = store.load("s_title_test")
        assert "title" in loaded
        assert len(loaded["title"]) > 0


class TestMakeTitle:
    def test_title_from_first_user_message(self):
        from icecode.agent.core import SessionStore
        messages = [
            {"role": "system", "content": "You are an AI"},
            {"role": "user", "content": "Tell me about Python"},
        ]
        title = SessionStore._make_title(messages)
        assert "Python" in title

    def test_title_truncated_at_60(self):
        from icecode.agent.core import SessionStore
        long_msg = "A" * 100
        messages = [{"role": "user", "content": long_msg}]
        title = SessionStore._make_title(messages)
        assert len(title) <= 62  # 60 chars + "…"
        assert "…" in title

    def test_title_default_when_no_user_message(self):
        from icecode.agent.core import SessionStore
        messages = [{"role": "system", "content": "system prompt"}]
        title = SessionStore._make_title(messages)
        assert title  # not empty


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_read_file(self, tmp_path):
        from icecode.agent.core import _exec_tool
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello ICECODE!")
        result = await _exec_tool("read_file", {"path": str(test_file)})
        assert "Hello ICECODE!" in result

    @pytest.mark.asyncio
    async def test_read_file_not_found(self):
        from icecode.agent.core import _exec_tool
        result = await _exec_tool("read_file", {"path": "/nonexistent/file.txt"})
        assert "Error" in result or "not found" in result

    @pytest.mark.asyncio
    async def test_write_file(self, tmp_path):
        from icecode.agent.core import _exec_tool
        target = tmp_path / "output.txt"
        result = await _exec_tool("write_file", {"path": str(target), "content": "test content"})
        assert target.exists()
        assert target.read_text() == "test content"

    @pytest.mark.asyncio
    async def test_list_dir(self, tmp_path):
        from icecode.agent.core import _exec_tool
        (tmp_path / "file1.py").write_text("x")
        (tmp_path / "file2.md").write_text("y")
        result = await _exec_tool("list_dir", {"path": str(tmp_path)})
        assert "file1.py" in result
        assert "file2.md" in result

    @pytest.mark.asyncio
    async def test_run_terminal_echo(self):
        from icecode.agent.core import _exec_tool
        result = await _exec_tool("run_terminal", {"command": "echo 'icecode_test'"})
        assert "icecode_test" in result

    @pytest.mark.asyncio
    async def test_run_terminal_exit_code(self):
        from icecode.agent.core import _exec_tool
        result = await _exec_tool("run_terminal", {"command": "exit 0"})
        assert "Exit code: 0" in result

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        from icecode.agent.core import _exec_tool
        result = await _exec_tool("nonexistent_tool", {})
        assert "Unknown" in result or "error" in result.lower()
