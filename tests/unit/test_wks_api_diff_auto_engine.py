"""Unit tests for wks.api.diff._auto_engine module."""

import pytest

from wks.api.diff._auto_engine import select_auto_diff_engine

pytestmark = pytest.mark.unit


class TestAutoEngine:
    """Test auto engine selection."""

    def test_select_sexp_for_sexp_files(self, tmp_path):
        """Test auto selects sexp engine for *.sexp files."""
        file1 = tmp_path / "a.sexp"
        file2 = tmp_path / "b.sexp"
        file1.write_text("(module)")
        file2.write_text("(module)")

        engine = select_auto_diff_engine(file1, file2)
        assert engine == "sexp"

    def test_select_myers_for_text_files(self, tmp_path):
        """Test auto selects myers engine for text files."""
        file1 = tmp_path / "a.txt"
        file2 = tmp_path / "b.txt"
        file1.write_text("hello world")
        file2.write_text("hello universe")

        engine = select_auto_diff_engine(file1, file2)
        assert engine == "myers"

    def test_select_bsdiff3_for_binary_files(self, tmp_path):
        """Test auto selects bsdiff3 engine for binary files."""
        file1 = tmp_path / "a.bin"
        file2 = tmp_path / "b.bin"
        file1.write_bytes(b"binary\x00data")
        file2.write_bytes(b"binary\x00data2")

        engine = select_auto_diff_engine(file1, file2)
        assert engine == "bsdiff3"

    def test_select_myers_for_utf8_text(self, tmp_path):
        """Test auto selects myers for UTF-8 text files."""
        file1 = tmp_path / "a.txt"
        file2 = tmp_path / "b.txt"
        file1.write_text("Hello 世界", encoding="utf-8")
        file2.write_text("Hello 宇宙", encoding="utf-8")

        engine = select_auto_diff_engine(file1, file2)
        assert engine == "myers"

    def test_select_bsdiff3_for_non_utf8_text(self, tmp_path):
        """Test auto selects bsdiff3 for non-UTF-8 text."""
        file1 = tmp_path / "a.txt"
        file2 = tmp_path / "b.txt"
        # Write Latin-1 encoded text (not UTF-8)
        file1.write_bytes(b"hello\xe9")  # é in Latin-1
        file2.write_bytes(b"hello\xe8")  # è in Latin-1

        engine = select_auto_diff_engine(file1, file2)
        assert engine == "bsdiff3"

    def test_select_bsdiff3_for_mixed_text_binary(self, tmp_path):
        """Test auto selects bsdiff3 when one file is text and other is binary."""
        file1 = tmp_path / "a.txt"
        file2 = tmp_path / "b.bin"
        file1.write_text("text")
        file2.write_bytes(b"binary\x00data")

        engine = select_auto_diff_engine(file1, file2)
        assert engine == "bsdiff3"

    def test_select_myers_for_empty_text_files(self, tmp_path):
        """Test auto selects myers for empty text files."""
        file1 = tmp_path / "a.txt"
        file2 = tmp_path / "b.txt"
        file1.write_text("")
        file2.write_text("")

        engine = select_auto_diff_engine(file1, file2)
        assert engine == "myers"

    def test_select_bsdiff3_for_nonexistent_file(self, tmp_path):
        """Test auto handles nonexistent file gracefully."""
        file1 = tmp_path / "a.txt"
        file2 = tmp_path / "nonexistent.txt"
        file1.write_text("text")

        # Should handle gracefully and default to binary
        engine = select_auto_diff_engine(file1, file2)
        assert engine == "bsdiff3"

    def test_select_sexp_requires_both_sexp(self, tmp_path):
        """Test sexp engine only selected if both files are *.sexp."""
        file1 = tmp_path / "a.sexp"
        file2 = tmp_path / "b.txt"
        file1.write_text("(module)")
        file2.write_text("text")

        engine = select_auto_diff_engine(file1, file2)
        assert engine != "sexp"
        assert engine in {"myers", "bsdiff3"}
