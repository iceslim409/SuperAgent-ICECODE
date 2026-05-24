"""Unit tests for engine_multimodal — multimodal result helpers."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "core"))


class TestIsMultimodalToolResult:
    def test_valid_multimodal_envelope(self):
        from icecode.agent.engine_multimodal import _is_multimodal_tool_result
        val = {"_multimodal": True, "content": [{"type": "text", "text": "ok"}]}
        assert _is_multimodal_tool_result(val) is True

    def test_plain_string_is_not_multimodal(self):
        from icecode.agent.engine_multimodal import _is_multimodal_tool_result
        assert _is_multimodal_tool_result("hello") is False

    def test_dict_without_flag_is_not_multimodal(self):
        from icecode.agent.engine_multimodal import _is_multimodal_tool_result
        assert _is_multimodal_tool_result({"content": []}) is False

    def test_none_is_not_multimodal(self):
        from icecode.agent.engine_multimodal import _is_multimodal_tool_result
        assert _is_multimodal_tool_result(None) is False


class TestMultimodalTextSummary:
    def test_string_returned_as_is(self):
        from icecode.agent.engine_multimodal import _multimodal_text_summary
        assert _multimodal_text_summary("hello") == "hello"

    def test_uses_text_summary_if_present(self):
        from icecode.agent.engine_multimodal import _multimodal_text_summary
        val = {"_multimodal": True, "content": [], "text_summary": "short summary"}
        assert _multimodal_text_summary(val) == "short summary"

    def test_extracts_text_parts(self):
        from icecode.agent.engine_multimodal import _multimodal_text_summary
        val = {
            "_multimodal": True,
            "content": [
                {"type": "text", "text": "line one"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
                {"type": "text", "text": "line two"},
            ]
        }
        result = _multimodal_text_summary(val)
        assert "line one" in result
        assert "line two" in result

    def test_no_text_parts_returns_placeholder(self):
        from icecode.agent.engine_multimodal import _multimodal_text_summary
        val = {
            "_multimodal": True,
            "content": [{"type": "image_url", "image_url": {"url": "x"}}]
        }
        result = _multimodal_text_summary(val)
        assert "multimodal" in result

    def test_dict_serialized_as_json(self):
        from icecode.agent.engine_multimodal import _multimodal_text_summary
        result = _multimodal_text_summary({"key": "value"})
        assert "key" in result


class TestAppendSubdirHintToMultimodal:
    def test_hint_added_to_text_part(self):
        from icecode.agent.engine_multimodal import _append_subdir_hint_to_multimodal
        val = {
            "_multimodal": True,
            "content": [{"type": "text", "text": "original"}],
            "text_summary": "original",
        }
        _append_subdir_hint_to_multimodal(val, " [hint]")
        assert "[hint]" in val["content"][0]["text"]
        assert "[hint]" in val["text_summary"]

    def test_non_multimodal_noop(self):
        from icecode.agent.engine_multimodal import _append_subdir_hint_to_multimodal
        val = "plain string"
        _append_subdir_hint_to_multimodal(val, " hint")
        assert val == "plain string"  # unchanged

    def test_hint_inserted_when_no_text_part(self):
        from icecode.agent.engine_multimodal import _append_subdir_hint_to_multimodal
        val = {
            "_multimodal": True,
            "content": [{"type": "image_url", "image_url": {"url": "x"}}],
        }
        _append_subdir_hint_to_multimodal(val, " [dir]")
        text_parts = [p for p in val["content"] if p.get("type") == "text"]
        assert len(text_parts) == 1
        assert "[dir]" in text_parts[0]["text"]


class TestExtractErrorPreview:
    def test_none_returns_empty(self):
        from icecode.agent.engine_multimodal import _extract_error_preview
        assert _extract_error_preview(None) == ""

    def test_plain_string_truncated(self):
        from icecode.agent.engine_multimodal import _extract_error_preview
        long = "x" * 300
        result = _extract_error_preview(long)
        assert len(result) <= 181  # max_len + ellipsis
        assert result.endswith("…")

    def test_json_error_field_extracted(self):
        from icecode.agent.engine_multimodal import _extract_error_preview
        import json
        result = _extract_error_preview(json.dumps({"success": False, "error": "File not found"}))
        assert "File not found" in result

    def test_whitespace_collapsed(self):
        from icecode.agent.engine_multimodal import _extract_error_preview
        result = _extract_error_preview("line one\n\nline   two")
        assert "\n" not in result
        assert "line one" in result


class TestTrajectoryNormalizeMsg:
    def test_regular_message_unchanged(self):
        from icecode.agent.engine_multimodal import _trajectory_normalize_msg
        msg = {"role": "user", "content": "hello"}
        result = _trajectory_normalize_msg(msg)
        assert result["content"] == "hello"

    def test_multimodal_content_replaced_with_summary(self):
        from icecode.agent.engine_multimodal import _trajectory_normalize_msg
        msg = {
            "role": "tool",
            "content": {
                "_multimodal": True,
                "content": [{"type": "text", "text": "screenshot text"}],
                "text_summary": "summary here",
            }
        }
        result = _trajectory_normalize_msg(msg)
        assert result["content"] == "summary here"

    def test_image_parts_replaced_with_placeholder(self):
        from icecode.agent.engine_multimodal import _trajectory_normalize_msg
        msg = {
            "role": "user",
            "content": [
                {"type": "text", "text": "describe this"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
            ]
        }
        result = _trajectory_normalize_msg(msg)
        types = [p["type"] for p in result["content"]]
        assert "image_url" not in types
        assert any(p.get("text") == "[screenshot]" for p in result["content"])

    def test_non_dict_returned_as_is(self):
        from icecode.agent.engine_multimodal import _trajectory_normalize_msg
        assert _trajectory_normalize_msg("string") == "string"
        assert _trajectory_normalize_msg(42) == 42
