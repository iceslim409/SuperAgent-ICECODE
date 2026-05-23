"""Unit tests for ICECodeAgent core functionality."""
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "core"))
sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "tools"))


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


# ── Tool selection ─────────────────────────────────────────────────────────────

def _get_all_tools():
    """Build the full tool pool the same way core.py does it at runtime."""
    from icecode.agent.core import TOOLS, _get_extended_tools
    pool = list(TOOLS)
    seen = {t["function"]["name"] for t in pool}
    for ext in _get_extended_tools():
        name = ext.get("function", {}).get("name", "")
        if name and name not in seen:
            pool.append(ext)
            seen.add(name)
    return pool


class TestIsGreeting:
    def test_pure_greetings_return_true(self):
        from icecode.agent.core import _is_pure_greeting
        for msg in ["salut", "buna ziua", "ok", "multumesc", "da", "bine", "hello", "hi"]:
            assert _is_pure_greeting(msg), f"Expected greeting: '{msg}'"

    def test_task_messages_return_false(self):
        from icecode.agent.core import _is_pure_greeting
        for msg in [
            "fa un site web", "creeaza un fisier", "instaleaza numpy",
            "ajuta-ma cu codul", "fa un kanban board", "cauta pe web",
            "scrie un script", "fa-mi o aplicatie",
        ]:
            assert not _is_pure_greeting(msg), f"Expected NOT greeting: '{msg}'"

    def test_long_message_is_not_greeting(self):
        from icecode.agent.core import _is_pure_greeting
        assert not _is_pure_greeting("a" * 51)

    def test_message_with_action_keyword_not_greeting(self):
        from icecode.agent.core import _is_pure_greeting
        assert not _is_pure_greeting("fa ceva")
        assert not _is_pure_greeting("cauta ceva")
        assert not _is_pure_greeting("list files")


class TestTokenize:
    def test_strips_punctuation(self):
        from icecode.agent.core import _tokenize
        assert "codul" in _tokenize("codul?")
        assert "script" in _tokenize("script.")
        assert "eroare" in _tokenize("eroare!")

    def test_splits_hyphenated_words(self):
        from icecode.agent.core import _tokenize
        tokens = _tokenize("fa-mi ceva")
        assert "fa" in tokens
        assert "mi" in tokens

    def test_lowercases(self):
        from icecode.agent.core import _tokenize
        assert "python" in _tokenize("Python")
        assert "cod" in _tokenize("COD")

    def test_em_dash_and_en_dash(self):
        from icecode.agent.core import _tokenize
        tokens = _tokenize("ajuta–ma")
        assert "ajuta" in tokens


class TestSelectTools:
    def setup_method(self):
        self.all_tools = _get_all_tools()

    def _names(self, msg):
        from icecode.agent.core import _select_tools_for_message
        return {t["function"]["name"] for t in _select_tools_for_message(msg, self.all_tools)}

    # Pure greetings → 0 tools
    def test_greeting_returns_no_tools(self):
        for msg in ["salut", "buna ziua", "ok", "multumesc", "da"]:
            assert self._names(msg) == set(), f"'{msg}' should return 0 tools"

    # Any task → always has core 7 tools
    def test_task_always_has_core_tools(self):
        core = {"read_file", "write_file", "edit_file", "run_terminal",
                "list_dir", "search_web", "web_fetch"}
        for msg in ["fa un site", "scrie un script", "instaleaza ceva", "fa-mi o aplicatie"]:
            selected = self._names(msg)
            missing = core - selected
            assert not missing, f"'{msg}' missing core tools: {missing}"

    # Code keywords trigger code tier
    def test_code_keyword_adds_code_tools(self):
        for msg in ["ajuta-ma cu codul?", "am o eroare in script", "fa un framework web"]:
            names = self._names(msg)
            assert "git_command" in names or "code_search" in names, \
                f"'{msg}' should trigger code tier, got: {names}"

    # Punctuation: "codul?" should still trigger code tools
    def test_punctuation_in_keyword_handled(self):
        names = self._names("poti sa ma ajuti cu codul?")
        assert "read_file" in names, "punctuation should not block tool selection"

    # Hyphen: "fa-mi" → "fa" matches action keyword
    def test_hyphenated_action_word(self):
        names = self._names("fa-mi o pagina web")
        assert len(names) >= 7, "hyphen should not block tool selection"

    # Kanban keywords
    def test_kanban_keyword_adds_kanban_tools(self):
        for msg in ["arata-mi taskurile din kanban", "creeaza un task nou", "fa un board"]:
            names = self._names(msg)
            assert any(n.startswith("kanban") or n in {"create_task", "list_tasks"}
                       for n in names), f"'{msg}' should add kanban tools, got: {names}"

    # Browser keywords
    def test_browser_keyword_adds_browser_tools(self):
        names = self._names("fa un screenshot la browser")
        assert "browser_snapshot" in names or "browser_navigate" in names

    # Telegram keyword adds messaging tools (only if gateway configured)
    def test_telegram_keyword_triggers_domain_check(self):
        # Even if send_message isn't available (no gateway), core tools should be present
        names = self._names("vreau sa fac un bot de telegram")
        assert "read_file" in names, "core tools should always be present for task messages"

    # Long message always gets tools regardless of content
    def test_long_message_gets_tools(self):
        long = "ce " * 30  # 90 chars, clearly > 80
        names = self._names(long)
        assert len(names) >= 7, "long messages should always get core tools"

    # RL keywords
    def test_rl_keywords(self):
        names = self._names("porneste un rl training run")
        assert any("rl_" in n for n in names), "RL keywords should add RL tools"

    # No duplicate tools returned
    def test_no_duplicate_tools(self):
        from icecode.agent.core import _select_tools_for_message
        msg = "fa un site cu kanban si browser si rl training run"
        selected = _select_tools_for_message(msg, self.all_tools)
        names = [t["function"]["name"] for t in selected]
        assert len(names) == len(set(names)), "No duplicate tools should be returned"
