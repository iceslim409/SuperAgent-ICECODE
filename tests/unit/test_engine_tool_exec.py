"""Unit tests for engine_tool_exec — _ToolExecutionMixin."""
import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "core"))


class TestToolExecutionMixinExists:
    def test_mixin_importable(self):
        from icecode.agent.engine_tool_exec import _ToolExecutionMixin
        assert _ToolExecutionMixin is not None

    def test_mixin_has_expected_methods(self):
        from icecode.agent.engine_tool_exec import _ToolExecutionMixin
        for method in (
            "_execute_tool_calls",
            "_dispatch_delegate_task",
            "_invoke_tool",
            "_wrap_verbose",
            "_execute_tool_calls_concurrent",
            "_execute_tool_calls_sequential",
        ):
            assert hasattr(_ToolExecutionMixin, method), f"missing method: {method}"


class TestWrapVerbose:
    def test_short_text_returned_unchanged(self):
        from icecode.agent.engine_tool_exec import _ToolExecutionMixin
        result = _ToolExecutionMixin._wrap_verbose("Label: ", "short text")
        assert "short text" in result
        assert "Label: " in result

    def test_long_text_wrapped(self):
        from icecode.agent.engine_tool_exec import _ToolExecutionMixin
        long_text = "word " * 60
        result = _ToolExecutionMixin._wrap_verbose("  ", long_text)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_multiline_text_preserves_breaks(self):
        from icecode.agent.engine_tool_exec import _ToolExecutionMixin
        text = "line one\nline two\nline three"
        result = _ToolExecutionMixin._wrap_verbose(">> ", text)
        assert "line one" in result
        assert "line two" in result

    def test_custom_indent(self):
        from icecode.agent.engine_tool_exec import _ToolExecutionMixin
        result = _ToolExecutionMixin._wrap_verbose("X: ", "text", indent="---")
        assert result.startswith("---")


class TestInvokeTool:
    def _make_agent(self):
        """Minimal AIAgent-like object for testing _invoke_tool via mixin."""
        from icecode.agent.engine_tool_exec import _ToolExecutionMixin

        class FakeAgent(_ToolExecutionMixin):
            session_id = "test_session"
            valid_tool_names = None
            clarify_callback = None
            _todo_store = {}
            _memory_store = {}
            _memory_manager = None
            _context_engine_tool_names = set()

            def _get_session_db_for_recall(self):
                return None

            def _build_memory_write_metadata(self, **kw):
                return {}

        return FakeAgent()

    def test_session_search_with_no_db(self):
        # Plugin hook import fails gracefully (ImportError caught), block_message=None.
        # Inject a minimal stub for icecode.icecode_state before invoking.
        import sys
        mock_state = MagicMock()
        mock_state.format_session_db_unavailable = lambda: "db unavailable"
        sys.modules["icecode.icecode_state"] = mock_state
        try:
            agent = self._make_agent()
            result = agent._invoke_tool("session_search", {"query": "hello"}, "task1")
        finally:
            sys.modules.pop("icecode.icecode_state", None)
        data = json.loads(result)
        assert data.get("success") is False

    def test_clarify_tool_uses_callback(self):
        agent = self._make_agent()
        agent.clarify_callback = MagicMock(return_value="user answer")
        with patch("tools.clarify_tool.clarify_tool", return_value="user answer"):
            result = agent._invoke_tool("clarify", {"question": "Continue?"}, "task1")
        assert result == "user answer"

    def test_delegate_task_routes_correctly(self):
        agent = self._make_agent()
        with patch("tools.delegate_tool.delegate_task", return_value="done") as mock_dt:
            result = agent._invoke_tool("delegate_task", {"goal": "test goal"}, "task1")
        mock_dt.assert_called_once()
        assert result == "done"

    def test_dispatch_delegate_passes_parent_agent(self):
        agent = self._make_agent()
        with patch("tools.delegate_tool.delegate_task", return_value="delegated") as mock_delegate:
            result = agent._dispatch_delegate_task({"goal": "do stuff", "tasks": None})
        mock_delegate.assert_called_once()
        call_kwargs = mock_delegate.call_args.kwargs
        assert call_kwargs.get("parent_agent") is agent
        assert result == "delegated"
