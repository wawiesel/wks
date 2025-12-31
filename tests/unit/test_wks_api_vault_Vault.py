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
    """Test backend init failure when base_dir is missing."""
    # Use model_construct to bypass VaultConfig validation to test Backend validation
    config = VaultConfig.model_construct(base_dir="", type="obsidian")
    with pytest.raises(ValueError, match=r"vault\.base_dir is required"), Vault(config):
        pass


def test_vault_resolve_link_relative(tmp_path):
    """Test resolution of internal note."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "note.md").touch()

    config = VaultConfig(base_dir=str(vault_dir), type="obsidian")
    with Vault(config) as vault:
        metadata = vault.resolve_link("note.md")
        assert metadata.status == "ok"
        assert metadata.target_uri == "vault:///note.md"


def test_vault_resolve_link_broken(tmp_path):
    """Test resolution of missing note."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    config = VaultConfig(base_dir=str(vault_dir), type="obsidian")
    with Vault(config) as vault:
        metadata = vault.resolve_link("missing.md")
        assert metadata.status == "missing_target"


def test_vault_resolve_link_links_dir_fallback(tmp_path):
    """Test fallback to _links directory."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    links_dir = vault_dir / "_links"
    links_dir.mkdir()

    # Symlink in _links
    target = tmp_path / "external.txt"
    target.touch()
    link_path = links_dir / "test.txt"
    link_path.symlink_to(target)

    config = VaultConfig(base_dir=str(vault_dir), type="obsidian")
    with Vault(config) as vault:
        metadata = vault.resolve_link("_links/test.txt")
        assert metadata.target_uri.startswith("file://")


def test_vault_iter_files_skip_non_file(tmp_path):
    """Test that directories matching *.md are skipped."""
    vault_dir = tmp_path / "vault_skip"
    vault_dir.mkdir()
    # Create a directory ending in .md
    subdir = vault_dir / "subdir.md"
    subdir.mkdir()
    (vault_dir / "real.md").touch()

    config = VaultConfig(base_dir=str(vault_dir), type="obsidian")
    with Vault(config) as vault:
        files = list(vault.iter_markdown_files())
        assert len(files) == 1
        assert not any("subdir.md" in str(f) for f in files)


def test_vault_iter_files_yield_exception(tmp_path):
    """Test handling exception during generator yield."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    # Create two files. We expect the generator to yield the first,
    # then we inject an error, and it should proceed to the second.
    # Note: Backend.iter_markdown_files() catches OSError/PermissionError internally
    # when iterating, but the test here is about injecting checks *into* the generator loop.
    # Actually, the Backend code yields inside a try/except block (lines 63-66).
    # If we throw() into the generator, we simulate an error happening *at yield*.

    from collections.abc import Generator
    from typing import cast

    (vault_dir / "note1.md").touch()
    (vault_dir / "note2.md").touch()

    config = VaultConfig(base_dir=str(vault_dir), type="obsidian")
    with Vault(config) as vault:
        gen = cast(Generator, vault.iter_markdown_files())

        # Depending on file system order, we get one.
        # We just need to consume one, throw, and ensure we get another (or stop iteration cleanly if only 1 left).
        # Since we have 2 files, if we consume 1 and throw permission error,
        # the generator should catch it and continue to the next file?
        # Looking at _Backend.py lines 63-66:
        # try: yield md; except (OSError, PermissionError): continue
        # So yes, it should catch and continue.

        _ = next(gen)
        # Throw error to verify robustness
        try:
            # If the backend handles it, it should return the next item (note2)
            # OR raise StopIteration if done.
            # But the order isn't guaranteed.
            # If note1 and note2 are the only ones, and we processed one,
            # throwing triggers the 'except' which 'continue's to next loop iteration.
            res = gen.throw(PermissionError("Denied"))
            # If we get here, we got the next item
            assert res is not None
        except StopIteration:
            # If we were at the last item, this is fine too,
            # but we want to prove it didn't CRASH.
            pass
