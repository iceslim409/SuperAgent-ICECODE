"""Unit tests for engine_tool_guard — parallel execution safety."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "core"))


class TestIsDestructiveCommand:
    def test_rm_is_destructive(self):
        from icecode.agent.engine_tool_guard import _is_destructive_command
        assert _is_destructive_command("rm -rf /tmp/test")
        assert _is_destructive_command("sudo rm file.txt")

    def test_echo_not_destructive(self):
        from icecode.agent.engine_tool_guard import _is_destructive_command
        assert not _is_destructive_command("echo hello")
        assert not _is_destructive_command("cat file.txt")
        assert not _is_destructive_command("ls -la")

    def test_empty_command(self):
        from icecode.agent.engine_tool_guard import _is_destructive_command
        assert not _is_destructive_command("")

    def test_redirect_overwrite_destructive(self):
        from icecode.agent.engine_tool_guard import _is_destructive_command
        assert _is_destructive_command("echo test > file.txt")

    def test_redirect_append_not_destructive(self):
        from icecode.agent.engine_tool_guard import _is_destructive_command
        assert not _is_destructive_command("echo test >> file.txt")

    def test_git_reset_destructive(self):
        from icecode.agent.engine_tool_guard import _is_destructive_command
        assert _is_destructive_command("git reset --hard HEAD")

    def test_mv_destructive(self):
        from icecode.agent.engine_tool_guard import _is_destructive_command
        assert _is_destructive_command("mv old.txt new.txt")

    def test_sed_inplace_destructive(self):
        from icecode.agent.engine_tool_guard import _is_destructive_command
        assert _is_destructive_command("sed -i 's/foo/bar/' file.txt")


class TestPathsOverlap:
    def test_same_path_overlaps(self):
        from icecode.agent.engine_tool_guard import _paths_overlap
        p = Path("/home/user/project/file.txt")
        assert _paths_overlap(p, p)

    def test_parent_child_overlap(self):
        from icecode.agent.engine_tool_guard import _paths_overlap
        parent = Path("/home/user/project")
        child = Path("/home/user/project/src/main.py")
        assert _paths_overlap(parent, child)
        assert _paths_overlap(child, parent)

    def test_sibling_no_overlap(self):
        from icecode.agent.engine_tool_guard import _paths_overlap
        a = Path("/home/user/project/src")
        b = Path("/home/user/project/tests")
        assert not _paths_overlap(a, b)

    def test_empty_paths(self):
        from icecode.agent.engine_tool_guard import _paths_overlap
        assert not _paths_overlap(Path(""), Path("/tmp"))


class TestShouldParallelizeToolBatch:
    def _make_tc(self, name: str, args: dict = None):
        tc = MagicMock()
        import json
        tc.function.name = name
        tc.function.arguments = json.dumps(args or {})
        return tc

    def test_single_tool_never_parallel(self):
        from icecode.agent.engine_tool_guard import _should_parallelize_tool_batch
        assert not _should_parallelize_tool_batch([self._make_tc("web_search")])

    def test_clarify_blocks_parallel(self):
        from icecode.agent.engine_tool_guard import _should_parallelize_tool_batch
        tc1 = self._make_tc("web_search")
        tc2 = self._make_tc("clarify")
        assert not _should_parallelize_tool_batch([tc1, tc2])

    def test_two_safe_tools_parallel(self):
        from icecode.agent.engine_tool_guard import _should_parallelize_tool_batch
        tc1 = self._make_tc("web_search")
        tc2 = self._make_tc("web_extract")
        assert _should_parallelize_tool_batch([tc1, tc2])

    def test_unsafe_tool_blocks_parallel(self):
        from icecode.agent.engine_tool_guard import _should_parallelize_tool_batch
        tc1 = self._make_tc("web_search")
        tc2 = self._make_tc("run_terminal")  # not in PARALLEL_SAFE_TOOLS
        assert not _should_parallelize_tool_batch([tc1, tc2])

    def test_independent_read_files_parallel(self):
        from icecode.agent.engine_tool_guard import _should_parallelize_tool_batch
        tc1 = self._make_tc("read_file", {"path": "/tmp/a.txt"})
        tc2 = self._make_tc("read_file", {"path": "/tmp/b.txt"})
        assert _should_parallelize_tool_batch([tc1, tc2])

    def test_same_path_read_files_not_parallel(self):
        from icecode.agent.engine_tool_guard import _should_parallelize_tool_batch
        tc1 = self._make_tc("read_file", {"path": "/tmp/same.txt"})
        tc2 = self._make_tc("read_file", {"path": "/tmp/same.txt"})
        assert not _should_parallelize_tool_batch([tc1, tc2])


class TestExtractParallelScopePath:
    def test_absolute_path_returned(self):
        from icecode.agent.engine_tool_guard import _extract_parallel_scope_path
        result = _extract_parallel_scope_path("read_file", {"path": "/tmp/test.txt"})
        assert result is not None
        assert str(result) == "/tmp/test.txt"

    def test_non_scoped_tool_returns_none(self):
        from icecode.agent.engine_tool_guard import _extract_parallel_scope_path
        result = _extract_parallel_scope_path("web_search", {"query": "test"})
        assert result is None

    def test_empty_path_returns_none(self):
        from icecode.agent.engine_tool_guard import _extract_parallel_scope_path
        result = _extract_parallel_scope_path("read_file", {"path": ""})
        assert result is None

    def test_missing_path_returns_none(self):
        from icecode.agent.engine_tool_guard import _extract_parallel_scope_path
        result = _extract_parallel_scope_path("read_file", {})
        assert result is None
