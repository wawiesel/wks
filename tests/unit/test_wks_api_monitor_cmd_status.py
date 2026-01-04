"""Unit tests for monitor cmd_status (no mocks, real mongomock via config)."""

# HODOR-ID: TST-MON-002
# HODOR-REQS: MON-002
# HODOR-TEXT: Monitor status command returns schema-shaped output and handles database issues.
# HODOR-REF: tests/unit/test_wks_api_monitor_cmd_status.py::test_cmd_status_success
# HODOR-REF: tests/unit/test_wks_api_monitor_cmd_status.py::test_cmd_status_tracked_files_excludes_meta_document
#
# HODOR-ID: TST-MON-007-STATUS
# HODOR-REQS: MON-007
# HODOR-TEXT: Status reports schema-conformant errors when the database fails.
# HODOR-REF: tests/unit/test_wks_api_monitor_cmd_status.py::test_cmd_status_database_error

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.database.Database import Database
from wks.api.monitor.cmd_status import cmd_status

pytestmark = pytest.mark.monitor


def test_cmd_status_success(monkeypatch, tmp_path, minimal_config_dict):
    """Status succeeds with default config and no issues."""
    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg = minimal_config_dict
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_status)
    assert result.success is True
    assert result.output["tracked_files"] == 0
    assert result.output["issues"] == []


def test_cmd_status_tracked_files_excludes_meta_document(monkeypatch, tmp_path, minimal_config_dict):
    """tracked_files count should exclude the __meta__ document."""
    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg = minimal_config_dict
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Manually insert a file node and a __meta__ document
    from wks.api.config.WKSConfig import WKSConfig

    config = WKSConfig.load()
    with Database(config.database, "nodes") as db:
        # Insert a real file node
        db.update_one(
            {"local_uri": "file:///test/file.md"},
            {
                "$set": {
                    "local_uri": "file:///test/file.md",
                    "checksum": "abc123",
                    "bytes": 100,
                    "priority": 100.0,
                    "timestamp": "2024-01-01T00:00:00",
                }
            },
            upsert=True,
        )
        # Insert the __meta__ document
        db.update_one(
            {"_id": "__meta__"},
            {"$set": {"_id": "__meta__", "doc_type": "meta", "last_sync": "2024-01-01T00:00:00"}},
            upsert=True,
        )

    result = run_cmd(cmd_status)
    assert result.success is True
    # Should count only the file node, not the __meta__ document
    assert result.output["tracked_files"] == 1


def test_cmd_status_database_error(monkeypatch, tmp_path, minimal_config_dict):
    """Status handles database errors by reporting them in output."""
    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg = minimal_config_dict
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    from wks.api.monitor.cmd_status import Database

    def mock_enter(self):
        raise RuntimeError("DB Connection Failed")

    monkeypatch.setattr(Database, "__enter__", mock_enter)

    result = run_cmd(cmd_status)
    assert result.success is False
    assert any("DB Connection Failed" in err for err in result.output["errors"])
