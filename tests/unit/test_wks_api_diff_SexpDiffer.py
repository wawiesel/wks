"""Unit tests for wks.api.diff.SexpDiffer module.

Requirements:
- WKS-DIFF-001
- WKS-DIFF-003
- WKS-DIFF-005
"""

import pytest

from wks.api.diff.SexpDiffer import SexpDiffer

pytestmark = pytest.mark.unit


class TestSexpDiffer:
    """Test SexpDiffer class."""

    def test_diff_identical_sexp(self, tmp_path):
        """Test diff with identical S-expression files."""
        file_a = tmp_path / "a.sexp"
        file_b = tmp_path / "b.sexp"
        content = "(module (function (name hello)))"
        file_a.write_text(content)
        file_b.write_text(content)

        engine = SexpDiffer()
        result = engine.diff(file_a, file_b, {})
        assert "no structural changes" in result.lower()

    def test_diff_different_sexp(self, tmp_path):
        """Test diff with different S-expression files."""
        file_a = tmp_path / "a.sexp"
        file_b = tmp_path / "b.sexp"
        file_a.write_text("(module (function (name hello)))")
        file_b.write_text("(module (function (name world)))")

        engine = SexpDiffer()
        result = engine.diff(file_a, file_b, {})
        assert isinstance(result, str)
        assert len(result) > 0
        assert "hello" in result or "world" in result

    def test_diff_invalid_extension(self, tmp_path):
        """Test diff fails with non-.sexp files."""
        file_a = tmp_path / "a.py"
        file_b = tmp_path / "b.py"
        file_a.write_text("(module)")
        file_b.write_text("(module)")

        engine = SexpDiffer()
        with pytest.raises(ValueError, match=r"requires.*sexp"):
            engine.diff(file_a, file_b, {})

    def test_diff_non_utf8_encoding(self, tmp_path):
        """Test diff fails with non-UTF-8 encoding."""
        file_a = tmp_path / "a.sexp"
        file_b = tmp_path / "b.sexp"
        # Write binary data that's not valid UTF-8
        file_a.write_bytes(b"\xff\xfe\x00\x00")  # Invalid UTF-8
        file_b.write_text("(module)")

        engine = SexpDiffer()
        with pytest.raises((ValueError, RuntimeError), match="UTF-8"):
            engine.diff(file_a, file_b, {})

    def test_diff_file2_invalid_extension(self, tmp_path):
        """Test diff fails when file2 is not *.sexp."""
        file_a = tmp_path / "a.sexp"
        file_b = tmp_path / "b.txt"
        file_a.write_text("(module)")
        file_b.write_text("text")

        engine = SexpDiffer()
        with pytest.raises(ValueError, match=r"requires.*sexp"):
            engine.diff(file_a, file_b, {})

    def test_diff_read_error_handling(self, tmp_path):
        """Test diff handles file read errors."""
        file_a = tmp_path / "a.sexp"
        file_b = tmp_path / "b.sexp"
        file_a.write_text("(module)")

        # Remove file_b to cause read error
        file_b.write_text("(module)")
        file_b.unlink()

        engine = SexpDiffer()
        with pytest.raises(RuntimeError, match="Failed to read files"):
            engine.diff(file_a, file_b, {})
