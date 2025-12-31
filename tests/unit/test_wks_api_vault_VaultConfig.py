"""Tests for VaultConfig."""

import pytest
from pydantic import ValidationError

from wks.api.vault.VaultConfig import VaultConfig


def test_vault_config_from_dict_success():
    """Test successful loading from dict."""
    config = {"vault": {"type": "obsidian", "base_dir": "/tmp/vault"}}
    vc = VaultConfig.from_config_dict(config)
    assert vc.type == "obsidian"
    assert vc.base_dir.endswith("/tmp/vault")


def test_vault_config_from_dict_missing_section():
    """Test error when vault section is missing."""
    with pytest.raises(ValueError, match="vault section is required"):
        VaultConfig.from_config_dict({})


def test_vault_config_validation_error():
    """Test pydantic validation error."""
    config = {
        "vault": {
            "type": "obsidian"
            # missing base_dir
        }
    }
    with pytest.raises(ValidationError):
        VaultConfig.from_config_dict(config)


def test_vault_config_forbid_extra():
    """Test that extra fields are forbidden."""
    with pytest.raises(ValidationError):
        VaultConfig(type="obsidian", base_dir="/tmp", extra="field")  # type: ignore
