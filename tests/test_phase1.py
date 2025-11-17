"""Test Phase 1: Display infrastructure, priority calculation, config migration."""

import pytest
from pathlib import Path

from wks.display.base import Display
from wks.display.cli import CLIDisplay
from wks.display.mcp import MCPDisplay
from wks.display.context import get_display, is_mcp_context
from wks.priority import calculate_priority, find_managed_directory, priority_examples
from wks.config_schema import is_old_config, migrate_config, validate_config


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


class TestConfigMigration:
    """Test config schema and migration."""

    def test_is_old_config_detection(self):
        """Test detecting old config format."""
        old_config = {
            "vault_path": "~/_vault",
            "obsidian": {"base_dir": "WKS"},
            "similarity": {"enabled": True},
        }
        assert is_old_config(old_config) is True

        new_config = {
            "monitor": {"managed_directories": {"~": 100}},
            "vault": {"base_dir": "~/_vault"},
            "related": {"engines": {}},
        }
        assert is_old_config(new_config) is False

    def test_migrate_config_structure(self):
        """Test config migration produces valid structure."""
        old_config = {
            "vault_path": "~/_vault",
            "obsidian": {"base_dir": "WKS"},
            "similarity": {
                "enabled": True,
                "model": "all-MiniLM-L6-v2",
            },
            "monitor": {
                "include_paths": ["~"],
            },
            "mongo": {
                "uri": "mongodb://localhost:27017/",
            }
        }

        new_config = migrate_config(old_config)

        # Check new sections exist
        assert "monitor" in new_config
        assert "vault" in new_config
        assert "db" in new_config
        assert "related" in new_config
        assert "extract" in new_config
        assert "diff" in new_config
        assert "index" in new_config
        assert "search" in new_config

        # Check monitor has new fields
        assert "managed_directories" in new_config["monitor"]
        assert "priority" in new_config["monitor"]

        # Check vault converted from obsidian
        assert new_config["vault"]["base_dir"] == "~/_vault"
        assert new_config["vault"]["wks_dir"] == "WKS"

        # Check related converted from similarity
        assert "engines" in new_config["related"]
        assert "embedding" in new_config["related"]["engines"]
        assert new_config["related"]["engines"]["embedding"]["model"] == "all-MiniLM-L6-v2"

    def test_validate_config(self):
        """Test config validation."""
        # Valid config
        valid_config = {
            "monitor": {
                "managed_directories": {"~": 100},
                "priority": {"depth_multiplier": 0.9},
                "database": "wks_monitor",
            },
            "vault": {
                "base_dir": "~/_vault",
                "database": "wks.vault",
            },
            "db": {
                "uri": "mongodb://localhost:27017/",
            },
        }
        is_valid, errors = validate_config(valid_config)
        assert is_valid is True
        assert len(errors) == 0

        # Invalid config (missing sections)
        invalid_config = {
            "monitor": {},
        }
        is_valid, errors = validate_config(invalid_config)
        assert is_valid is False
        assert len(errors) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
