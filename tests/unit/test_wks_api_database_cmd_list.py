from typing import cast
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from tests.unit.conftest import run_cmd
from wks.api.database.cmd_list import cmd_list

pytestmark = pytest.mark.database


class TestCmdList:
    def test_cmd_list_success(self, tracked_wks_config):
        with patch("wks.api.database.cmd_list.Database.list_databases", return_value=["nodes", "vault", "transform"]):
            result = run_cmd(cmd_list)
            assert result.success
            assert set(result.output.keys()) == {"errors", "warnings", "prefix", "databases"}
            assert result.output["errors"] == []
            assert result.output["warnings"] == []
            assert result.output["prefix"] == tracked_wks_config.database.prefix
            assert set(result.output["databases"]) == {"nodes", "vault", "transform"}
            assert "Found" in result.result
            assert "database" in result.result

    def test_cmd_list_empty(self, tracked_wks_config):
        with patch("wks.api.database.cmd_list.Database.list_databases", return_value=[]):
            result = run_cmd(cmd_list)
            assert result.success
            assert result.output["errors"] == []
            assert result.output["warnings"] == []
            assert result.output["prefix"] == tracked_wks_config.database.prefix
            assert result.output["databases"] == []

    def test_cmd_list_error(self, tracked_wks_config):
        with patch("wks.api.database.cmd_list.Database.list_databases", side_effect=Exception("Connection failed")):
            result = run_cmd(cmd_list)
            assert not result.success
            assert set(result.output.keys()) == {"errors", "warnings", "prefix", "databases"}
            assert result.output["warnings"] == []
            assert result.output["databases"] == []
            assert "Connection failed" in result.output["errors"][0]
            assert "Failed to list databases" in result.result

    def test_cmd_list_load_config_error(self, monkeypatch):
        from wks.api.config.WKSConfig import WKSConfig

        monkeypatch.setattr(WKSConfig, "load", lambda: (_ for _ in ()).throw(RuntimeError("bad config")))
        result = run_cmd(cmd_list)
        assert result.success is False
        assert set(result.output.keys()) == {"errors", "warnings", "prefix", "databases"}
        assert result.output["prefix"] == ""
        assert result.output["databases"] == []
        assert result.output["warnings"] == []
        assert "bad config" in result.output["errors"][0]

    def test_cmd_list_names_strip_prefix(self, monkeypatch, tmp_path, minimal_config_dict):
        """Verify that listed databases (collections) have prefix stripped and prefix is returned separately."""
        import json

        from wks.api.database.Database import Database
        from wks.api.database.DatabaseConfig import DatabaseConfig

        wks_home = tmp_path / "env1/.wks"
        wks_home.mkdir(parents=True)
        monkeypatch.setenv("WKS_HOME", str(wks_home))

        cfg = minimal_config_dict
        prefix = "wks_test_1"
        cfg["database"]["prefix"] = prefix
        cfg["database"]["type"] = "mongomock"
        (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

        db_cfg = DatabaseConfig(type="mongomock", prefix=prefix, prune_frequency_secs=3600, data=cast(BaseModel, {}))

        # Create collections (names should NOT include prefix here because Database facade prepends it)
        with Database(db_cfg, "nodes") as db:
            db.update_one({"id": 1}, {"$set": {"id": 1}}, upsert=True)

        with Database(db_cfg, "vault") as db:
            db.update_one({"id": 1}, {"$set": {"id": 1}}, upsert=True)

        # Run the command
        result = run_cmd(cmd_list)

        assert result.success is True
        assert result.output["prefix"] == prefix
        # Databases should be 'monitor' and 'vault'
        assert "nodes" in result.output["databases"]
        assert "vault" in result.output["databases"]
        assert f"{prefix}.monitor" not in result.output["databases"]

        # Ensure they are sorted
        assert result.output["databases"] == sorted(result.output["databases"])

    def test_cmd_list_names_exclude_other_prefixes(self, monkeypatch, tmp_path, minimal_config_dict):
        """Verify that only collections with the correct prefix are listed by the command."""
        import json

        from wks.api.database.Database import Database
        from wks.api.database.DatabaseConfig import DatabaseConfig

        wks_home = tmp_path / "env2/.wks"
        wks_home.mkdir(parents=True)
        monkeypatch.setenv("WKS_HOME", str(wks_home))

        cfg = minimal_config_dict
        prefix = "wks_test_2"
        cfg["database"]["prefix"] = prefix
        cfg["database"]["type"] = "mongomock"
        (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

        # db_cfg = DatabaseConfig(type="mongomock", prefix=prefix, data=cast(BaseModel, {}))
        other_prefix = "other"
        other_cfg = DatabaseConfig(
            type="mongomock", prefix=other_prefix, prune_frequency_secs=3600, data=cast(BaseModel, {})
        )

        # Create other prefixed collection (DB "other", collection "nodes")
        with Database(other_cfg, "nodes") as db:
            db.update_one({"id": 1}, {"$set": {"id": 1}}, upsert=True)

        # Run the command for prefix "wks_test_2"
        result = run_cmd(cmd_list)

        assert result.success is True
        assert result.output["prefix"] == prefix
        # Should NOT find 'monitor' because it's only in the 'other' database
        assert "monitor" not in result.output["databases"]


def test_cmd_list_list_databases_error(tracked_wks_config):
    """Test error in cmd_list when list_databases fails."""
    with patch("wks.api.database.cmd_list.Database.list_databases", side_effect=Exception("List error")):
        result = run_cmd(cmd_list)
        assert not result.success
        assert "List error" in result.output["errors"][0]
