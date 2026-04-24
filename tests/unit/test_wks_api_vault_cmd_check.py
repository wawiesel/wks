import copy
import json
import platform

import pytest

from tests.unit._vault_test_helpers import setup_vault_env, write_unit_config
from tests.unit.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.vault.cmd_check import cmd_check

pytestmark = pytest.mark.vault


def write_vault_note(vault_dir, name: str, content: str) -> None:
    (vault_dir / name).write_text(content, encoding="utf-8")


def test_cmd_check_empty_vault_structure_and_validity(monkeypatch, tmp_path, minimal_config_dict):
    _, _, _ = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict)

    result = run_cmd(cmd_check)

    assert result.success is True
    assert result.output["is_valid"] is True
    assert result.output["broken_count"] == 0
    assert {"notes_checked", "links_checked", "broken_count", "is_valid", "success"} <= set(result.output)


@pytest.mark.parametrize("target", [URI.from_path("/nonexistent/file.md"), URI("vault:///../../outside.md")])
def test_cmd_check_invalid_targets(monkeypatch, tmp_path, minimal_config_dict, target):
    _, _, _ = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict)

    result = run_cmd(cmd_check, uri=target)

    assert result.success is False
    assert result.output["errors"]


def test_cmd_check_config_failure(monkeypatch, tmp_path):
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    result = run_cmd(cmd_check)

    assert result.success is False
    assert "Failed to load config" in result.output["errors"][0]


def test_cmd_check_missing_base_dir(monkeypatch, tmp_path, minimal_config_dict):
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(minimal_config_dict), encoding="utf-8")

    from wks.api.config.WKSConfig import WKSConfig
    from wks.api.vault.VaultConfig import VaultConfig

    if hasattr(WKSConfig, "_instance"):
        WKSConfig._instance = None

    config = WKSConfig.load()
    config.vault = VaultConfig.model_construct(base_dir="", type="obsidian")
    monkeypatch.setattr(WKSConfig, "load", lambda: config)

    result = run_cmd(cmd_check)

    assert result.success is False
    assert "base_dir not configured" in result.output["errors"][0]


def test_cmd_check_vault_init_failure(monkeypatch, tmp_path, minimal_config_dict):
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    config = copy.deepcopy(minimal_config_dict)
    config["vault"]["base_dir"] = "/tmp"
    config["vault"]["type"] = "obsidian"
    write_unit_config(wks_home, config)

    monkeypatch.setattr(
        "wks.api.vault.Vault.Vault.__enter__",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("Vault Init Error")),
    )

    result = run_cmd(cmd_check)

    assert result.success is False
    assert "Vault Init Error" in result.output["errors"][0]


def test_cmd_check_rewrites_file_urls(monkeypatch, tmp_path, minimal_config_dict):
    _, vault_dir, _ = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict)

    ext_file = (tmp_path / "external.txt").resolve()
    ext_file.write_text("external content", encoding="utf-8")
    write_vault_note(vault_dir, "note.md", f"Check this: [external]({ext_file.as_uri()})")

    result = run_cmd(cmd_check)

    assert result.success is True
    assert "[[_links/" in (vault_dir / "note.md").read_text(encoding="utf-8")
    machine = platform.node().split(".")[0]
    assert (vault_dir / "_links" / machine).exists()


def test_cmd_check_handles_missing_file_url(monkeypatch, tmp_path, minimal_config_dict):
    _, vault_dir, _ = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict)
    write_vault_note(vault_dir, "note.md", "[bad](file:///non/existent/path/file.txt)")

    result = run_cmd(cmd_check)

    assert result.success is False
    assert any("non-existent path" in err for err in result.output["errors"])


def test_cmd_check_resolves_attachment(monkeypatch, tmp_path, minimal_config_dict):
    _, vault_dir, _ = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict)
    write_vault_note(vault_dir, "_img.png", "data")
    write_vault_note(vault_dir, "note.md", "[[_img.png]]")

    result = run_cmd(cmd_check)

    assert result.success is True
    assert result.output["links_checked"] >= 1


def test_cmd_check_single_note_and_broken_link(monkeypatch, tmp_path, minimal_config_dict):
    _, vault_dir, _ = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict)
    write_vault_note(vault_dir, "valid.md", "# Valid")
    write_vault_note(vault_dir, "broken.md", "[[nonexistent]]")

    note_result = run_cmd(cmd_check, uri=URI("vault:///valid.md"))
    broken_result = run_cmd(cmd_check)

    assert note_result.success is True
    assert note_result.output["notes_checked"] == 1
    assert broken_result.success is False
    assert broken_result.output["broken_count"] == 1
    assert broken_result.output["is_valid"] is False


def test_cmd_check_scanner_errors(monkeypatch, tmp_path, minimal_config_dict):
    _, vault_dir, _ = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict)

    unreadable = vault_dir / "unreadable.md"
    unreadable.write_text("# Secret", encoding="utf-8")
    unreadable.chmod(0o000)

    rewrite_fail = vault_dir / "rewrite_fail.md"
    target = (tmp_path / "target.txt").resolve()
    target.touch()
    rewrite_fail.write_text(f"[link]({target.as_uri()})", encoding="utf-8")
    rewrite_fail.chmod(0o444)

    try:
        result = run_cmd(cmd_check)
    finally:
        unreadable.chmod(0o644)
        rewrite_fail.chmod(0o644)

    assert result.output["notes_checked"] >= 2
    assert any("unreadable.md" in err for err in result.output["errors"])
    assert any("Failed to rewrite" in err or "Permission" in err for err in result.output["errors"])
