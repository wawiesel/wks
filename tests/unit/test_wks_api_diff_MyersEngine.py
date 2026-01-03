"""Unit tests for wks.api.diff.MyersEngine."""

import pytest

from wks.api.diff.MyersEngine import MyersEngine


@pytest.fixture
def engine():
    return MyersEngine()


def test_is_text_file_valid_utf8(engine, tmp_path):
    """Test _is_text_file with valid UTF-8 file."""
    f = tmp_path / "test.txt"
    f.write_text("Hello World", encoding="utf-8")
    assert engine._is_text_file(f) is True


def test_is_text_file_valid_ascii(engine, tmp_path):
    """Test _is_text_file with valid ASCII file."""
    f = tmp_path / "test.txt"
    f.write_text("Hello World", encoding="ascii")
    assert engine._is_text_file(f) is True


def test_is_text_file_binary(engine, tmp_path):
    """Test _is_text_file with binary file (null byte)."""
    f = tmp_path / "binary.bin"
    f.write_bytes(b"Hello\x00World")
    assert engine._is_text_file(f) is False


def test_diff_identical_files(engine, tmp_path):
    """Test diff with identical files."""
    f1 = tmp_path / "f1.txt"
    f2 = tmp_path / "f2.txt"
    f1.write_text("content")
    f2.write_text("content")

    result = engine.diff(f1, f2, {})
    assert result == "Files are identical"


def test_diff_different_files(engine, tmp_path):
    """Test diff with different files."""
    f1 = tmp_path / "f1.txt"
    f2 = tmp_path / "f2.txt"
    f1.write_text("line1\nline2")
    f2.write_text("line1\nline3")

    result = engine.diff(f1, f2, {})
    assert "line2" in result
    assert "line3" in result
    assert "diff" in result or "@@" in result  # Check for some diff output characteristic


def test_diff_non_text_error(engine, tmp_path):
    """Test diff raises ValueError for non-text files."""
    f1 = tmp_path / "f1.bin"
    f2 = tmp_path / "f2.txt"
    f1.write_bytes(b"\x00")
    f2.write_text("text")

    with pytest.raises(ValueError, match="is not a text file"):
        engine.diff(f1, f2, {})


def test_diff_options_context_lines(engine, tmp_path):
    """Test diff respects context_lines option."""
    # Create files with enough common lines to test context
    lines = ["a", "b", "c", "d", "e", "f"]
    f1 = tmp_path / "f1.txt"
    f2 = tmp_path / "f2.txt"
    f1.write_text("\n".join(lines))

    lines_mod = list(lines)
    lines_mod[2] = "MODIFIED"
    f2.write_text("\n".join(lines_mod))

    # With 0 context lines, we shouldn't see surrounding lines
    result = engine.diff(f1, f2, {"context_lines": 0})
    assert "MODIFIED" in result
    assert "b" not in result  # Surrounding line
    assert "d" not in result  # Surrounding line
