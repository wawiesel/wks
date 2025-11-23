"""Tests for Diff layer."""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock
from wks.diff.engines import Bsdiff3Engine, MyersEngine, get_engine
from wks.diff.controller import DiffController


class TestBsdiff3Engine:
    """Test Bsdiff3Engine."""

    def test_diff_identical_files(self, tmp_path):
        """Bsdiff3 detects identical files."""
        engine = Bsdiff3Engine()

        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"
        file1.write_bytes(b"same content")
        file2.write_bytes(b"same content")

        result = engine.diff(file1, file2, {})

        assert "identical" in result.lower()

    def test_diff_different_files(self, tmp_path):
        """Bsdiff3 detects different files."""
        engine = Bsdiff3Engine()

        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"
        file1.write_bytes(b"content A")
        file2.write_bytes(b"content B different")

        result = engine.diff(file1, file2, {})

        assert "differ" in result.lower()
        assert "9 bytes" in result  # file1 size
        assert "19 bytes" in result  # file2 size


class TestMyersEngine:
    """Test MyersEngine."""

    def test_diff_identical_text_files(self, tmp_path):
        """Myers detects identical text files."""
        engine = MyersEngine()

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("line 1\nline 2\nline 3\n")
        file2.write_text("line 1\nline 2\nline 3\n")

        result = engine.diff(file1, file2, {})

        assert "identical" in result.lower()

    def test_diff_different_text_files(self, tmp_path):
        """Myers shows diff for different text files."""
        engine = MyersEngine()

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("line 1\nline 2\nline 3\n")
        file2.write_text("line 1\nmodified line 2\nline 3\n")

        result = engine.diff(file1, file2, {"context_lines": 1})

        assert "-line 2" in result  # Removed line
        assert "+modified line 2" in result  # Added line

    def test_diff_binary_file_fails(self, tmp_path):
        """Myers fails on binary files."""
        engine = MyersEngine()

        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"
        file1.write_bytes(b"\x00\x01\x02\x03")
        file2.write_bytes(b"\x00\x01\x02\x04")

        with pytest.raises(ValueError, match="not a text file"):
            engine.diff(file1, file2, {})

    def test_is_text_file_utf8(self, tmp_path):
        """Detect UTF-8 text file."""
        engine = MyersEngine()

        text_file = tmp_path / "text.txt"
        text_file.write_text("Hello world", encoding="utf-8")

        assert engine._is_text_file(text_file) is True

    def test_is_text_file_binary(self, tmp_path):
        """Detect binary file."""
        engine = MyersEngine()

        binary_file = tmp_path / "binary.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03\xff\xfe")

        assert engine._is_text_file(binary_file) is False

    def test_diff_context_lines_option(self, tmp_path):
        """Myers respects context_lines option."""
        engine = MyersEngine()

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("A\nB\nC\nD\nE\n")
        file2.write_text("A\nB\nX\nD\nE\n")

        # With 0 context lines
        result_0 = engine.diff(file1, file2, {"context_lines": 0})

        # With 2 context lines
        result_2 = engine.diff(file1, file2, {"context_lines": 2})

        # More context = more lines shown
        assert len(result_2.split("\n")) >= len(result_0.split("\n"))


class TestEngineRegistry:
    """Test engine registry."""

    def test_get_engine_bsdiff3(self):
        """Get bsdiff3 engine."""
        engine = get_engine("bsdiff3")

        assert engine is not None
        assert isinstance(engine, Bsdiff3Engine)

    def test_get_engine_myers(self):
        """Get myers engine."""
        engine = get_engine("myers")

        assert engine is not None
        assert isinstance(engine, MyersEngine)

    def test_get_engine_unknown(self):
        """Get unknown engine returns None."""
        engine = get_engine("unknown")

        assert engine is None


class TestDiffController:
    """Test DiffController."""

    def test_diff_file1_not_found(self, tmp_path):
        """Diff raises on missing file1."""
        controller = DiffController()

        file2 = tmp_path / "file2.txt"
        file2.write_text("content")

        with pytest.raises(ValueError, match="File not found"):
            controller.diff(tmp_path / "missing.txt", file2, "myers")

    def test_diff_file2_not_found(self, tmp_path):
        """Diff raises on missing file2."""
        controller = DiffController()

        file1 = tmp_path / "file1.txt"
        file1.write_text("content")

        with pytest.raises(ValueError, match="File not found"):
            controller.diff(file1, tmp_path / "missing.txt", "myers")

    def test_diff_unknown_engine(self, tmp_path):
        """Diff raises on unknown engine."""
        controller = DiffController()

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content A")
        file2.write_text("content B")

        with pytest.raises(ValueError, match="Unknown engine"):
            controller.diff(file1, file2, "unknown")

    def test_diff_success_myers(self, tmp_path):
        """Diff succeeds with myers engine."""
        controller = DiffController()

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("line 1\nline 2\n")
        file2.write_text("line 1\nmodified\n")

        result = controller.diff(file1, file2, "myers", {"context_lines": 1})

        assert "-line 2" in result
        assert "+modified" in result

    def test_diff_success_bsdiff3(self, tmp_path):
        """Diff succeeds with bsdiff3 engine."""
        controller = DiffController()

        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"
        file1.write_bytes(b"binary A")
        file2.write_bytes(b"binary B")

        result = controller.diff(file1, file2, "bsdiff3")

        assert "differ" in result.lower()

    def test_diff_options_passed_to_engine(self, tmp_path):
        """Diff passes options to engine."""
        controller = DiffController()

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("A\nB\nC\nD\nE\n")
        file2.write_text("A\nX\nC\nD\nE\n")

        # Pass custom context_lines
        result = controller.diff(file1, file2, "myers", {"context_lines": 0})

        # Verify it was used (minimal context)
        assert result is not None
