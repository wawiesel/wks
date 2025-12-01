"""Tests for display infrastructure and priority calculation."""

import pytest
from pathlib import Path

from wks.display.base import Display
from wks.display.cli import CLIDisplay
from wks.display.mcp import MCPDisplay
from wks.display.context import get_display, is_mcp_context
from wks.priority import calculate_priority, find_managed_directory, priority_examples


class TestDisplayInfrastructure:
    """Test display system."""

    def test_get_display_cli(self):
        """Test CLI display instantiation."""
        display = get_display("cli")
        assert isinstance(display, CLIDisplay)

    def test_get_display_mcp(self):
        """Test MCP display instantiation."""
        display = get_display("mcp")
        assert isinstance(display, MCPDisplay)

    def test_display_base_interface(self):
        """Test that both displays implement Display interface."""
        cli = get_display("cli")
        mcp = get_display("mcp")

        # Check key methods exist
        assert hasattr(cli, "status")
        assert hasattr(cli, "success")
        assert hasattr(cli, "error")
        assert hasattr(cli, "table")
        assert hasattr(cli, "progress_start")

        assert hasattr(mcp, "status")
        assert hasattr(mcp, "success")
        assert hasattr(mcp, "error")
        assert hasattr(mcp, "table")
        assert hasattr(mcp, "progress_start")


class TestPriorityCalculation:
    """Test priority calculation algorithm."""

    def test_find_managed_directory(self):
        """Test finding managed directory for a path."""
        managed_dirs = {
            "~/Desktop": 150,
            "~/Documents": 100,
            "~": 100,
        }

        home = Path.home()

        # Test exact match
        matched, priority = find_managed_directory(
            home / "Desktop",
            managed_dirs
        )
        assert priority == 150

        # Test nested path
        matched, priority = find_managed_directory(
            home / "Documents/2025-Project",
            managed_dirs
        )
        assert priority == 100

        # Test deepest match wins
        matched, priority = find_managed_directory(
            home / "other/path",
            managed_dirs
        )
        assert priority == 100  # Matches ~

    def test_priority_examples_from_spec(self):
        """Test that all SPEC.md examples pass."""
        results = priority_examples()

        for result in results:
            assert result["match"], (
                f"Priority mismatch for {result['path']}: "
                f"expected {result['expected']}, got {result['calculated']}"
            )

    def test_calculate_priority_basic(self):
        """Test basic priority calculation."""
        managed_dirs = {"~": 100}
        priority_config = {
            "depth_multiplier": 0.9,
            "extension_weights": {"default": 1.0}
        }

        home = Path.home()

        # File at home level
        priority = calculate_priority(
            home / "file.txt",
            managed_dirs,
            priority_config
        )
        assert priority == 100

        # File one level deep
        priority = calculate_priority(
            home / "subdir/file.txt",
            managed_dirs,
            priority_config
        )
        assert priority == 90  # 100 * 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


