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

    def test_diff_file2_not_text(self, tmp_path):
        """Test diff fails when file2 is not text."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.bin"
        file_a.write_text("text")
        file_b.write_bytes(b"binary\x00data")

        engine = MyersEngine()
        with pytest.raises(ValueError, match="not a text file"):
            engine.diff(file_a, file_b, {})

    def test_diff_command_error_handling(self, tmp_path, monkeypatch):
        """Test diff handles diff command errors."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("text1")
        file_b.write_text("text2")

        # Mock subprocess.run to simulate diff command failure (returncode >= 2)
        def mock_run(*args, **kwargs):
            class MockResult:
                returncode = 2
                stdout = ""
                stderr = "diff: error"

            return MockResult()

        monkeypatch.setattr("subprocess.run", mock_run)

        engine = MyersEngine()
        with pytest.raises(RuntimeError, match="diff command failed"):
            engine.diff(file_a, file_b, {})

    def test_diff_exception_handling(self, tmp_path, monkeypatch):
        """Test diff handles unexpected exceptions."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("text1")
        file_b.write_text("text2")

        # Mock subprocess.run to raise unexpected exception
        def mock_run(*args, **kwargs):
            raise OSError("Unexpected error")

        monkeypatch.setattr("subprocess.run", mock_run)

        engine = MyersEngine()
        with pytest.raises(RuntimeError, match="diff error"):
            engine.diff(file_a, file_b, {})

    def test_is_text_file_ascii_fallback(self, tmp_path):
        """Test _is_text_file handles ASCII-only text."""
        file_a = tmp_path / "a.txt"
        file_a.write_text("ASCII only text", encoding="ascii")

        engine = MyersEngine()
        # Access private method via public API (diff will call it)
        result = engine.diff(file_a, file_a, {})
        assert "identical" in result.lower()

    def test_is_text_file_exception_handling(self, tmp_path):
        """Test _is_text_file handles file read exceptions."""
        # Create a file that can't be read (permission denied scenario)
        # We'll test via the public API which calls _is_text_file
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("text")

        # Make file_b unreadable by removing it after creation
        file_b.write_text("text")
        file_b.unlink()

        engine = MyersEngine()
        # Should handle gracefully - will try to read and fail
        # The _is_text_file should return False on exception
        # But diff will try to read file2 and fail, so we expect an error
        with pytest.raises((ValueError, RuntimeError)):
            engine.diff(file_a, file_b, {})
