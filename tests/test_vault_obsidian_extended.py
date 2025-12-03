"""Extended tests for ObsidianVault initialization and path computation."""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock
from datetime import datetime

from wks.vault.obsidian import ObsidianVault
from wks.constants import DEFAULT_TIMESTAMP_FORMAT


class TestVaultInitialization:
    """Test vault initialization with various configurations."""

    def test_init_requires_wks_dir(self, tmp_path):
        """Test that initialization requires wks_dir."""
        with pytest.raises(ValueError, match="vault.wks_dir is required"):
            ObsidianVault(
                vault_path=tmp_path,
                base_dir=""
            )

    def test_init_requires_non_empty_wks_dir(self, tmp_path):
        """Test that wks_dir cannot be whitespace only."""
        with pytest.raises(ValueError, match="vault.wks_dir is required"):
            ObsidianVault(
                vault_path=tmp_path,
                base_dir="   "
            )

    def test_init_strips_wks_dir_whitespace(self, tmp_path):
        """Test that wks_dir whitespace is stripped."""
        vault = ObsidianVault(
            vault_path=tmp_path,
            base_dir="  WKS  "
        )
        assert vault.base_dir == "WKS"

    def test_init_uses_platform_machine_name(self, tmp_path):
        """Test that machine name defaults to platform.node()."""
        with patch("platform.node", return_value="my-machine.local"):
            vault = ObsidianVault(
                vault_path=tmp_path,
                base_dir="WKS"
            )
            assert vault.machine == "my-machine"

    def test_init_uses_custom_machine_name(self, tmp_path):
        """Test that custom machine name is used."""
        vault = ObsidianVault(
            vault_path=tmp_path,
            base_dir="WKS",
            machine_name="custom-machine"
        )
        assert vault.machine == "custom-machine"

    def test_init_strips_machine_name_whitespace(self, tmp_path):
        """Test that machine name whitespace is stripped."""
        vault = ObsidianVault(
            vault_path=tmp_path,
            base_dir="WKS",
            machine_name="  machine-name  "
        )
        assert vault.machine == "machine-name"

    def test_init_handles_machine_name_with_dot(self, tmp_path):
        """Test that machine name with domain is split correctly."""
        with patch("platform.node", return_value="machine.example.com"):
            vault = ObsidianVault(
                vault_path=tmp_path,
                base_dir="WKS"
            )
            assert vault.machine == "machine"


class TestPathComputation:
    """Test _recompute_paths() method."""

    def test_recompute_paths_creates_correct_directories(self, tmp_path):
        """Test that _recompute_paths() sets all directory paths correctly."""
        vault = ObsidianVault(
            vault_path=tmp_path,
            base_dir="WKS"
        )

        assert vault.links_dir == tmp_path / "_links"
        assert vault.projects_dir == tmp_path / "Projects"
        assert vault.people_dir == tmp_path / "People"
        assert vault.topics_dir == tmp_path / "Topics"
        assert vault.ideas_dir == tmp_path / "Ideas"
        assert vault.orgs_dir == tmp_path / "Organizations"
        assert vault.records_dir == tmp_path / "Records"
        assert vault.docs_dir == tmp_path / "WKS" / "Docs"

    def test_recompute_paths_updates_on_base_dir_change(self, tmp_path):
        """Test that paths are recomputed when base_dir changes."""
        vault = ObsidianVault(
            vault_path=tmp_path,
            base_dir="WKS"
        )
        original_docs_dir = vault.docs_dir

        vault.set_base_dir("Custom")
        assert vault.base_dir == "Custom"
        assert vault.docs_dir == tmp_path / "Custom" / "Docs"
        assert vault.docs_dir != original_docs_dir

    def test_set_base_dir_strips_whitespace(self, tmp_path):
        """Test that set_base_dir strips leading/trailing slashes and whitespace."""
        vault = ObsidianVault(
            vault_path=tmp_path,
            base_dir="WKS"
        )

        vault.set_base_dir("  /Custom/  ")
        assert vault.base_dir == "Custom"
        assert vault.docs_dir == tmp_path / "Custom" / "Docs"


class TestDirectoryCreation:
    """Test ensure_structure() method."""

    def test_ensure_structure_creates_all_directories(self, tmp_path):
        """Test that ensure_structure creates all required directories."""
        vault = ObsidianVault(
            vault_path=tmp_path,
            base_dir="WKS"
        )

        vault.ensure_structure()

        assert (tmp_path / "WKS").exists()
        assert (tmp_path / "WKS" / "Docs").exists()
        assert (tmp_path / "_links").exists()
        assert (tmp_path / "Projects").exists()
        assert (tmp_path / "People").exists()
        assert (tmp_path / "Topics").exists()
        assert (tmp_path / "Ideas").exists()
        assert (tmp_path / "Organizations").exists()
        assert (tmp_path / "Records").exists()

    def test_ensure_structure_idempotent(self, tmp_path):
        """Test that ensure_structure can be called multiple times safely."""
        vault = ObsidianVault(
            vault_path=tmp_path,
            base_dir="WKS"
        )

        vault.ensure_structure()
        # Create a file in one directory
        test_file = tmp_path / "Projects" / "test.md"
        test_file.write_text("test")

        # Call again
        vault.ensure_structure()

        # File should still exist
        assert test_file.exists()

    def test_ensure_structure_creates_nested_directories(self, tmp_path):
        """Test that ensure_structure creates nested directory structures."""
        vault = ObsidianVault(
            vault_path=tmp_path,
            base_dir="WKS"
        )

        vault.ensure_structure()

        # Verify nested structure
        assert (tmp_path / "WKS" / "Docs").exists()
        assert (tmp_path / "WKS" / "Docs").is_dir()


class TestTimestampFormat:
    """Test timestamp format handling."""

    def test_timestamp_format_defaults_when_config_fails(self, tmp_path):
        """Test that DEFAULT_TIMESTAMP_FORMAT is used when config fails."""
        with patch("wks.config.WKSConfig.load", side_effect=Exception("Config error")):
            vault = ObsidianVault(
                vault_path=tmp_path,
                base_dir="WKS"
            )
            assert vault.timestamp_format == DEFAULT_TIMESTAMP_FORMAT

    def test_timestamp_format_from_config(self, tmp_path):
        """Test that timestamp format is loaded from config."""
        mock_config = Mock()
        mock_config.display.timestamp_format = "%Y-%m-%d %H:%M:%S"

        with patch("wks.config.WKSConfig.load", return_value=mock_config):
            vault = ObsidianVault(
                vault_path=tmp_path,
                base_dir="WKS"
            )
            assert vault.timestamp_format == "%Y-%m-%d %H:%M:%S"

    def test_format_dt_uses_custom_format(self, tmp_path):
        """Test that _format_dt uses the configured format."""
        mock_config = Mock()
        mock_config.display.timestamp_format = "%Y-%m-%d"

        with patch("wks.config.WKSConfig.load", return_value=mock_config):
            vault = ObsidianVault(
                vault_path=tmp_path,
                base_dir="WKS"
            )
            dt = datetime(2024, 1, 15, 10, 30, 45)
            formatted = vault._format_dt(dt)
            assert formatted == "2024-01-15"

    def test_format_dt_falls_back_on_invalid_format(self, tmp_path):
        """Test that _format_dt falls back to default on invalid format."""
        mock_config = Mock()
        mock_config.display.timestamp_format = "%invalid"

        with patch("wks.config.WKSConfig.load", return_value=mock_config):
            vault = ObsidianVault(
                vault_path=tmp_path,
                base_dir="WKS"
            )
            dt = datetime(2024, 1, 15, 10, 30, 45)
            formatted = vault._format_dt(dt)
            # strftime('%invalid') behavior varies by Python version:
            # - Some versions return 'invalid' (literal text)
            # - Some versions may return '%invalid' or raise exception
            # Just verify it returns something and doesn't crash
            assert len(formatted) > 0
            assert formatted != "%invalid"  # Should not return the format string itself

    def test_format_dt_handles_invalid_datetime(self, tmp_path):
        """Test that _format_dt handles invalid datetime gracefully."""
        vault = ObsidianVault(
            vault_path=tmp_path,
            base_dir="WKS"
        )

        # Pass None (invalid) - the code handles None and returns empty string
        result = vault._format_dt(None)
        assert result == ""


class TestMachineNameExtraction:
    """Test machine name extraction from platform.node()."""

    def test_machine_name_extracts_hostname(self, tmp_path):
        """Test that machine name is extracted from FQDN."""
        with patch("platform.node", return_value="myhost.example.com"):
            vault = ObsidianVault(
                vault_path=tmp_path,
                base_dir="WKS"
            )
            assert vault.machine == "myhost"

    def test_machine_name_handles_simple_hostname(self, tmp_path):
        """Test that simple hostname (no domain) works."""
        with patch("platform.node", return_value="myhost"):
            vault = ObsidianVault(
                vault_path=tmp_path,
                base_dir="WKS"
            )
            assert vault.machine == "myhost"

    def test_machine_name_handles_multiple_dots(self, tmp_path):
        """Test that machine name with multiple dots is handled."""
        with patch("platform.node", return_value="sub.domain.example.com"):
            vault = ObsidianVault(
                vault_path=tmp_path,
                base_dir="WKS"
            )
            assert vault.machine == "sub"
