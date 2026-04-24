import pytest
from pydantic import ValidationError

from wks.api.vault.VaultConfig import VaultConfig


def test_vault_config_from_dict_success():
    config = {"vault": {"type": "obsidian", "base_dir": "/tmp/vault"}}
    vc = VaultConfig.from_config_dict(config)
    assert vc.type == "obsidian"
    assert vc.base_dir.endswith("/tmp/vault")


def test_vault_config_from_dict_missing_section():
    with pytest.raises(ValueError, match="vault section is required"):
        VaultConfig.from_config_dict({})


def test_vault_config_validation_error():
    config = {"vault": {"type": "obsidian"}}
    with pytest.raises(ValidationError):
        VaultConfig.from_config_dict(config)


def test_vault_config_forbid_extra():
    with pytest.raises(ValidationError):
        VaultConfig(type="obsidian", base_dir="/tmp", extra="field")  # type: ignore
