"""Tests for Vault facade."""

import pytest

from wks.api.vault.Vault import Vault
from wks.api.vault.VaultConfig import VaultConfig


def test_vault_auto_load_config(monkeypatch, tmp_path, minimal_config_dict):
    """Test Vault initialization without explicit config."""
    import json

    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    config = minimal_config_dict
    config["vault"] = {"base_dir": str(tmp_path / "vault"), "type": "obsidian"}
    (wks_home / "config.json").write_text(json.dumps(config), encoding="utf-8")

    vault = Vault()
    assert vault.vault_config.type == "obsidian"
    assert vault.vault_config.base_dir == str(tmp_path / "vault")


def test_vault_unsupported_backend():
    """Test error for unsupported backend type."""
    config = VaultConfig(base_dir="/tmp", type="invalid")
    with pytest.raises(ValueError, match="Unsupported backend type"), Vault(config):
        pass


def test_vault_uninitialized_access():
    """Test error when accessing properties before initialization."""
    vault = Vault(VaultConfig(base_dir="/tmp", type="obsidian"))

    with pytest.raises(RuntimeError, match="Vault not initialized"):
        _ = vault.vault_path

    with pytest.raises(RuntimeError, match="Vault not initialized"):
        _ = vault.links_dir

    with pytest.raises(RuntimeError, match="Vault not initialized"):
        next(vault.iter_markdown_files())

    with pytest.raises(RuntimeError, match="Vault not initialized"):
        vault.resolve_link("target")


def test_vault_find_broken_links_no_backend_support(monkeypatch):
    """Test find_broken_links when backend doesn't support it."""
    config = VaultConfig(base_dir="/tmp", type="obsidian")
    vault = Vault(config)

    # Mock backend to NOT have find_broken_links
    class MockBackend:
        pass

    vault._backend = MockBackend()  # type: ignore
    assert vault.find_broken_links() == []


def test_vault_resolve_external_url(tmp_path):
    """Test resolution of external URLs in vault (covers _Backend.py branches)."""
    config = VaultConfig(base_dir=str(tmp_path), type="obsidian")
    with Vault(config) as vault:
        url = "https://example.com"
        metadata = vault.resolve_link(url)
        assert metadata.target_uri == url
        assert metadata.status == "ok"


def test_vault_backend_broken_symlinks(tmp_path):
    """Test find_broken_links directly on backend (to cover more lines)."""
    config = VaultConfig(base_dir=str(tmp_path), type="obsidian")
    with Vault(config) as vault:
        import platform

        machine = platform.node().split(".")[0]
        links_dir = tmp_path / "_links" / machine
        links_dir.mkdir(parents=True)

        # 1. Valid symlink
        target = tmp_path / "target.txt"
        target.touch()
        valid = links_dir / "valid.txt"
        valid.symlink_to(target)

        # 2. Broken symlink
        broken = links_dir / "broken.txt"
        broken.symlink_to(tmp_path / "nonexistent.txt")

        broken_list = vault.find_broken_links()
        assert any("broken.txt" in str(p) for p in broken_list)
        assert not any("valid.txt" in str(p) for p in broken_list)


def test_vault_resolve_missing_symlink(tmp_path):
    """Test resolution of missing symlink."""
    config = VaultConfig(base_dir=str(tmp_path), type="obsidian")
    with Vault(config) as vault:
        # Resolve a symlink that doesn't exist
        metadata = vault.resolve_link("_links/missing.txt")
        assert metadata.status == "missing_symlink"


def test_vault_backend_init_failure():
    """Test backend init failure when base_dir is missing (covers _Backend.py)."""
    # VaultConfig validates base_dir exists, but we can try to bypass it
    # if we mock normalized_path or use an empty string if allowed.
    # Actually, VaultConfig forbids empty base_dir.
    # But _Backend.py line 30 checks it too.
    from wks.api.vault._obsidian._Backend import _Backend
    from wks.api.vault.VaultConfig import VaultConfig as MockVC

    with pytest.raises(ValueError, match=r"vault\.base_dir is required"):
        _Backend(MockVC.model_construct(base_dir="", type="obsidian"))
