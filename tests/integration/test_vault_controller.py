"""Tests for VaultController."""

from unittest.mock import Mock, patch

import pytest

from wks.config import VaultConfig, WKSConfig
from wks.vault.controller import VaultController
from wks.vault.obsidian import ObsidianVault


@pytest.mark.integration
class TestVaultController:
    """Test VaultController initialization."""

    def test_init_default_machine_name(self):
        """Controller initializes with platform machine name."""
        vault = Mock(spec=ObsidianVault)
        controller = VaultController(vault)
        assert controller.vault == vault
        assert isinstance(controller.machine, str)
        assert len(controller.machine) > 0

    def test_init_custom_machine_name(self):
        """Controller initializes with custom machine name."""
        vault = Mock(spec=ObsidianVault)
        controller = VaultController(vault, machine_name="test-machine")
        assert controller.machine == "test-machine"


@pytest.mark.integration
class TestSyncVault:
    """Test sync_vault static method."""

    def test_sync_vault_requires_vault_base_dir(self):
        """sync_vault raises error if vault.base_dir not configured."""
        # Mock WKSConfig to return empty base_dir
        mock_config = Mock(spec=WKSConfig)
        mock_config.vault = Mock(spec=VaultConfig)
        mock_config.vault.base_dir = ""
        mock_config.vault.wks_dir = "WKS"

        with (
            patch("wks.config.WKSConfig.load", return_value=mock_config),
            pytest.raises(ValueError, match=r"vault.base_dir not configured"),
        ):
            VaultController.sync_vault()
