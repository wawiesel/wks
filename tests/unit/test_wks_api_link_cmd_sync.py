from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.unit.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.link.cmd_sync import cmd_sync


def ensure_sync_root(tracked_wks_config, root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    tracked_wks_config.monitor.filter.include_paths.append(str(root))
    return root


@pytest.mark.parametrize("uri", [URI.from_path(Path("missing.md").absolute()), URI("http://example.com")])
def test_cmd_sync_rejects_invalid_targets(tracked_wks_config, uri):
    result = run_cmd(cmd_sync, uri=uri)

    assert result.success is False
    assert result.output["errors"]


def test_cmd_sync_no_files(tracked_wks_config, tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    result = run_cmd(cmd_sync, uri=URI.from_path(empty_dir))

    assert result.success is True
    assert result.output["links_synced"] == 0
    assert "No matching files found" in result.output["errors"]


def test_cmd_sync_success(tracked_wks_config):
    from wks.api.database.Database import Database

    vault_root = ensure_sync_root(tracked_wks_config, Path(tracked_wks_config.vault.base_dir).expanduser())
    file_path = vault_root / "note.md"
    file_path.write_text("[link](file:///etc/hosts)", encoding="utf-8")

    result = run_cmd(cmd_sync, uri=URI.from_path(file_path))

    assert result.success is True
    assert result.output["links_synced"] == 1
    with Database(tracked_wks_config.database, "edges") as db:
        docs = list(db.find({}))
        assert len(docs) == 1
        assert docs[0]["to_local_uri"] == "file:///etc/hosts"


def test_cmd_sync_fallback_no_vault(tracked_wks_config, tmp_path, monkeypatch):
    from wks.api.vault.Vault import Vault

    monkeypatch.setattr(Vault, "__enter__", lambda self: (_ for _ in ()).throw(Exception("vault fail")))

    monitored_root = ensure_sync_root(tracked_wks_config, tmp_path / "monitored")
    file_path = monitored_root / "note.md"
    file_path.write_text("[link](file:///etc/hosts)", encoding="utf-8")

    result = run_cmd(cmd_sync, uri=URI.from_path(file_path))

    assert result.success is True
    assert result.output["links_synced"] == 1


def test_cmd_sync_with_remote_targets(tracked_wks_config):
    vault_root = ensure_sync_root(tracked_wks_config, Path(tracked_wks_config.vault.base_dir).expanduser())
    file_path = vault_root / "remote.md"
    file_path.write_text("[google](https://google.com)", encoding="utf-8")

    result = run_cmd(cmd_sync, uri=URI.from_path(file_path), remote=True)

    assert result.success is True
    assert result.output["links_synced"] == 1


def test_sync_single_file_complex_resolutions(tracked_wks_config, tmp_path):
    vault_root = ensure_sync_root(tracked_wks_config, tmp_path / "vault")
    tracked_wks_config.vault.base_dir = str(vault_root)
    file_path = vault_root / "complex.md"
    file_path.write_text("[[broken]] [vlt](vault:///some/file.md) [rel](other.md)", encoding="utf-8")

    def mock_resolver(target):
        meta = MagicMock()
        if target in {"broken", "target"}:
            meta.status = "broken"
        else:
            meta.status = "ok"
            meta.target_uri = f"vault:///{target}.md"
        return meta

    with patch("wks.api.vault.Vault.Vault.resolve_link", side_effect=mock_resolver):
        result = run_cmd(cmd_sync, uri=URI.from_path(file_path))

    assert result.success is True
    assert result.output["links_synced"] == 2


def test_cmd_sync_expand_error(tracked_wks_config, tmp_path, monkeypatch):
    from wks.api.link import cmd_sync as cmd_sync_mod

    monkeypatch.setattr(
        cmd_sync_mod,
        "expand_paths",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError("missing folder")),
    )

    result = run_cmd(cmd_sync, uri=URI.from_path(tmp_path))

    assert result.success is False
    assert "missing folder" in result.output["errors"][0]


def test_sync_single_file_fatal_error(tracked_wks_config, tmp_path, monkeypatch):
    from wks.api.link import _sync_single_file as sync_helper

    monkeypatch.setattr(sync_helper, "get_parser", lambda *_args: (_ for _ in ()).throw(RuntimeError("fatal sync")))

    file_path = tmp_path / "note.md"
    file_path.touch()

    result = run_cmd(cmd_sync, uri=URI.from_path(file_path))

    assert result.success is True
    assert "fatal sync" in result.output["errors"][0]


def test_sync_single_file_remote_uri_found(tracked_wks_config, tmp_path):
    from wks.api.database.Database import Database
    from wks.api.monitor.RemoteMapping import RemoteMapping

    vault_root = ensure_sync_root(tracked_wks_config, Path(tracked_wks_config.vault.base_dir).expanduser())
    tracked_wks_config.monitor.remote.mappings = [RemoteMapping(local_path=str(vault_root), remote_uri="https://rem")]

    file_path = vault_root / "rem_found.md"
    file_path.write_text(f"[link](file://{vault_root}/target.md)", encoding="utf-8")
    (vault_root / "target.md").touch()

    result = run_cmd(cmd_sync, uri=URI.from_path(file_path))

    assert result.success is True
    with Database(tracked_wks_config.database, "edges") as db:
        docs = list(db.find({}))
        target_doc = next((doc for doc in docs if "target.md" in str(doc.get("to_local_uri"))), None)
        assert target_doc is not None
        assert target_doc["to_remote_uri"] == "https://rem/target.md"


def test_parsers_sync_directory(tracked_wks_config, tmp_path):
    monitored_root = ensure_sync_root(tracked_wks_config, tmp_path / "monitored")
    (monitored_root / "test.html").write_text(
        '<a href="">none</a> <a href="#top">top</a> <img src=""> <a href="http://e.com">ok</a> <img src="i.png">',
        encoding="utf-8",
    )
    (monitored_root / "test.rst").write_text("`link <http://example.com>`_\n\n.. image:: img.png", encoding="utf-8")
    (monitored_root / "test.txt").write_text("Check http://example.com and https://google.com", encoding="utf-8")
    (monitored_root / "test.md").write_text(
        "[link](http://m.com) ![img](http://i.com) [[target|alias]] [[target2\\|alias2]]",
        encoding="utf-8",
    )

    result = run_cmd(cmd_sync, uri=URI.from_path(monitored_root), recursive=True)

    assert result.success is True
    assert result.output["links_found"] >= 7
