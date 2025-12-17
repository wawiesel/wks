"""Unit tests for vault scanner error handling."""

import pytest

from tests.unit.conftest import run_cmd
from wks.api.vault.cmd_sync import cmd_sync

pytestmark = pytest.mark.vault


def test_scanner_handles_read_errors(monkeypatch, tmp_path, minimal_config_dict):
    """Scanner reports errors if file cannot be read."""
    # Setup
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    # Create a real file
    note = vault_dir / "note.md"
    note.write_text("content", encoding="utf-8")

    # Make it unreadable
    note.chmod(0o000)

    try:
        cfg = minimal_config_dict
        cfg["vault"]["base_dir"] = str(vault_dir)
        cfg["vault"]["type"] = "obsidian"
        (wks_home / "config.json").write_text(json_dumps(minimal_config_dict), encoding="utf-8")

        result = run_cmd(cmd_sync)

        # Sync should still succeed (partial success), but report errors
        assert result.success is False
        assert len(result.output["errors"]) > 0
        assert "Permission denied" in result.output["errors"][0] or "Access is denied" in result.output["errors"][0]
    finally:
        # Restore permissions so cleanup works
        note.chmod(0o755)


def test_scanner_handles_external_file_paths(monkeypatch, tmp_path, minimal_config_dict):
    """Scanner ignores files outside vault root during iteration."""
    # Setup
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json_dumps(minimal_config_dict), encoding="utf-8")

    # To test this without mocking iter_markdown_files (which is part of the real implementation),
    # we would need to symlink an external file into the vault, but _Backend ignores symlinks or handles them.
    # The original test mocked the iterator to yield a path outside the vault.
    # To reproduce this "naturally", we might rely on a symlink pointing out.

    # However, _Backend.iter_markdown_files actively filters.
    # If we want to test that Scanner handles a path outside vault *if* it receives one:
    # We can pass an explicit file list to scan() that includes an external path.
    # cmd_sync accepts a 'path' argument.

    external_file = tmp_path / "external.md"
    external_file.write_text("[[link]]", encoding="utf-8")

    from wks.api.vault.cmd_sync import cmd_sync

    result = run_cmd(cmd_sync, path=str(external_file))

    # Scanner fails when trying to compute relative path for the link record
    # cmd_sync catches exception
    assert result.success is False
    assert any("is not in the subpath of" in e or "relative_to" in str(e) for e in result.output["errors"])


def test_scanner_handles_rewrite_errors(monkeypatch, tmp_path, minimal_config_dict):
    """Scanner reports errors if file rewrite fails."""
    # Setup
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    # Create file with file:// URL to trigger rewrite
    note = vault_dir / "rewrite_me.md"
    # We need a real file to convert to symlink
    target = vault_dir / "target.txt"
    target.touch()
    target_uri = target.as_uri()

    note.write_text(f"[link]({target_uri})", encoding="utf-8")

    # Make file readonly to trigger write failure
    note.chmod(0o444)

    try:
        cfg = minimal_config_dict
        cfg["vault"]["base_dir"] = str(vault_dir)
        cfg["vault"]["type"] = "obsidian"
        (wks_home / "config.json").write_text(json_dumps(minimal_config_dict), encoding="utf-8")

        result = run_cmd(cmd_sync)

        # Should report error
        assert any("Permission denied" in e or "Access is denied" in e for e in result.output["errors"])
        assert result.success is False
    finally:
        note.chmod(0o644)


def json_dumps(d):
    import json

    return json.dumps(d)
