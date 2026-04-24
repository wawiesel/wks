"""Unit tests for vault cmd_status."""

import pytest

from tests.unit._vault_test_helpers import setup_vault_env, vault_database_config, write_unit_config
from tests.unit.conftest import run_cmd
from wks.api.vault.cmd_status import cmd_status

pytestmark = pytest.mark.vault


def test_cmd_status_returns_structure(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_status returns expected output structure."""
    setup_vault_env(monkeypatch, tmp_path, minimal_config_dict)

    result = run_cmd(cmd_status)

    # Should have expected output keys (simplified schema)
    assert "total_links" in result.output
    assert "last_sync" in result.output
    assert "success" in result.output
    assert "database" in result.output
    # These were removed from schema
    assert "ok_links" not in result.output
    assert "broken_links" not in result.output
    assert "issues" not in result.output
    assert "notes_scanned" not in result.output


def test_cmd_status_empty_vault(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_status on empty vault returns zero counts."""
    _, _, config = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict)

    # Clear DB state
    from wks.api.database.Database import Database

    with Database(vault_database_config(config), "edges") as db:
        db.delete_many({})

    result = run_cmd(cmd_status)

    assert result.output["total_links"] == 0
    assert result.output["last_sync"] is None
    assert result.success is True


def test_cmd_status_config_failure(monkeypatch, tmp_path):
    """cmd_status handles config load failure."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    # No config file created

    result = run_cmd(cmd_status)
    assert result.success is False
    assert "Failed to load config" in result.output["errors"][0]


def test_cmd_status_work_failure(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_status handles runtime failure in work loop."""
    setup_vault_env(monkeypatch, tmp_path, minimal_config_dict)

    from unittest.mock import patch

    with patch("wks.api.database.Database.Database.__enter__") as mock_db:
        mock_db.side_effect = RuntimeError("DB Failure")

        result = run_cmd(cmd_status)
        assert result.success is False
        assert "Vault status failed: DB Failure" in result.result


def test_cmd_status_missing_base_dir(monkeypatch, tmp_path, minimal_config_dict):
    """Test cmd_status with missing base_dir (line 32)."""
    wks_home, _, cfg = setup_vault_env(
        monkeypatch, tmp_path, minimal_config_dict, vault_base_dir=tmp_path / "vault", create_vault_dir=False
    )
    write_unit_config(wks_home, cfg)

    # Now muck with the loaded model or re-mock load
    from wks.api.config.WKSConfig import WKSConfig
    from wks.api.vault.VaultConfig import VaultConfig

    config = WKSConfig.load()
    config.vault = VaultConfig.model_construct(base_dir="", type="obsidian")

    monkeypatch.setattr(WKSConfig, "load", lambda: config)

    result = run_cmd(cmd_status)
    assert result.success is False
    assert "base_dir not configured" in result.output["errors"][0]
