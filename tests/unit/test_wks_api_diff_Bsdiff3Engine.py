"""Unit tests for wks.api.diff.Bsdiff3Engine module."""

import pytest

from wks.api.diff.Bsdiff3Engine import BSDIFF4_AVAILABLE, Bsdiff3Engine

pytestmark = pytest.mark.unit


class TestBsdiff3Engine:
    """Test Bsdiff3Engine class."""

    def test_diff_identical_files(self, tmp_path):
        """Test diff with identical binary files."""
        file_a = tmp_path / "a.bin"
        file_b = tmp_path / "b.bin"
        content = b"binary data"
        file_a.write_bytes(content)
        file_b.write_bytes(content)

        engine = Bsdiff3Engine()
        result = engine.diff(file_a, file_b, {})
        assert "identical" in result.lower()

    def test_diff_different_files(self, tmp_path):
        """Test diff with different binary files."""
        file_a = tmp_path / "a.bin"
        file_b = tmp_path / "b.bin"
        file_a.write_bytes(b"binary data 1")
        file_b.write_bytes(b"binary data 2")

        if not BSDIFF4_AVAILABLE:
            pytest.skip("bsdiff4 package not available")

        engine = Bsdiff3Engine()
        result = engine.diff(file_a, file_b, {})
        assert "patch" in result.lower()
        assert "bytes" in result.lower()

    def test_diff_missing_bsdiff4(self, tmp_path, monkeypatch):
        """Test diff fails when bsdiff4 is not available."""
        file_a = tmp_path / "a.bin"
        file_b = tmp_path / "b.bin"
        file_a.write_bytes(b"data1")
        file_b.write_bytes(b"data2")

        # Mock BSDIFF4_AVAILABLE to False
        monkeypatch.setattr("wks.api.diff.Bsdiff3Engine.BSDIFF4_AVAILABLE", False)

        engine = Bsdiff3Engine()
        with pytest.raises(RuntimeError, match="bsdiff4 package is required"):
            engine.diff(file_a, file_b, {})

    def test_diff_read_error(self, tmp_path):
        """Test diff handles file read errors."""
        file_a = tmp_path / "a.bin"
        file_b = tmp_path / "nonexistent.bin"
        file_a.write_bytes(b"data")

        if not BSDIFF4_AVAILABLE:
            pytest.skip("bsdiff4 package not available")

        engine = Bsdiff3Engine()
        with pytest.raises(RuntimeError, match="Failed to read files"):
            engine.diff(file_a, file_b, {})

    def test_diff_patch_generation(self, tmp_path):
        """Test diff generates patch for different files."""
        file_a = tmp_path / "a.bin"
        file_b = tmp_path / "b.bin"
        file_a.write_bytes(b"old" * 100)
        file_b.write_bytes(b"new" * 100)

        if not BSDIFF4_AVAILABLE:
            pytest.skip("bsdiff4 package not available")

        engine = Bsdiff3Engine()
        result = engine.diff(file_a, file_b, {})
        assert "patch size" in result.lower()
        assert "compression ratio" in result.lower()

    def test_diff_large_files(self, tmp_path):
        """Test diff handles large binary files."""
        file_a = tmp_path / "a.bin"
        file_b = tmp_path / "b.bin"
        # Create files with different sizes
        file_a.write_bytes(b"x" * 10000)
        file_b.write_bytes(b"y" * 10000)

        if not BSDIFF4_AVAILABLE:
            pytest.skip("bsdiff4 package not available")

        engine = Bsdiff3Engine()
        result = engine.diff(file_a, file_b, {})
        assert isinstance(result, str)
        assert len(result) > 0
