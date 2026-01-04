from pathlib import Path

from tests.unit.conftest import run_cmd
from wks.api.link.cmd_check import cmd_check
from wks.api.URI import URI


def test_cmd_check_file_not_found(tracked_wks_config):
    """Test file not found (lines 69-78)."""
    # Use URI.from_path for strict URI creation (expands path)
    result = run_cmd(cmd_check, uri=URI.from_path(Path("missing.md").absolute()))
    assert result.success is False
    assert "File does not exist" in result.output["errors"]


def test_cmd_check_not_monitored(tracked_wks_config, tmp_path):
    """Test file outside monitored roots (lines 81, 202-203)."""
    # Just use a path that is NOT in include_paths, but don't clear the list
    # (because it must at least contain the transform cache)
    outside_file = tmp_path / "outside.md"
    outside_file.write_text("[[link]]", encoding="utf-8")

    result = run_cmd(cmd_check, uri=URI.from_path(outside_file))
    assert result.success is True
    assert result.output["is_monitored"] is False
    assert "File is not in monitor allowed list" in result.output["errors"]


def test_cmd_check_read_error(tracked_wks_config, tmp_path, monkeypatch):
    """Test read error (lines 91-94)."""
    unreadable = tmp_path / "unreadable.md"
    unreadable.touch()
    unreadable.chmod(0o000)

    try:
        # Patch Path.read_text
        monkeypatch.setattr(Path, "read_text", lambda self, **kwargs: exec("raise ValueError('fail')"))
        result = run_cmd(cmd_check, uri=URI.from_path(unreadable))
        assert result.success is False
        assert "Cannot read file" in result.output["errors"][0]
    finally:
        unreadable.chmod(0o644)


def test_cmd_check_success_vault(tracked_wks_config, tmp_path):
    """Test successful link check within vault (lines 115-150)."""
    vault_root = Path(tracked_wks_config.vault.base_dir).expanduser()
    if not vault_root.exists():
        vault_root.mkdir(parents=True)

    # Register vault root in monitor include_paths
    tracked_wks_config.monitor.filter.include_paths.append(str(vault_root))

    file_path = vault_root / "note.md"
    # test multiple link types (wikilink, file uri, relative path)
    file_path.write_text("[[target]] [link](file:///etc/hosts) [rel](other.md)", encoding="utf-8")

    result = run_cmd(cmd_check, uri=URI.from_path(file_path))
    assert result.success is True
    assert result.output["is_monitored"] is True
    assert len(result.output["links"]) == 3
    links = {lk["to_local_uri"]: lk for lk in result.output["links"]}
    assert "vault:///target.md" in links
    assert "file:///etc/hosts" in links
    assert "other.md" in links


def test_cmd_check_process_link_exception(tracked_wks_config, tmp_path, monkeypatch):
    """Test exception in _process_link handles gracefully (line 36-38)."""
    vault_root = Path(tracked_wks_config.vault.base_dir).expanduser()
    if not vault_root.exists():
        vault_root.mkdir(parents=True)
    tracked_wks_config.monitor.filter.include_paths.append(str(vault_root))

    file_path = vault_root / "err.md"
    file_path.write_text("[[target]]", encoding="utf-8")

    # Selective mock to avoid failing the from_remote_uri calculation at line 131
    from wks.api.link.cmd_check import resolve_remote_uri

    original_resolve = resolve_remote_uri

    def selective_resolve(path, cfg):
        if "target.md" in str(path):
            raise RuntimeError("fail inside process_link")
        return original_resolve(path, cfg)

    monkeypatch.setattr("wks.api.link.cmd_check.resolve_remote_uri", selective_resolve)

    # Should not raise, just skip remote_uri calculation for the target
    result = run_cmd(cmd_check, uri=URI.from_path(file_path))
    assert result.success is True
    assert result.output["links"][0]["to_remote_uri"] is None


def test_cmd_check_fallback_no_vault(tracked_wks_config, tmp_path, monkeypatch):
    """Test fallback when vault is not configured or fails (lines 151-200)."""
    from wks.api.vault.Vault import Vault

    monkeypatch.setattr(Vault, "__enter__", lambda self: exec("raise Exception('vault fail')"))

    # Monitor a temp path
    monitored_root = tmp_path / "monitored"
    monitored_root.mkdir()
    tracked_wks_config.monitor.filter.include_paths.append(str(monitored_root))
    file_path = monitored_root / "note.md"
    # use a file link to trigger lines 176-180
    file_path.write_text("[link](file:///etc/hosts)", encoding="utf-8")

    result = run_cmd(cmd_check, uri=URI.from_path(file_path))
    assert result.success is True
    assert len(result.output["links"]) == 1
    assert result.output["links"][0]["to_local_uri"] == "file:///etc/hosts"
    assert result.output["links"][0]["from_local_uri"].startswith("file://")


def test_cmd_check_parser_error(tracked_wks_config, tmp_path, monkeypatch):
    """Test parser error (lines 216-225)."""
    file_path = tmp_path / "exists.md"
    file_path.touch()

    monkeypatch.setattr("wks.api.link.cmd_check.get_parser", lambda p, path: exec("raise RuntimeError('parser fail')"))

    result = run_cmd(cmd_check, uri=URI.from_path(file_path))
    assert result.success is False
    assert "parser fail" in result.output["errors"][0]


def test_cmd_check_non_file_uri(tracked_wks_config):
    """Test non-file URI returns structured error instead of crashing (Codex P1)."""
    uri = URI("http://example.com")
    result = run_cmd(cmd_check, uri=uri)
    assert result.success is False
    assert result.output is not None
    assert "Cannot resolve local path from URI" in result.output["errors"][0]
