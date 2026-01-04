from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.unit.conftest import run_cmd
from wks.api.link.cmd_sync import cmd_sync
from wks.api.URI import URI


def test_cmd_sync_path_not_found(tracked_wks_config):
    """Test path not found (lines 35-45)."""
    result = run_cmd(cmd_sync, uri=URI.from_path(Path("missing.md").absolute()))
    assert result.success is False
    assert "Path does not exist" in result.output["errors"]


def test_cmd_sync_no_files(tracked_wks_config, tmp_path):
    """Test no matching files found (lines 62-72)."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    result = run_cmd(cmd_sync, uri=URI.from_path(empty_dir))
    assert result.success is True
    assert result.output["links_synced"] == 0
    assert "No matching files found" in result.output["errors"]


def test_cmd_sync_success(tracked_wks_config, tmp_path):
    """Test successful link sync (lines 76-97)."""
    vault_root = Path(tracked_wks_config.vault.base_dir).expanduser()
    if not vault_root.exists():
        vault_root.mkdir(parents=True)
    tracked_wks_config.monitor.filter.include_paths.append(str(vault_root))

    file_path = vault_root / "note.md"
    file_path.write_text("[link](file:///etc/hosts)", encoding="utf-8")

    result = run_cmd(cmd_sync, uri=URI.from_path(file_path))
    assert result.success is True
    assert result.output["links_synced"] == 1

    from wks.api.database.Database import Database

    with Database(tracked_wks_config.database, "edges") as db:
        docs = list(db.find({}))
        assert len(docs) == 1
        assert docs[0]["to_local_uri"] == "file:///etc/hosts"


def test_cmd_sync_fallback_no_vault(tracked_wks_config, tmp_path, monkeypatch):
    """Test fallback when vault is not configured (lines 98-114)."""
    from wks.api.vault.Vault import Vault

    monkeypatch.setattr(Vault, "__enter__", lambda self: exec("raise Exception('vault fail')"))

    monitored_root = tmp_path / "monitored"
    monitored_root.mkdir()
    tracked_wks_config.monitor.filter.include_paths.append(str(monitored_root))
    file_path = monitored_root / "note.md"
    file_path.write_text("[link](file:///etc/hosts)", encoding="utf-8")

    result = run_cmd(cmd_sync, uri=URI.from_path(file_path))
    assert result.success is True
    assert result.output["links_synced"] == 1


def test_cmd_sync_with_remote_targets(tracked_wks_config, tmp_path):
    """Test sync with remote targets (lines 126-130 in helper)."""
    vault_root = Path(tracked_wks_config.vault.base_dir).expanduser()
    if not vault_root.exists():
        vault_root.mkdir(parents=True)
    tracked_wks_config.monitor.filter.include_paths.append(str(vault_root))

    file_path = vault_root / "remote.md"
    file_path.write_text("[google](https://google.com)", encoding="utf-8")

    result = run_cmd(cmd_sync, uri=URI.from_path(file_path), remote=True)
    assert result.success is True
    assert result.output["links_synced"] == 1


def test_sync_single_file_monitor_error(tracked_wks_config, tmp_path, monkeypatch):
    """Test non-fatal monitor registration error (lines 35-43 in helper)."""
    vault_root = Path(tracked_wks_config.vault.base_dir).expanduser()
    if not vault_root.exists():
        vault_root.mkdir(parents=True)

    monkeypatch.setattr(
        "wks.api.monitor.cmd_sync.cmd_sync",
        lambda *args, **kwargs: exec("raise Exception('monitor fail')"),
    )

    file_path = vault_root / "mon_err.md"
    file_path.write_text("[link](file:///etc/hosts)", encoding="utf-8")

    result = run_cmd(cmd_sync, uri=URI.from_path(file_path))
    assert result.success is True
    assert result.output["links_synced"] == 1


def test_sync_single_file_complex_resolutions(tracked_wks_config, tmp_path, monkeypatch):
    """Test various resolution paths in _sync_single_file (lines 70-113)."""
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    tracked_wks_config.vault.base_dir = str(vault_root)
    tracked_wks_config.monitor.filter.include_paths.append(str(vault_root))

    file_path = vault_root / "complex.md"
    file_path.write_text("[[broken]] [vlt](vault:///some/file.md) [rel](other.md)", encoding="utf-8")

    def mock_resolver(target):
        mock_meta = MagicMock()
        if target == "broken" or target == "target":
            mock_meta.status = "broken"
        else:
            mock_meta.status = "ok"
            mock_meta.target_uri = f"vault:///{target}.md"
        return mock_meta

    with patch("wks.api.vault.Vault.Vault.resolve_link", side_effect=mock_resolver):
        result = run_cmd(cmd_sync, uri=URI.from_path(file_path))
        assert result.success is True
        assert result.output["links_synced"] == 2


def test_cmd_sync_expand_error(tracked_wks_config, tmp_path, monkeypatch):
    """Test FileNotFoundError in expand_paths (lines 50-60)."""
    from wks.api.link import cmd_sync as cmd_sync_mod

    monkeypatch.setattr(
        cmd_sync_mod,
        "expand_paths",
        lambda *args, **kwargs: exec("raise FileNotFoundError('missing folder')"),
    )

    result = run_cmd(cmd_sync, uri=URI.from_path(tmp_path))
    assert result.success is False
    assert "missing folder" in result.output["errors"][0]


def test_sync_single_file_fatal_error(tracked_wks_config, tmp_path, monkeypatch):
    """Test general exception in _sync_single_file (lines 163-169 in helper)."""
    from wks.api.link import _sync_single_file as sync_helper

    monkeypatch.setattr(sync_helper, "get_parser", lambda *args: exec("raise RuntimeError('fatal sync')"))

    file_path = tmp_path / "note.md"
    file_path.touch()

    result = run_cmd(cmd_sync, uri=URI.from_path(file_path))
    assert result.success is True
    assert "fatal sync" in result.output["errors"][0]


def test_sync_single_file_remote_error(tracked_wks_config, tmp_path, monkeypatch):
    """Test exception in target remote resolution (lines 112-113 in helper)."""
    vault_root = Path(tracked_wks_config.vault.base_dir).expanduser()
    if not vault_root.exists():
        vault_root.mkdir(parents=True)
    tracked_wks_config.monitor.filter.include_paths.append(str(vault_root))

    file_path = vault_root / "rem_err.md"
    file_path.write_text("[link](file:///etc/hosts)", encoding="utf-8")

    from wks.api.link._sync_single_file import resolve_remote_uri

    original_resolver = resolve_remote_uri

    def selective_resolver(path, cfg):
        if str(path).endswith("hosts"):
            raise RuntimeError("fail target remote")
        return original_resolver(path, cfg)

    monkeypatch.setattr("wks.api.link._sync_single_file.resolve_remote_uri", selective_resolver)

    result = run_cmd(cmd_sync, uri=URI.from_path(file_path))
    assert result.success is True
    assert result.output["links_synced"] == 1


def test_sync_single_file_remote_uri_found(tracked_wks_config, tmp_path):
    """Test branch where remote_uri is found for target (line 110)."""
    from wks.api.monitor.RemoteMapping import RemoteMapping

    vault_root = Path(tracked_wks_config.vault.base_dir).expanduser()
    if not vault_root.exists():
        vault_root.mkdir(parents=True)
    tracked_wks_config.monitor.filter.include_paths.append(str(vault_root))
    tracked_wks_config.monitor.remote.mappings = [RemoteMapping(local_path=str(vault_root), remote_uri="https://rem")]

    file_path = vault_root / "rem_found.md"
    file_path.write_text(f"[link](file://{vault_root}/target.md)", encoding="utf-8")
    (vault_root / "target.md").touch()

    result = run_cmd(cmd_sync, uri=URI.from_path(file_path))
    assert result.success is True
    assert result.output["links_synced"] == 1

    from wks.api.database.Database import Database

    with Database(tracked_wks_config.database, "edges") as db:
        docs = list(db.find({}))
        target_doc = next((d for d in docs if "target.md" in str(d.get("to_local_uri"))), None)
        assert target_doc is not None, f"No record found in {docs}. Sync output: {result.output}"
        assert target_doc["to_remote_uri"] == "https://rem/target.md"


def test_sync_single_file_normalize_error(tracked_wks_config, tmp_path, monkeypatch):
    """Test exception in normalize_path (lines 104-105 in helper)."""
    file_path = tmp_path / "note.md"
    file_path.write_text("[link](target.md)", encoding="utf-8")

    test_uri = URI.from_path(file_path)

    # We can't easily capture original if we haven't imported it, but we can assume it works if we don't patch
    # Actually, we need to import it to wrap it
    from wks.utils.normalize_path import normalize_path as real_norm

    def mock_norm(p):
        if "target.md" in str(p):
            raise RuntimeError("norm fail")
        return real_norm(p)

    monkeypatch.setattr("wks.utils.normalize_path.normalize_path", mock_norm)

    result = run_cmd(cmd_sync, uri=test_uri)
    assert result.success is True


def test_parsers_coverage(tracked_wks_config, tmp_path):
    """Test various parsers (HTML, RST, Raw) to reach 100% in link domain."""
    monitored_root = tmp_path / "monitored"
    monitored_root.mkdir()
    tracked_wks_config.monitor.filter.include_paths.append(str(monitored_root))

    # 1. HTML Parser (edge cases: empty href, fragments + valid link/image)
    html_file = monitored_root / "test.html"
    html_content = (
        '<a href="">none</a> <a href="#top">top</a> <img src=""> <a href="http://e.com">ok</a> <img src="i.png">'
    )
    html_file.write_text(html_content, encoding="utf-8")

    # 2. RST Parser
    rst_file = monitored_root / "test.rst"
    rst_file.write_text("`link <http://example.com>`_\n\n.. image:: img.png", encoding="utf-8")

    # 3. Raw Parser
    raw_file = monitored_root / "test.txt"
    raw_file.write_text("Check http://example.com and https://google.com", encoding="utf-8")

    # 4. Markdown Parser
    md_file = monitored_root / "test.md"
    md_content = "[link](http://m.com) ![img](http://i.com) [[target|alias]] [[target2\\|alias2]]"
    md_file.write_text(md_content, encoding="utf-8")

    # Sync all
    result = run_cmd(cmd_sync, uri=URI.from_path(monitored_root), recursive=True)
    assert result.success is True
    assert result.output["links_found"] >= 7


def test_get_parser_invalid(tracked_wks_config):
    """Test invalid parser name or unknown extension."""
    from wks.api.link._parsers import RawParser, get_parser

    # 1. Unknown extension
    assert get_parser(file_path=Path("test.unknown")).__class__ == RawParser

    # 2. Invalid name
    import pytest

    with pytest.raises(ValueError, match="Unknown parser: invalid"):
        get_parser("invalid", Path("test.md"))


def test_cmd_sync_non_file_uri(tracked_wks_config):
    """Test non-file URI returns structured error instead of crashing (Codex P1)."""
    uri = URI("http://example.com")
    result = run_cmd(cmd_sync, uri=uri)
    assert result.success is False
    assert result.output is not None
    assert "Only file URIs are supported" in result.output["errors"][0]
