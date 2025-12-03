"""Tests for vault package initialization and factory functions."""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock

from wks.vault import load_vault, ObsidianVault, VaultController
from wks.vault.obsidian import ObsidianVault as ObsidianVaultClass


class TestVaultPackageInitialization:
    """Test vault package initialization."""

    def test_package_exports(self):
        """Test that package exports expected symbols."""
        from wks.vault import ObsidianVault, VaultController, load_vault

        assert ObsidianVault is not None
        assert VaultController is not None
        assert load_vault is not None
        assert callable(load_vault)

    def test_obsidian_vault_type(self):
        """Test that VaultType is set to ObsidianVault."""
        from wks.vault import ObsidianVault
        # VaultType is internal, but we can verify ObsidianVault is available
        assert ObsidianVault is ObsidianVaultClass


class TestLoadVault:
    """Test load_vault() factory function."""

    def test_load_vault_requires_base_dir(self, tmp_path):
        """Test that load_vault() requires vault.base_dir in config."""
        cfg = {
            "vault": {
                "type": "obsidian",
                # Missing base_dir
            }
        }

        with pytest.raises(SystemExit, match="vault.base_dir.*required"):
            load_vault(cfg)

    def test_load_vault_requires_wks_dir(self, tmp_path):
        """Test that load_vault() requires vault.wks_dir in config."""
        cfg = {
            "vault": {
                "type": "obsidian",
                "base_dir": str(tmp_path),
                # Missing wks_dir
            }
        }

        with pytest.raises(SystemExit, match="vault.wks_dir.*required"):
            load_vault(cfg)

    def test_load_vault_creates_obsidian_vault(self, tmp_path):
        """Test that load_vault() creates ObsidianVault instance."""
        cfg = {
            "vault": {
                "type": "obsidian",
                "base_dir": str(tmp_path),
                "wks_dir": "WKS"
            }
        }

        vault = load_vault(cfg)
        assert isinstance(vault, ObsidianVault)
        assert vault.vault_path == Path(tmp_path)
        assert vault.base_dir == "WKS"

    def test_load_vault_defaults_to_obsidian(self, tmp_path):
        """Test that load_vault() defaults to obsidian type."""
        cfg = {
            "vault": {
                "base_dir": str(tmp_path),
                "wks_dir": "WKS"
                # type not specified
            }
        }

        vault = load_vault(cfg)
        assert isinstance(vault, ObsidianVault)

    def test_load_vault_loads_config_when_none(self, tmp_path):
        """Test that load_vault() loads config when cfg is None."""
        mock_config = {
            "vault": {
                "type": "obsidian",
                "base_dir": str(tmp_path),
                "wks_dir": "WKS"
            }
        }

        with patch("wks.config.load_config", return_value=mock_config):
            vault = load_vault(None)
            assert isinstance(vault, ObsidianVault)

    def test_load_vault_raises_on_unsupported_type(self, tmp_path):
        """Test that load_vault() raises SystemExit for unsupported vault type."""
        cfg = {
            "vault": {
                "type": "unsupported",
                "base_dir": str(tmp_path),
                "wks_dir": "WKS"
            }
        }

        with pytest.raises(SystemExit, match="unsupported vault.type"):
            load_vault(cfg)

    def test_load_vault_expands_paths(self, tmp_path):
        """Test that load_vault() expands paths correctly."""
        # Use ~ for home directory expansion
        home = Path.home()
        relative_path = tmp_path.relative_to(home) if tmp_path.is_relative_to(home) else tmp_path

        cfg = {
            "vault": {
                "type": "obsidian",
                "base_dir": str(relative_path) if relative_path != tmp_path else str(tmp_path),
                "wks_dir": "WKS"
            }
        }

        vault = load_vault(cfg)
        assert vault.vault_path.exists() or str(vault.vault_path).startswith(str(home))

    def test_load_vault_handles_absolute_paths(self, tmp_path):
        """Test that load_vault() handles absolute paths."""
        cfg = {
            "vault": {
                "type": "obsidian",
                "base_dir": str(tmp_path.absolute()),
                "wks_dir": "WKS"
            }
        }

        vault = load_vault(cfg)
        assert vault.vault_path.is_absolute()


class TestResolveObsidianSettings:
    """Test _resolve_obsidian_settings() function."""

    def test_resolve_obsidian_settings_extracts_paths(self, tmp_path):
        """Test that _resolve_obsidian_settings() extracts required paths."""
        cfg = {
            "vault": {
                "base_dir": str(tmp_path),
                "wks_dir": "WKS"
            }
        }

        # Call load_vault which uses _resolve_obsidian_settings internally
        vault = load_vault(cfg)
        assert vault.vault_path == Path(tmp_path)
        assert vault.base_dir == "WKS"

    def test_resolve_obsidian_settings_raises_on_missing_base_dir(self):
        """Test that _resolve_obsidian_settings() raises on missing base_dir."""
        cfg = {
            "vault": {
                "wks_dir": "WKS"
                # Missing base_dir
            }
        }

        with pytest.raises(SystemExit, match="vault.base_dir.*required"):
            load_vault(cfg)

    def test_resolve_obsidian_settings_raises_on_missing_wks_dir(self, tmp_path):
        """Test that _resolve_obsidian_settings() raises on missing wks_dir."""
        cfg = {
            "vault": {
                "base_dir": str(tmp_path)
                # Missing wks_dir
            }
        }

        with pytest.raises(SystemExit, match="vault.wks_dir.*required"):
            load_vault(cfg)

    def test_resolve_obsidian_settings_handles_empty_vault_section(self):
        """Test that _resolve_obsidian_settings() handles empty vault section."""
        cfg = {
            "vault": {}
        }

        with pytest.raises(SystemExit):
            load_vault(cfg)

    def test_resolve_obsidian_settings_handles_missing_vault_section(self):
        """Test that _resolve_obsidian_settings() handles missing vault section."""
        cfg = {}

        with pytest.raises(SystemExit):
            load_vault(cfg)


class TestVaultFactoryFunctions:
    """Test factory functions for creating vault instances."""

    def test_load_vault_creates_controller_compatible_vault(self, tmp_path):
        """Test that load_vault() creates vault compatible with VaultController."""
        cfg = {
            "vault": {
                "type": "obsidian",
                "base_dir": str(tmp_path),
                "wks_dir": "WKS"
            }
        }

        vault = load_vault(cfg)
        controller = VaultController(vault)

        assert controller.vault == vault
        assert isinstance(controller.vault, ObsidianVault)

    def test_vault_has_required_attributes(self, tmp_path):
        """Test that created vault has all required attributes."""
        cfg = {
            "vault": {
                "type": "obsidian",
                "base_dir": str(tmp_path),
                "wks_dir": "WKS"
            }
        }

        vault = load_vault(cfg)

        # Check required attributes exist
        assert hasattr(vault, "vault_path")
        assert hasattr(vault, "base_dir")
        assert hasattr(vault, "links_dir")
        assert hasattr(vault, "machine")
        assert hasattr(vault, "iter_markdown_files")

    def test_vault_can_iterate_markdown(self, tmp_path):
        """Test that created vault can iterate markdown files."""
        cfg = {
            "vault": {
                "type": "obsidian",
                "base_dir": str(tmp_path),
                "wks_dir": "WKS"
            }
        }

        # Create a markdown file
        (tmp_path / "note.md").write_text("# Test")

        vault = load_vault(cfg)
        files = list(vault.iter_markdown_files())

        # Should find the markdown file
        assert len(files) >= 1
        assert any(f.name == "note.md" for f in files)
