import pytest

from wks.api.vault.Vault import Vault
from wks.api.vault.VaultConfig import VaultConfig


def test_vault_auto_load_config(monkeypatch, tmp_path, minimal_config_dict):
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
    config = VaultConfig(base_dir="/tmp", type="invalid")
    with pytest.raises(ValueError, match="Unsupported backend type"), Vault(config):
        pass


def test_vault_uninitialized_access():
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
    config = VaultConfig(base_dir="/tmp", type="obsidian")
    vault = Vault(config)

    class MockBackend:
        pass

    vault._backend = MockBackend()  # type: ignore
    assert vault.find_broken_links() == []


def test_vault_resolve_external_url(tmp_path):
    config = VaultConfig(base_dir=str(tmp_path), type="obsidian")
    with Vault(config) as vault:
        url = "https://example.com"
        metadata = vault.resolve_link(url)
        assert metadata.target_uri == url
        assert metadata.status == "ok"


def test_vault_backend_broken_symlinks(tmp_path):
    config = VaultConfig(base_dir=str(tmp_path), type="obsidian")
    with Vault(config) as vault:
        import platform

        machine = platform.node().split(".")[0]
        links_dir = tmp_path / "_links" / machine
        links_dir.mkdir(parents=True)

        target = tmp_path / "target.txt"
        target.touch()
        valid = links_dir / "valid.txt"
        valid.symlink_to(target)

        broken = links_dir / "broken.txt"
        broken.symlink_to(tmp_path / "nonexistent.txt")

        broken_list = vault.find_broken_links()
        assert any("broken.txt" in str(p) for p in broken_list)
        assert not any("valid.txt" in str(p) for p in broken_list)


def test_vault_resolve_missing_symlink(tmp_path):
    config = VaultConfig(base_dir=str(tmp_path), type="obsidian")
    with Vault(config) as vault:
        metadata = vault.resolve_link("_links/missing.txt")
        assert metadata.status == "missing_symlink"


def test_vault_backend_init_failure():
    config = VaultConfig.model_construct(base_dir="", type="obsidian")
    with pytest.raises(ValueError, match=r"vault\.base_dir is required"), Vault(config):
        pass


def test_vault_resolve_link_relative(tmp_path):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "note.md").touch()

    config = VaultConfig(base_dir=str(vault_dir), type="obsidian")
    with Vault(config) as vault:
        metadata = vault.resolve_link("note.md")
        assert metadata.status == "ok"
        assert metadata.target_uri == "vault:///note.md"


def test_vault_resolve_link_broken(tmp_path):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    config = VaultConfig(base_dir=str(vault_dir), type="obsidian")
    with Vault(config) as vault:
        metadata = vault.resolve_link("missing.md")
        assert metadata.status == "missing_target"


def test_vault_resolve_link_links_dir_fallback(tmp_path):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    links_dir = vault_dir / "_links"
    links_dir.mkdir()

    target = tmp_path / "external.txt"
    target.touch()
    link_path = links_dir / "test.txt"
    link_path.symlink_to(target)

    config = VaultConfig(base_dir=str(vault_dir), type="obsidian")
    with Vault(config) as vault:
        metadata = vault.resolve_link("_links/test.txt")
        assert metadata.target_uri.startswith("file://")


def test_vault_iter_files_skip_non_file(tmp_path):
    vault_dir = tmp_path / "vault_skip"
    vault_dir.mkdir()
    subdir = vault_dir / "subdir.md"
    subdir.mkdir()
    (vault_dir / "real.md").touch()

    config = VaultConfig(base_dir=str(vault_dir), type="obsidian")
    with Vault(config) as vault:
        files = list(vault.iter_markdown_files())
        assert len(files) == 1
        assert not any("subdir.md" in str(f) for f in files)


def test_vault_iter_files_yield_exception(tmp_path):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    from collections.abc import Generator
    from typing import cast

    (vault_dir / "note1.md").touch()
    (vault_dir / "note2.md").touch()

    config = VaultConfig(base_dir=str(vault_dir), type="obsidian")
    with Vault(config) as vault:
        gen = cast(Generator, vault.iter_markdown_files())

        _ = next(gen)
        try:
            res = gen.throw(PermissionError("Denied"))
            assert res is not None
        except StopIteration:
            pass
