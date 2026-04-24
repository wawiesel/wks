from pathlib import Path

import pytest

from tests.unit.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.link.cmd_check import cmd_check


def ensure_monitored_root(tracked_wks_config, root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    tracked_wks_config.monitor.filter.include_paths.append(str(root))
    return root


@pytest.mark.parametrize("uri", [URI.from_path(Path("missing.md").absolute()), URI("http://example.com")])
def test_cmd_check_rejects_invalid_targets(tracked_wks_config, uri):
    result = run_cmd(cmd_check, uri=uri)

    assert result.success is False
    assert result.output["errors"]


def test_cmd_check_not_monitored(tracked_wks_config, tmp_path):
    outside_file = tmp_path / "outside.md"
    outside_file.write_text("[[link]]", encoding="utf-8")

    result = run_cmd(cmd_check, uri=URI.from_path(outside_file))

    assert result.success is True
    assert result.output["is_monitored"] is False
    assert "File is not in monitor allowed list" in result.output["errors"]


def test_cmd_check_read_error(tracked_wks_config, tmp_path, monkeypatch):
    unreadable = tmp_path / "unreadable.md"
    unreadable.touch()
    unreadable.chmod(0o000)

    try:
        monkeypatch.setattr(Path, "read_text", lambda self, **kwargs: (_ for _ in ()).throw(ValueError("fail")))
        result = run_cmd(cmd_check, uri=URI.from_path(unreadable))
    finally:
        unreadable.chmod(0o644)

    assert result.success is False
    assert "Cannot read file" in result.output["errors"][0]


def test_cmd_check_success_with_vault_resolution(tracked_wks_config, tmp_path):
    vault_root = ensure_monitored_root(tracked_wks_config, Path(tracked_wks_config.vault.base_dir).expanduser())
    file_path = vault_root / "note.md"
    file_path.write_text("[[target]] [link](file:///etc/hosts) [rel](other.md)", encoding="utf-8")

    result = run_cmd(cmd_check, uri=URI.from_path(file_path))

    assert result.success is True
    assert result.output["is_monitored"] is True
    links = {link["to_local_uri"]: link for link in result.output["links"]}
    assert {"vault:///target.md", "file:///etc/hosts", str(URI.from_path(vault_root / "other.md"))} <= set(links)


def test_cmd_check_process_link_exception(tracked_wks_config, tmp_path, monkeypatch):
    vault_root = ensure_monitored_root(tracked_wks_config, Path(tracked_wks_config.vault.base_dir).expanduser())
    file_path = vault_root / "err.md"
    file_path.write_text("[[target]]", encoding="utf-8")

    from wks.api.link.cmd_check import resolve_remote_uri

    def selective_resolve(path, cfg):
        if "target.md" in str(path):
            raise RuntimeError("fail inside process_link")
        return resolve_remote_uri(path, cfg)

    monkeypatch.setattr("wks.api.link.cmd_check.resolve_remote_uri", selective_resolve)

    result = run_cmd(cmd_check, uri=URI.from_path(file_path))

    assert result.success is True
    assert result.output["links"][0]["to_remote_uri"] is None


@pytest.mark.parametrize(
    ("content", "expected_target"),
    [
        ("[link](file:///etc/hosts)", "file:///etc/hosts"),
        ("[link](http://example.com)", "http://example.com"),
        ("[link](vault:///target.md)", "vault:///target.md"),
    ],
)
def test_cmd_check_fallback_without_vault(tracked_wks_config, tmp_path, monkeypatch, content, expected_target):
    monitored_root = ensure_monitored_root(tracked_wks_config, tmp_path / "monitored")
    file_path = monitored_root / "note.md"
    file_path.write_text(content, encoding="utf-8")

    import wks.api.link.cmd_check as cmd_check_mod

    monkeypatch.setattr(
        cmd_check_mod.Vault, "__enter__", lambda self: (_ for _ in ()).throw(RuntimeError("Vault init failed"))
    )

    result = run_cmd(cmd_check, uri=URI.from_path(file_path))

    assert result.success is True
    assert any(expected_target in str(link.get("to_local_uri", "")) for link in result.output["links"])


def test_cmd_check_parser_error(tracked_wks_config, tmp_path, monkeypatch):
    file_path = tmp_path / "exists.md"
    file_path.touch()
    monkeypatch.setattr(
        "wks.api.link.cmd_check.get_parser", lambda _parser, _path: (_ for _ in ()).throw(RuntimeError("parser fail"))
    )

    result = run_cmd(cmd_check, uri=URI.from_path(file_path))

    assert result.success is False
    assert "parser fail" in result.output["errors"][0]
