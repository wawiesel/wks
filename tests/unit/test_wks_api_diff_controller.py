"""Unit tests for wks.api.diff.controller module.

Requirements:
- WKS-DIFF-001
- WKS-DIFF-003
- WKS-DIFF-004
"""

from unittest.mock import MagicMock

import pytest

from wks.api.diff.controller import DiffController
from wks.api.diff.DiffConfig import DiffConfig
from wks.api.diff.DiffEngineConfig import DiffEngineConfig
from wks.api.diff.DiffRouterConfig import DiffRouterConfig

pytestmark = pytest.mark.unit


class TestDiffController:
    """Test DiffController class."""

    def test_controller_init_no_config(self):
        """Test DiffController initialization without config."""
        controller = DiffController()
        assert controller.config is None
        assert controller.transform_controller is None

    def test_controller_init_with_config(self):
        """Test DiffController initialization with config."""
        engines = {
            "myers": DiffEngineConfig(name="myers", enabled=True, is_default=True, options={}),
        }
        router = DiffRouterConfig(rules=[], fallback="text")
        config = DiffConfig(engines=engines, router=router)
        controller = DiffController(config=config)
        assert controller.config == config

    def test_controller_diff_success_myers(self, tmp_path):
        """Test controller.diff succeeds with myers engine."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("hello\nworld\n")
        file_b.write_text("hello\nuniverse\n")

        controller = DiffController()
        result = controller.diff(str(file_a), str(file_b), "myers", {})
        assert "hello" in result
        assert "world" in result or "universe" in result

    def test_controller_diff_success_bsdiff3(self, tmp_path):
        """Test controller.diff succeeds with bsdiff3 engine."""
        file_a = tmp_path / "a.bin"
        file_b = tmp_path / "b.bin"
        file_a.write_bytes(b"binary data 1")
        file_b.write_bytes(b"binary data 2")

        controller = DiffController()
        result = controller.diff(str(file_a), str(file_b), "bsdiff3", {})
        assert "bsdiff" in result.lower() or "patch" in result.lower()

    def test_controller_diff_success_sexp(self, tmp_path):
        """Test controller.diff succeeds with sexp engine."""
        file_a = tmp_path / "a.sexp"
        file_b = tmp_path / "b.sexp"
        file_a.write_text("(module (function (name hello)))")
        file_b.write_text("(module (function (name world)))")

        controller = DiffController()
        result = controller.diff(str(file_a), str(file_b), "sexp", {})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_controller_diff_failure_file_not_found(self, tmp_path):
        """Test controller.diff fails when files don't exist."""
        controller = DiffController()
        with pytest.raises(ValueError, match="File not found"):
            controller.diff(str(tmp_path / "nonexistent_a.txt"), str(tmp_path / "nonexistent_b.txt"), "myers", {})

    def test_controller_diff_failure_unknown_engine(self, tmp_path):
        """Test controller.diff fails with unknown engine."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("hello\n")
        file_b.write_text("world\n")

        controller = DiffController()
        with pytest.raises(ValueError, match="Unknown engine"):
            controller.diff(str(file_a), str(file_b), "unknown_engine", {})

    def test_controller_diff_validation_with_config_disabled_engine(self, tmp_path):
        """Test controller.diff validates against config and fails for disabled engine."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("hello\n")
        file_b.write_text("world\n")

        # Need at least one default engine for DiffConfig validation
        engines = {
            "bsdiff3": DiffEngineConfig(name="bsdiff3", enabled=True, is_default=True, options={}),
            "myers": DiffEngineConfig(name="myers", enabled=False, is_default=False, options={}),
        }
        router = DiffRouterConfig(rules=[], fallback="text")
        config = DiffConfig(engines=engines, router=router)
        controller = DiffController(config=config)

        with pytest.raises(ValueError, match="Unknown engine"):
            controller.diff(str(file_a), str(file_b), "myers", {})

    def test_controller_diff_validation_with_config_enabled_engine(self, tmp_path):
        """Test controller.diff succeeds with enabled engine in config."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("hello\n")
        file_b.write_text("world\n")

        engines = {
            "myers": DiffEngineConfig(name="myers", enabled=True, is_default=True, options={}),
        }
        router = DiffRouterConfig(rules=[], fallback="text")
        config = DiffConfig(engines=engines, router=router)
        controller = DiffController(config=config)

        result = controller.diff(str(file_a), str(file_b), "myers", {})
        assert isinstance(result, str)

    def test_controller_diff_with_checksum_no_transform_controller(self, tmp_path):
        """Test controller.diff fails for checksum without transform_controller."""
        controller = DiffController()
        checksum = "a" * 64  # Valid checksum format
        with pytest.raises(ValueError, match="TransformController required"):
            controller.diff(checksum, checksum, "myers", {})

    def test_controller_diff_with_checksum_and_transform_controller(self, tmp_path):
        """Test controller.diff resolves checksum with transform_controller."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        checksum = "a" * 64
        cache_file = cache_dir / f"{checksum}.md"
        cache_file.write_text("cached content\n")

        mock_transform_controller = MagicMock()
        mock_transform_controller.cache_manager.cache_dir = cache_dir

        controller = DiffController(transform_controller=mock_transform_controller)
        # Should succeed when both targets are the same checksum (identical files)
        result = controller.diff(checksum, checksum, "myers", {})
        assert isinstance(result, str)
