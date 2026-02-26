"""Unit tests for wks.api.diff.cmd_diff module.

Requirements:
- WKS-DIFF-001
- WKS-DIFF-002
- WKS-DIFF-003
"""

import tempfile
from pathlib import Path

import pytest

from tests.unit.conftest import run_cmd
from wks.api.diff.cmd_diff import cmd_diff

pytestmark = pytest.mark.unit


class TestCmdDiff:
    """Test cmd_diff function."""

    def test_cmd_diff_success_myers(self, tmp_path):
        """Test cmd_diff succeeds with myers engine for text files."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("hello\nworld\n")
        file_b.write_text("hello\nuniverse\n")

        config = {
            "engine_config": {"engine": "myers"},
            "timeout_seconds": 60,
            "max_size_mb": 100,
        }

        result = run_cmd(cmd_diff, config, str(file_a), str(file_b))
        assert result.success
        assert result.output["status"] == "success"
        assert result.output["metadata"]["engine_used"] == "myers"
        assert result.output["diff_output"] is not None

    def test_cmd_diff_success_identical_files(self, tmp_path):
        """Test cmd_diff succeeds with identical files."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        content = "identical content\n"
        file_a.write_text(content)
        file_b.write_text(content)

        config = {
            "engine_config": {"engine": "myers"},
            "timeout_seconds": 60,
            "max_size_mb": 100,
        }

        result = run_cmd(cmd_diff, config, str(file_a), str(file_b))
        assert result.success
        assert result.output["status"] == "success"
        assert result.output["metadata"]["is_identical"] is True
        assert result.output["metadata"]["engine_used"] == "myers"

    def test_cmd_diff_success_sexp(self, tmp_path):
        """Test cmd_diff succeeds with sexp engine for S-expression files."""
        file_a = tmp_path / "a.sexp"
        file_b = tmp_path / "b.sexp"
        file_a.write_text("(module (function (name hello)))")
        file_b.write_text("(module (function (name world)))")

        config = {
            "engine_config": {"engine": "sexp"},
            "timeout_seconds": 60,
            "max_size_mb": 100,
        }

        result = run_cmd(cmd_diff, config, str(file_a), str(file_b))
        assert result.success
        assert result.output["status"] == "success"
        assert result.output["metadata"]["engine_used"] == "sexp"

    def test_cmd_diff_failure_missing_config(self):
        """Test cmd_diff fails with missing config."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            file_a = f.name
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            file_b = f.name

        try:
            result = run_cmd(cmd_diff, None, file_a, file_b)
            assert not result.success
            assert "config must be a dict" in result.output["error_details"]["errors"][0]
        finally:
            Path(file_a).unlink(missing_ok=True)
            Path(file_b).unlink(missing_ok=True)

    def test_cmd_diff_failure_missing_engine_config(self):
        """Test cmd_diff fails with missing engine_config."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            file_a = f.name
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            file_b = f.name

        try:
            config = {"timeout_seconds": 60, "max_size_mb": 100}
            result = run_cmd(cmd_diff, config, file_a, file_b)
            assert not result.success
            assert "config.engine_config is required" in result.output["error_details"]["errors"][0]
        finally:
            Path(file_a).unlink(missing_ok=True)
            Path(file_b).unlink(missing_ok=True)

    def test_cmd_diff_failure_invalid_engine(self):
        """Test cmd_diff fails with invalid engine name."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            file_a = f.name
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            file_b = f.name

        try:
            config = {
                "engine_config": {"engine": "invalid_engine"},
                "timeout_seconds": 60,
                "max_size_mb": 100,
            }
            result = run_cmd(cmd_diff, config, file_a, file_b)
            assert not result.success
            assert "must be one of auto,bsdiff3,myers,sexp,semantic" in result.output["error_details"]["errors"][0]
        finally:
            Path(file_a).unlink(missing_ok=True)
            Path(file_b).unlink(missing_ok=True)

    def test_cmd_diff_failure_missing_target_a(self):
        """Test cmd_diff fails with missing target_a."""
        config = {
            "engine_config": {"engine": "myers"},
            "timeout_seconds": 60,
            "max_size_mb": 100,
        }
        result = run_cmd(cmd_diff, config, "", "some_file")
        assert not result.success
        assert "target_a is required" in result.output["error_details"]["errors"][0]

    def test_cmd_diff_failure_missing_target_b(self):
        """Test cmd_diff fails with missing target_b."""
        config = {
            "engine_config": {"engine": "myers"},
            "timeout_seconds": 60,
            "max_size_mb": 100,
        }
        result = run_cmd(cmd_diff, config, "some_file", "")
        assert not result.success
        assert "target_b is required" in result.output["error_details"]["errors"][0]

    def test_cmd_diff_failure_file_not_found(self, tmp_path):
        """Test cmd_diff fails when files don't exist."""
        config = {
            "engine_config": {"engine": "myers"},
            "timeout_seconds": 60,
            "max_size_mb": 100,
        }
        result = run_cmd(cmd_diff, config, str(tmp_path / "nonexistent_a.txt"), str(tmp_path / "nonexistent_b.txt"))
        assert not result.success
        assert "not found" in result.output["error_details"]["errors"][0].lower()

    def test_cmd_diff_failure_invalid_timeout(self):
        """Test cmd_diff fails with invalid timeout_seconds."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            file_a = f.name
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            file_b = f.name

        try:
            config = {
                "engine_config": {"engine": "myers"},
                "timeout_seconds": -1,
                "max_size_mb": 100,
            }
            result = run_cmd(cmd_diff, config, file_a, file_b)
            assert not result.success
            assert "timeout_seconds must be a positive int" in result.output["error_details"]["errors"][0]
        finally:
            Path(file_a).unlink(missing_ok=True)
            Path(file_b).unlink(missing_ok=True)

    def test_cmd_diff_failure_invalid_max_size(self):
        """Test cmd_diff fails with invalid max_size_mb."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            file_a = f.name
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            file_b = f.name

        try:
            config = {
                "engine_config": {"engine": "myers"},
                "timeout_seconds": 60,
                "max_size_mb": 0,
            }
            result = run_cmd(cmd_diff, config, file_a, file_b)
            assert not result.success
            assert "max_size_mb must be a positive int" in result.output["error_details"]["errors"][0]
        finally:
            Path(file_a).unlink(missing_ok=True)
            Path(file_b).unlink(missing_ok=True)

    def test_cmd_diff_failure_file_too_large(self, tmp_path):
        """Test cmd_diff fails when files exceed max_size_mb."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        # Create files larger than 1MB
        large_content = "x" * (2 * 1024 * 1024)
        file_a.write_text(large_content)
        file_b.write_text(large_content)

        config = {
            "engine_config": {"engine": "myers"},
            "timeout_seconds": 60,
            "max_size_mb": 1,  # 1MB limit
        }

        result = run_cmd(cmd_diff, config, str(file_a), str(file_b))
        assert not result.success
        assert "exceeds max_size_mb" in result.output["error_details"]["errors"][0]

    def test_cmd_diff_myers_with_options(self, tmp_path):
        """Test cmd_diff with myers engine and custom options."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("hello\nworld\n")
        file_b.write_text("hello\nuniverse\n")

        config = {
            "engine_config": {
                "engine": "myers",
                "context_lines": 5,
                "ignore_whitespace": True,
            },
            "timeout_seconds": 60,
            "max_size_mb": 100,
        }

        result = run_cmd(cmd_diff, config, str(file_a), str(file_b))
        assert result.success
        assert result.output["status"] == "success"

    def test_cmd_diff_success_bsdiff3(self, tmp_path):
        """Test cmd_diff succeeds with bsdiff3 engine for binary files."""
        file_a = tmp_path / "a.bin"
        file_b = tmp_path / "b.bin"
        file_a.write_bytes(b"binary data 1")
        file_b.write_bytes(b"binary data 2")

        config = {
            "engine_config": {"engine": "bsdiff3"},
            "timeout_seconds": 60,
            "max_size_mb": 100,
        }

        result = run_cmd(cmd_diff, config, str(file_a), str(file_b))
        assert result.success
        assert result.output["status"] == "success"
        assert result.output["metadata"]["engine_used"] == "bsdiff3"

    def test_cmd_diff_success_semantic_text(self, tmp_path, monkeypatch):
        """Test cmd_diff succeeds with semantic engine for text files."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("hello world\nfission data\n")
        file_b.write_text("hello universe\nfission dataset\n")

        import numpy as np

        def _fake_embed(self, units, model_name):
            if "world" in units[0]:
                return np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
            return np.array([[0.95, 0.1], [0.05, 0.99]], dtype=np.float32)

        monkeypatch.setattr("wks.api.diff.SemanticDiffEngine.SemanticDiffEngine._embed_text_units", _fake_embed)

        config = {
            "engine_config": {
                "engine": "semantic",
                "modified_threshold": 0.6,
                "unchanged_threshold": 0.95,
            },
            "timeout_seconds": 60,
            "max_size_mb": 100,
        }

        result = run_cmd(cmd_diff, config, str(file_a), str(file_b))
        assert result.success
        assert result.output["status"] == "success"
        assert result.output["metadata"]["engine_used"] == "semantic"
        assert result.output["diff_output"] is not None
