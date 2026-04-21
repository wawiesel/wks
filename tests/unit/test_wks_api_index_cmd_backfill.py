"""Tests for wksc index backfill command."""

import json
from pathlib import Path

from tests.conftest import run_cmd
from wks.api.index.cmd_backfill import cmd_backfill


def _setup_backfill_env(tmp_path, monkeypatch, min_priority: float = 0.0) -> Path:
    """Set up a minimal config + monitor DB with two files."""
    from tests.conftest import minimal_config_dict

    doc_dir = tmp_path / "docs"
    doc_dir.mkdir()

    config_dict = minimal_config_dict()
    config_dict["monitor"]["filter"]["include_paths"].append(str(doc_dir))
    config_dict["monitor"]["priority"]["dirs"] = {str(doc_dir): 100.0}
    config_dict["index"] = {
        "default_index": "main",
        "indexes": {
            "main": {
                "engine": "textpass",
                "min_priority": min_priority,
            }
        },
    }

    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(config_dict))

    return doc_dir


def _populate_monitor(uris_and_priorities: list[tuple[str, float]]) -> None:
    """Insert fake monitor DB entries directly."""
    from wks.api.config.WKSConfig import WKSConfig
    from wks.api.database.Database import Database

    config = WKSConfig.load()
    with Database(config.database, "nodes") as db:
        for uri, priority in uris_and_priorities:
            db.update_one(
                {"local_uri": uri},
                {
                    "$set": {
                        "local_uri": uri,
                        "priority": priority,
                        "checksum": "abc123",
                        "bytes": 10,
                        "timestamp": "2026-01-01T00:00:00",
                    }
                },
                upsert=True,
            )


def test_backfill_indexes_monitored_files(tmp_path, monkeypatch):
    """Files in monitor DB meeting min_priority are indexed by backfill."""
    doc_dir = _setup_backfill_env(tmp_path, monkeypatch, min_priority=0.0)

    doc = doc_dir / "note.txt"
    doc.write_text("Hello world content.\n")
    from wks.api.config.URI import URI

    uri = str(URI.from_path(doc))
    _populate_monitor([(uri, 50.0)])

    result = run_cmd(cmd_backfill, "main")
    assert result.success is True
    assert result.output["indexed"] == 1
    assert result.output["skipped"] == 0
    assert result.output["errors"] == []


def test_backfill_skips_below_min_priority(tmp_path, monkeypatch):
    """Files below min_priority are not indexed."""
    doc_dir = _setup_backfill_env(tmp_path, monkeypatch, min_priority=80.0)

    doc = doc_dir / "low.txt"
    doc.write_text("Low priority content.\n")
    from wks.api.config.URI import URI

    uri = str(URI.from_path(doc))
    # Priority 10.0 < min_priority 80.0 — should not be a candidate
    _populate_monitor([(uri, 10.0)])

    result = run_cmd(cmd_backfill, "main")
    assert result.success is True
    assert result.output["indexed"] == 0
    assert result.output["skipped"] == 0
    assert result.output["errors"] == []


def test_backfill_no_index_config(tmp_path, monkeypatch):
    """Backfill fails gracefully when no index is configured."""
    from tests.conftest import minimal_config_dict

    config_dict = minimal_config_dict()
    # No index section

    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(config_dict))

    result = run_cmd(cmd_backfill, "main")
    assert result.success is False
    assert "No index" in result.result


def test_backfill_unknown_index(tmp_path, monkeypatch):
    """Backfill fails gracefully with unknown index name."""
    _setup_backfill_env(tmp_path, monkeypatch)

    result = run_cmd(cmd_backfill, "nonexistent")
    assert result.success is False
    assert "nonexistent" in result.result


def test_backfill_empty_monitor(tmp_path, monkeypatch):
    """Backfill returns success when no monitored files exist."""
    _setup_backfill_env(tmp_path, monkeypatch, min_priority=0.0)

    result = run_cmd(cmd_backfill, "main")
    assert result.success is True
    assert result.output["indexed"] == 0
    assert result.output["skipped"] == 0
    assert result.output["errors"] == []
