"""Unit tests for vault factory and abstract implementation."""

import pytest

from wks.api.vault import ObsidianVault, load_vault
from wks.api.vault._AbstractVault import _AbstractVault

pytestmark = pytest.mark.unit


def test_load_vault_obsidian(monkeypatch, tmp_path):
    """Test loading obsidian vault from config."""
    config = {"vault": {"type": "obsidian", "base_dir": str(tmp_path / "vault"), "database": "vault"}}

    vault = load_vault(config)
    assert isinstance(vault, ObsidianVault)
    assert isinstance(vault, _AbstractVault)
    assert vault.vault_path == tmp_path / "vault"


def test_load_vault_unsupported():
    """Test loading unsupported vault type raises SystemExit."""
    config = {"vault": {"type": "unknown_type", "base_dir": "/tmp", "database": "vault"}}

    with pytest.raises(SystemExit) as exc:
        load_vault(config)
    assert "unsupported vault.type" in str(exc.value)


def test_load_vault_missing_base_dir():
    """Test loading vault without base_dir raises SystemExit."""
    config = {
        "vault": {
            "type": "obsidian",
            # base_dir missing
            "database": "vault",
        }
    }

    with pytest.raises(SystemExit) as exc:
        load_vault(config)
    assert "vault.base_dir" in str(exc.value)
