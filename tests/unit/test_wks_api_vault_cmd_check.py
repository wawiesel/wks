"""Unit tests for vault cmd_check."""

import json
import platform

import pytest

from tests.unit.conftest import run_cmd
from wks.api.vault.cmd_check import cmd_check

pytestmark = pytest.mark.vault


def test_cmd_check_returns_structure(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_check returns expected output structure."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_check)

    assert "notes_checked" in result.output
    assert "links_checked" in result.output
    assert "broken_count" in result.output
    assert "is_valid" in result.output
    assert "success" in result.output


def test_cmd_check_empty_vault_is_valid(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_check on empty vault reports as valid."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_check)

    assert result.output["is_valid"] is True
    assert result.output["broken_count"] == 0
    assert result.success is True


def test_cmd_check_nonexistent_path_fails(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_check with nonexistent path returns error."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_check, path="/nonexistent/file.md")

    assert result.success is False
    assert len(result.output["errors"]) > 0


def test_cmd_check_config_failure(monkeypatch, tmp_path):
    """cmd_check handles config load failure gracefully."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    # No config file created

    result = run_cmd(cmd_check)
    assert result.success is False
    assert "Failed to load config" in result.output["errors"][0]


def test_cmd_check_vault_init_failure(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_check handles vault init failure gracefully."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = "/tmp"
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Mock Vault init failure
    def mock_enter(*args, **kwargs):
        raise RuntimeError("Vault Init Error")

    monkeypatch.setattr("wks.api.vault.Vault.Vault.__enter__", mock_enter)

    result = run_cmd(cmd_check)
    assert result.success is False
    assert "Vault Init Error" in result.output["errors"][0]


def test_scanner_rewrites_file_urls_via_check(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_check should trigger file:// URL rewriting and symlink creation."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()

    ext_file = (tmp_path / "external.txt").resolve()
    ext_file.write_text("external content", encoding="utf-8")
    ext_uri = ext_file.as_uri()

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    note = vault_dir / "note.md"
    note.write_text(f"Check this: [external]({ext_uri})", encoding="utf-8")

    result = run_cmd(cmd_check)
    assert result.success

    content = note.read_text(encoding="utf-8")
    assert "[[_links/" in content

    machine = platform.node().split(".")[0]
    assert (vault_dir / "_links" / machine).exists()


def test_scanner_handles_missing_file_url_via_check(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_check handles missing file URLs in scanner."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    bad_uri = "file:///non/existent/path/file.txt"
    note = vault_dir / "note.md"
    note.write_text(f"[bad]({bad_uri})", encoding="utf-8")

    result = run_cmd(cmd_check)
    assert result.success is False
    assert any("non-existent path" in err for err in result.output["errors"])


def test_resolve_attachment_via_check(monkeypatch, tmp_path, minimal_config_dict):
    """Test resolution of vault attachments via cmd_check."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    (vault_dir / "_img.png").write_text("data", encoding="utf-8")
    (vault_dir / "note.md").write_text("[[_img.png]]", encoding="utf-8")

    result = run_cmd(cmd_check)
    assert result.success
    assert result.output["links_checked"] >= 1


def test_cmd_check_path_valid(monkeypatch, tmp_path, minimal_config_dict):
    """Test cmd_check with a specific valid path."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    note = vault_dir / "valid.md"
    note.write_text("# Valid", encoding="utf-8")

    result = run_cmd(cmd_check, path="valid.md")
    assert result.success is True
    assert result.output["notes_checked"] == 1


def test_cmd_check_path_invalid_vault_path(monkeypatch, tmp_path, minimal_config_dict):
    """Test cmd_check with a path that triggers VaultPathError (line 61-75)."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Path outside vault
    result = run_cmd(cmd_check, path="../../outside.md")
    assert result.success is False
    assert "does not exist" in result.result or "not in vault" in result.result.lower()


def test_cmd_check_missing_base_dir(monkeypatch, tmp_path, minimal_config_dict):
    """Test cmd_check with missing base_dir (line 32)."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # Create a valid config first so load() succeeds if it was cached
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(tmp_path / "vault")
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Now muck with the loaded model or re-mock load
    from wks.api.config.WKSConfig import WKSConfig
    from wks.api.vault.VaultConfig import VaultConfig

    # Reset internal cache if any
    if hasattr(WKSConfig, "_instance"):
        WKSConfig._instance = None

    config = WKSConfig.load()
    config.vault = VaultConfig.model_construct(base_dir="", type="obsidian")

    monkeypatch.setattr(WKSConfig, "load", lambda: config)

    result = run_cmd(cmd_check)
    assert result.success is False
    assert "base_dir not configured" in result.output["errors"][0]


def test_cmd_check_with_broken_link(monkeypatch, tmp_path, minimal_config_dict):
    """Test cmd_check with a broken link to hit line 87."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    note = vault_dir / "broken.md"
    note.write_text("[[nonexistent]]", encoding="utf-8")

    result = run_cmd(cmd_check)
    assert result.success is True  # scanner errors are strings, status != OK is just an issue
    assert result.output["broken_count"] == 1
    assert result.output["is_valid"] is False
