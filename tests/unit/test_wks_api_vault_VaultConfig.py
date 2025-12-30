"""Unit tests for wks.api.vault.VaultConfig module."""

import pytest
from pydantic import ValidationError

from wks.api.vault.VaultConfig import VaultConfig


def test_vault_config_valid():
    cfg = VaultConfig.model_validate({"type": "obsidian", "base_dir": "/tmp/vault"})
    assert cfg.type == "obsidian"
    assert cfg.base_dir == "/tmp/vault"


def test_vault_config_validation():
    with pytest.raises(ValidationError):
        VaultConfig.model_validate({"type": "obsidian"})  # missing base_dir
