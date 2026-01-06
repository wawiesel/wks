"""Unit tests for wks.api.diff.MyersEngine module.

Requirements:
- WKS-DIFF-001
- WKS-DIFF-003
"""

import pytest

from wks.api.diff.MyersEngine import MyersEngine

pytestmark = pytest.mark.unit


class TestMyersEngine:
    """Test MyersEngine class."""

    def test_diff_identical_files(self, tmp_path):
        """Test diff with identical files."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        content = "identical content\n"
        file_a.write_text(content)
        file_b.write_text(content)

        engine = MyersEngine()
        result = engine.diff(file_a, file_b, {})
        assert "identical" in result.lower()

    def test_diff_different_files(self, tmp_path):
        """Test diff with different files."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("hello\nworld\n")
        file_b.write_text("hello\nuniverse\n")

        engine = MyersEngine()
        result = engine.diff(file_a, file_b, {})
        assert "world" in result or "universe" in result
        assert isinstance(result, str)

    def test_diff_with_context_lines(self, tmp_path):
        """Test diff with custom context_lines option."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("line1\nline2\nline3\nline4\nline5\n")
        file_b.write_text("line1\nline2_modified\nline3\nline4\nline5\n")

        engine = MyersEngine()
        result_default = engine.diff(file_a, file_b, {})
        result_custom = engine.diff(file_a, file_b, {"context_lines": 10})
        assert isinstance(result_default, str)
        assert isinstance(result_custom, str)

    def test_diff_binary_file_fails(self, tmp_path):
        """Test diff fails with binary file."""
        file_a = tmp_path / "a.bin"
        file_b = tmp_path / "b.bin"
        file_a.write_bytes(b"binary\x00data")
        file_b.write_bytes(b"binary\x00data2")

        engine = MyersEngine()
        with pytest.raises(ValueError, match="not a text file"):
            engine.diff(file_a, file_b, {})

    def test_diff_utf8_text(self, tmp_path):
        """Test diff handles UTF-8 text files."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("Hello 世界\n", encoding="utf-8")
        file_b.write_text("Hello 宇宙\n", encoding="utf-8")

        engine = MyersEngine()
        result = engine.diff(file_a, file_b, {})
        assert isinstance(result, str)

    def test_diff_empty_files(self, tmp_path):
        """Test diff handles empty text files."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("")
        file_b.write_text("")

        engine = MyersEngine()
        result = engine.diff(file_a, file_b, {})
        assert "identical" in result.lower()
