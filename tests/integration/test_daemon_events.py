from __future__ import annotations

from datetime import datetime

import pytest

# Import shared fixtures
from tests.integration.conftest import FakeCollection, FakeIndexer, FakeVault


def _build_daemon(monkeypatch, tmp_path, collection: FakeCollection):
    from wks.api.service import daemon as daemon_mod
    from wks.api.config import (
        DisplayConfig,
        MetricsConfig,
        WKSConfig,
    )
    from wks.api.db.DbConfig import DbConfig
    from wks.api.monitor.MonitorConfig import MonitorConfig
    from wks.api.transform.config import TransformConfig
    from wks.api.vault.config import VaultConfig

    monkeypatch.setattr(daemon_mod, "ObsidianVault", FakeVault)
    monkeypatch.setattr(daemon_mod, "VaultLinkIndexer", FakeIndexer)

    # Mock MongoGuard and other dependencies
    class MockMongoGuard:
        def __init__(self, *args, **kwargs):
            pass

        def start(self, *args, **kwargs):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(daemon_mod, "MongoGuard", MockMongoGuard)

    from unittest.mock import MagicMock

    mock_broker = MagicMock()
    from wks.mcp import bridge as mcp_bridge_mod
    monkeypatch.setattr(mcp_bridge_mod, "MCPBroker", lambda *_a, **_k: mock_broker)
    monkeypatch.setattr(daemon_mod, "start_monitoring", lambda *_a, **_k: MagicMock())
    monkeypatch.setattr(daemon_mod, "load_db_activity_summary", lambda: None)
    monkeypatch.setattr(daemon_mod, "load_db_activity_history", lambda *_a: [])
    # monkeypatch.setattr(daemon_mod.WKSDaemon, "_enforce_monitor_db_limit", lambda self: None)

    config = {
        "monitor": {
            "filter": {
                "include_paths": [str(tmp_path)],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": [],
                "exclude_globs": [],
            },
            "priority": {
                "dirs": {str(tmp_path): 100},
                "weights": {},
            },
            "database": "monitor",
            "sync": {
                "max_documents": 1000000,
                "prune_interval_secs": 300.0,
            },
        },
        "vault": {
            "base_dir": str(tmp_path),
            "wks_dir": "WKS",
            "update_frequency_seconds": 10,
        },
    }

    # Construct WKSConfig
    monitor_cfg = MonitorConfig.from_config_dict(config)
    vault_cfg = VaultConfig(
        base_dir=config["vault"]["base_dir"],
        wks_dir=config["vault"]["wks_dir"],
        update_frequency_seconds=config["vault"]["update_frequency_seconds"],
        database="wks.vault",
        vault_type="obsidian",
    )
    mongo_cfg = DbConfig(type="mongo", prefix="wks", data={"uri": "mongodb://localhost:27017/"})
    display_cfg = DisplayConfig()
    from pathlib import Path

    from wks.api.transform.config import CacheConfig

    transform_cfg = TransformConfig(
        cache=CacheConfig(location=Path(".wks/cache"), max_size_bytes=1024 * 1024 * 100),
        engines={},
        database="wks.transform",
    )
    metrics_cfg = MetricsConfig()

    wks_config = WKSConfig(
        monitor=monitor_cfg,
        vault=vault_cfg,
        db=mongo_cfg,
        display=display_cfg,
        transform=transform_cfg,
        metrics=metrics_cfg,
    )

    return daemon_mod.WKSDaemon(
        config=wks_config,
        vault_path=tmp_path,
        base_dir="WKS",
        monitor_paths=[tmp_path],
        monitor_collection=collection,
    )


@pytest.mark.integration
def test_move_into_tracked_directory_records_file(monkeypatch, tmp_path):
    coll = FakeCollection()
    daemon = _build_daemon(monkeypatch, tmp_path, coll)

    dest = tmp_path / "tracked" / "report.txt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("new data")
    src = tmp_path / "untracked" / "report.txt"
    src.parent.mkdir(parents=True, exist_ok=True)

    daemon._handle_move_event(str(src), str(dest))

    assert dest.as_uri() in coll.docs


@pytest.mark.integration
def test_move_directory_drops_source_but_skips_destination(monkeypatch, tmp_path):
    coll = FakeCollection()
    src = tmp_path / "projects" / "results.txt"
    src.parent.mkdir(parents=True, exist_ok=True)
    coll.docs[src.as_uri()] = {
        "path": src.as_uri(),
        "timestamp": datetime.now().isoformat(),
    }
    dest_dir = tmp_path / "archive" / "results"
    dest_dir.mkdir(parents=True, exist_ok=True)

    daemon = _build_daemon(monkeypatch, tmp_path, coll)
    daemon._handle_move_event(str(src), str(dest_dir))

    assert src.as_uri() not in coll.docs
    assert dest_dir.as_uri() not in coll.docs


@pytest.mark.integration
def test_move_tracked_file_updates_destination(monkeypatch, tmp_path):
    coll = FakeCollection()
    src = tmp_path / "reports" / "weekly.txt"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("old")
    coll.docs[src.as_uri()] = {
        "path": src.as_uri(),
        "timestamp": datetime.now().isoformat(),
    }
    dest = tmp_path / "archive" / "weekly.txt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("new")

    daemon = _build_daemon(monkeypatch, tmp_path, coll)
    daemon._handle_move_event(str(src), str(dest))

    assert src.as_uri() not in coll.docs
    assert dest.as_uri() in coll.docs


@pytest.mark.integration
def test_delete_event_only_tracks_known_paths(monkeypatch, tmp_path):
    coll = FakeCollection()
    daemon = _build_daemon(monkeypatch, tmp_path, coll)

    tracked = tmp_path / "keep.txt"
    tracked.write_text("x")
    coll.docs[tracked.as_uri()] = {
        "path": tracked.as_uri(),
        "timestamp": datetime.now().isoformat(),
    }
    untracked = tmp_path / "ignore.txt"

    daemon._handle_delete_event(untracked)
    assert not daemon._pending_deletes

    daemon._handle_delete_event(tracked)
    assert tracked.resolve().as_posix() in daemon._pending_deletes


@pytest.mark.integration
def test_delete_event_flush_removes_db_row(monkeypatch, tmp_path):
    coll = FakeCollection()
    tracked = tmp_path / "remove.txt"
    tracked.parent.mkdir(parents=True, exist_ok=True)
    tracked.write_text("bye")
    coll.docs[tracked.as_uri()] = {
        "path": tracked.as_uri(),
        "timestamp": datetime.now().isoformat(),
    }

    daemon = _build_daemon(monkeypatch, tmp_path, coll)
    daemon._delete_grace_secs = 0
    daemon._handle_delete_event(tracked)
    tracked.unlink()

    daemon._maybe_flush_pending_deletes()

    assert tracked.as_uri() not in coll.docs
    assert tracked.resolve().as_posix() not in daemon._pending_deletes
