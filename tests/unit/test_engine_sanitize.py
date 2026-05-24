"""Unit tests for engine_sanitize — message/string sanitization utilities."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "core"))


class TestSanitizeSurrogates:
    def test_clean_string_unchanged(self):
        from icecode.agent.engine_sanitize import _sanitize_surrogates
        assert _sanitize_surrogates("hello world") == "hello world"

    def test_surrogate_replaced(self):
        from icecode.agent.engine_sanitize import _sanitize_surrogates
        text = "hello \ud800 world"
        result = _sanitize_surrogates(text)
        assert "\ud800" not in result
        assert "hello" in result
        assert "world" in result

    def test_empty_string(self):
        from icecode.agent.engine_sanitize import _sanitize_surrogates
        assert _sanitize_surrogates("") == ""


class TestSanitizeStructureSurrogates:
    def test_no_surrogates_returns_false(self):
        from icecode.agent.engine_sanitize import _sanitize_structure_surrogates
        payload = {"key": "clean text", "nested": {"a": "fine"}}
        assert _sanitize_structure_surrogates(payload) is False

    def test_surrogate_in_dict_value_replaced(self):
        from icecode.agent.engine_sanitize import _sanitize_structure_surrogates
        payload = {"key": "bad \ud800 text"}
        changed = _sanitize_structure_surrogates(payload)
        assert changed is True
        assert "\ud800" not in payload["key"]

    def test_surrogate_in_list(self):
        from icecode.agent.engine_sanitize import _sanitize_structure_surrogates
        payload = ["ok", "bad \udfff"]
        changed = _sanitize_structure_surrogates(payload)
        assert changed is True
        assert "\udfff" not in payload[1]


class TestSanitizeMessagesSurrogates:
    def test_clean_messages_returns_false(self):
        from icecode.agent.engine_sanitize import _sanitize_messages_surrogates
        msgs = [{"role": "user", "content": "hello"}]
        assert _sanitize_messages_surrogates(msgs) is False

    def test_surrogate_in_content_fixed(self):
        from icecode.agent.engine_sanitize import _sanitize_messages_surrogates
        msgs = [{"role": "user", "content": "text \ud800 here"}]
        changed = _sanitize_messages_surrogates(msgs)
        assert changed is True
        assert "\ud800" not in msgs[0]["content"]

    def test_surrogate_in_tool_call_arguments(self):
        from icecode.agent.engine_sanitize import _sanitize_messages_surrogates
        msgs = [{
            "role": "assistant",
            "tool_calls": [{"id": "tc1", "function": {"name": "f", "arguments": '{"a": "\ud800"}'}}]
        }]
        changed = _sanitize_messages_surrogates(msgs)
        assert changed is True


class TestEscapeInvalidCharsInJsonStrings:
    def test_clean_json_unchanged(self):
        from icecode.agent.engine_sanitize import _escape_invalid_chars_in_json_strings
        raw = '{"key": "value"}'
        assert _escape_invalid_chars_in_json_strings(raw) == raw

    def test_control_char_in_string_escaped(self):
        from icecode.agent.engine_sanitize import _escape_invalid_chars_in_json_strings
        raw = '{"key": "val\tue"}'  # literal tab in string
        result = _escape_invalid_chars_in_json_strings(raw)
        assert "\\u0009" in result or "\t" not in result

    def test_empty_string(self):
        from icecode.agent.engine_sanitize import _escape_invalid_chars_in_json_strings
        assert _escape_invalid_chars_in_json_strings("") == ""


class TestRepairToolCallArguments:
    def test_valid_json_unchanged(self):
        from icecode.agent.engine_sanitize import _repair_tool_call_arguments
        result = _repair_tool_call_arguments('{"path": "/tmp/file.txt"}')
        import json
        assert json.loads(result) == {"path": "/tmp/file.txt"}

    def test_empty_returns_empty_object(self):
        from icecode.agent.engine_sanitize import _repair_tool_call_arguments
        assert _repair_tool_call_arguments("") == "{}"
        assert _repair_tool_call_arguments("   ") == "{}"

    def test_python_none_returns_empty_object(self):
        from icecode.agent.engine_sanitize import _repair_tool_call_arguments
        assert _repair_tool_call_arguments("None") == "{}"

    def test_trailing_comma_fixed(self):
        from icecode.agent.engine_sanitize import _repair_tool_call_arguments
        import json
        result = _repair_tool_call_arguments('{"a": 1,}')
        assert json.loads(result) == {"a": 1}

    def test_unclosed_brace_fixed(self):
        from icecode.agent.engine_sanitize import _repair_tool_call_arguments
        import json
        result = _repair_tool_call_arguments('{"a": 1')
        assert json.loads(result) == {"a": 1}

    def test_unrepairable_returns_empty_object(self):
        from icecode.agent.engine_sanitize import _repair_tool_call_arguments
        result = _repair_tool_call_arguments("not json at all !@#$")
        assert result == "{}"


class TestStripNonAscii:
    def test_ascii_unchanged(self):
        from icecode.agent.engine_sanitize import _strip_non_ascii
        assert _strip_non_ascii("hello world") == "hello world"

    def test_non_ascii_stripped(self):
        from icecode.agent.engine_sanitize import _strip_non_ascii
        assert _strip_non_ascii("héllo") == "hllo"
        assert _strip_non_ascii("café") == "caf"

    def test_empty_string(self):
        from icecode.agent.engine_sanitize import _strip_non_ascii
        assert _strip_non_ascii("") == ""


class TestStripImagesFromMessages:
    def test_no_images_unchanged(self):
        from icecode.agent.engine_sanitize import _strip_images_from_messages
        msgs = [{"role": "user", "content": "hello"}]
        assert _strip_images_from_messages(msgs) is False
        assert msgs[0]["content"] == "hello"

    def test_image_url_part_removed(self):
        from icecode.agent.engine_sanitize import _strip_images_from_messages
        msgs = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "describe this"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
            ]
        }]
        changed = _strip_images_from_messages(msgs)
        assert changed is True
        parts = msgs[0]["content"]
        assert all(p.get("type") != "image_url" for p in parts)

    def test_tool_image_replaced_with_placeholder(self):
        from icecode.agent.engine_sanitize import _strip_images_from_messages
        msgs = [{
            "role": "tool",
            "tool_call_id": "tc1",
            "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}],
        }]
        _strip_images_from_messages(msgs)
        # tool message must survive (for tool_call_id linkage)
        assert len(msgs) == 1
        assert isinstance(msgs[0]["content"], str)

    def test_non_tool_image_only_message_dropped(self):
        from icecode.agent.engine_sanitize import _strip_images_from_messages
        msgs = [
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "x"}}]},
        ]
        _strip_images_from_messages(msgs)
        assert len(msgs) == 0
