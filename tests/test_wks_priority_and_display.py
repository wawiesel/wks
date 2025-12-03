"""Tests for display infrastructure and priority calculation."""

import pytest
from pathlib import Path

from wks.display.base import Display
from wks.display.cli import CLIDisplay
from wks.display.mcp import MCPDisplay
from wks.display.context import get_display, is_mcp_context, add_display_argument
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

    def test_get_display_auto_detect_cli(self, monkeypatch):
        """Test get_display auto-detects CLI context."""
        # Ensure we're in CLI context
        monkeypatch.delenv("MCP_MODE", raising=False)
        monkeypatch.delenv("MCP_SERVER", raising=False)
        monkeypatch.setenv("TERM", "xterm")

        display = get_display()
        assert isinstance(display, CLIDisplay)

    def test_get_display_auto_detect_mcp(self, monkeypatch):
        """Test get_display auto-detects MCP context."""
        # Set MCP environment
        monkeypatch.setenv("MCP_MODE", "1")

        display = get_display()
        assert isinstance(display, MCPDisplay)

    def test_get_display_invalid_mode(self):
        """Test get_display raises ValueError for invalid mode."""
        with pytest.raises(ValueError, match="Invalid display mode"):
            get_display("invalid")

    def test_is_mcp_context_env_var_mcp_mode(self, monkeypatch):
        """Test is_mcp_context detects MCP_MODE env var."""
        monkeypatch.setenv("MCP_MODE", "1")

        assert is_mcp_context() is True

    def test_is_mcp_context_env_var_mcp_server(self, monkeypatch):
        """Test is_mcp_context detects MCP_SERVER env var."""
        monkeypatch.setenv("MCP_SERVER", "true")
        monkeypatch.delenv("MCP_MODE", raising=False)

        assert is_mcp_context() is True

    def test_is_mcp_context_no_term(self, monkeypatch):
        """Test is_mcp_context detects no TERM and piped stdout."""
        monkeypatch.delenv("MCP_MODE", raising=False)
        monkeypatch.delenv("MCP_SERVER", raising=False)
        monkeypatch.delenv("TERM", raising=False)

        # Mock stdout.isatty to return False
        import sys
        original_isatty = sys.stdout.isatty

        def mock_isatty():
            return False
        sys.stdout.isatty = mock_isatty

        try:
            result = is_mcp_context()
            assert result is True
        finally:
            sys.stdout.isatty = original_isatty

    def test_is_mcp_context_returns_false(self, monkeypatch):
        """Test is_mcp_context returns False in normal CLI context."""
        monkeypatch.delenv("MCP_MODE", raising=False)
        monkeypatch.delenv("MCP_SERVER", raising=False)
        monkeypatch.setenv("TERM", "xterm")

        assert is_mcp_context() is False

    def test_add_display_argument(self):
        """Test add_display_argument adds --display arg."""
        import argparse

        parser = argparse.ArgumentParser()
        add_display_argument(parser)

        # Parse with --display
        args = parser.parse_args(["--display", "mcp"])
        assert args.display == "mcp"


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
