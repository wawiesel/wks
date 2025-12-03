"""Tests for DoclingEngine."""

import pytest
import subprocess
from pathlib import Path
from unittest.mock import patch, Mock
from wks.transform.engines import DoclingEngine


class TestDoclingEngine:
    """Test DoclingEngine."""

    def test_get_extension_default(self):
        """DoclingEngine returns default extension."""
        engine = DoclingEngine()

        ext = engine.get_extension({})

        assert ext == "md"

    def test_get_extension_custom(self):
        """DoclingEngine returns custom extension."""
        engine = DoclingEngine()

        ext = engine.get_extension({"write_extension": "txt"})

        assert ext == "txt"

    def test_compute_options_hash(self):
        """DoclingEngine computes consistent options hash."""
        engine = DoclingEngine()

        hash1 = engine.compute_options_hash({"ocr": True, "timeout_secs": 30})
        hash2 = engine.compute_options_hash({"timeout_secs": 30, "ocr": True})

        assert hash1 == hash2  # Order doesn't matter
        assert len(hash1) == 16  # Truncated to 16 chars

    @patch("subprocess.run")
    def test_transform_success(self, mock_run, tmp_path):
        """DoclingEngine transforms successfully."""
        engine = DoclingEngine()

        input_path = tmp_path / "test.pdf"
        input_path.write_bytes(b"PDF content")

        output_path = tmp_path / "output.md"

        # The DoclingEngine creates a temp directory and expects docling to write to it.
        # We need to intercept the subprocess.run call, find the temp directory argument,
        # and create the output file there.

        def create_output(cmd, *args, **kwargs):
            # cmd is like ["docling", input_path, "--to", "md", "--output", temp_dir]
            # Find output dir (it's after --output)
            try:
                output_idx = cmd.index("--output")
                temp_dir = Path(cmd[output_idx + 1])
                # Create the expected output file: <input_stem>.md
                expected_file = temp_dir / f"{input_path.stem}.md"
                expected_file.write_text("# Transformed\n\nContent")
            except (ValueError, IndexError):
                pass
            return Mock(stdout="Done", returncode=0)

        mock_run.side_effect = create_output

        engine.transform(input_path, output_path, {"ocr": False, "timeout_secs": 30})

        assert output_path.exists()
        assert "Transformed" in output_path.read_text()
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_transform_with_ocr(self, mock_run, tmp_path):
        """DoclingEngine includes --ocr flag when OCR is enabled."""
        engine = DoclingEngine()

        input_path = tmp_path / "test.pdf"
        input_path.write_bytes(b"PDF content")

        output_path = tmp_path / "output.md"

        def create_output(cmd, *args, **kwargs):
            try:
                output_idx = cmd.index("--output")
                temp_dir = Path(cmd[output_idx + 1])
                expected_file = temp_dir / f"{input_path.stem}.md"
                expected_file.write_text("# Transformed\n\nContent")
            except (ValueError, IndexError):
                pass
            return Mock(stdout="Done", returncode=0)

        mock_run.side_effect = create_output

        engine.transform(input_path, output_path, {"ocr": True, "timeout_secs": 30})

        # Verify --ocr flag was included
        call_args = mock_run.call_args[0][0]
        assert "--ocr" in call_args

    @patch("subprocess.run")
    def test_transform_timeout(self, mock_run, tmp_path):
        """DoclingEngine raises on timeout."""
        engine = DoclingEngine()

        input_path = tmp_path / "test.pdf"
        input_path.write_bytes(b"PDF content")
        output_path = tmp_path / "output.md"

        # Mock timeout
        mock_run.side_effect = subprocess.TimeoutExpired("docling", 30)

        with pytest.raises(RuntimeError, match="timed out"):
            engine.transform(input_path, output_path, {"timeout_secs": 30})

    @patch("subprocess.run")
    def test_transform_called_process_error(self, mock_run, tmp_path):
        """DoclingEngine raises RuntimeError on CalledProcessError."""
        engine = DoclingEngine()

        input_path = tmp_path / "test.pdf"
        input_path.write_bytes(b"PDF content")
        output_path = tmp_path / "output.md"

        # Mock CalledProcessError
        mock_run.side_effect = subprocess.CalledProcessError(1, "docling", stderr="Error occurred")

        with pytest.raises(RuntimeError, match="Docling failed"):
            engine.transform(input_path, output_path, {})

    @patch("subprocess.run")
    def test_transform_output_file_not_created(self, mock_run, tmp_path):
        """DoclingEngine raises when output file is not created."""
        engine = DoclingEngine()

        input_path = tmp_path / "test.pdf"
        input_path.write_bytes(b"PDF content")
        output_path = tmp_path / "output.md"

        # Mock successful run but no output file
        def create_output(cmd, *args, **kwargs):
            # Don't create the expected file
            return Mock(stdout="Done", returncode=0)

        mock_run.side_effect = create_output

        with pytest.raises(RuntimeError, match="Docling did not create expected output"):
            engine.transform(input_path, output_path, {})

    @patch("subprocess.run")
    def test_transform_general_exception(self, mock_run, tmp_path):
        """DoclingEngine wraps general exceptions."""
        engine = DoclingEngine()

        input_path = tmp_path / "test.pdf"
        input_path.write_bytes(b"PDF content")
        output_path = tmp_path / "output.md"

        # Mock general exception
        mock_run.side_effect = Exception("Unexpected error")

        with pytest.raises(RuntimeError, match="Docling error"):
            engine.transform(input_path, output_path, {})
