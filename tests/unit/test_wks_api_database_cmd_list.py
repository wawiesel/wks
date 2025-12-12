"""Unit tests for database cmd_list."""

from unittest.mock import patch

import pytest

from tests.unit.conftest import run_cmd
from wks.api.database.cmd_list import cmd_list

pytestmark = pytest.mark.db


class TestCmdList:
    def test_cmd_list_success(self, patch_wks_config):
        with patch("wks.api.database.cmd_list.Database.list_databases", return_value=["monitor", "vault", "transform"]):
            result = run_cmd(cmd_list)
            assert result.success
            assert set(result.output["databases"]) == {"monitor", "vault", "transform"}

    def test_cmd_list_empty(self, patch_wks_config):
        with patch("wks.api.database.cmd_list.Database.list_databases", return_value=[]):
            result = run_cmd(cmd_list)
            assert result.success
            assert result.output["databases"] == []

    def test_cmd_list_error(self, patch_wks_config):
        with patch("wks.api.database.cmd_list.Database.list_databases", side_effect=Exception("Connection failed")):
            result = run_cmd(cmd_list)
            assert not result.success
            assert "Connection failed" in result.output["errors"][0]

    def test_cmd_list_load_config_error(self, monkeypatch):
        from wks.api.config.WKSConfig import WKSConfig

        monkeypatch.setattr(WKSConfig, "load", lambda: (_ for _ in ()).throw(RuntimeError("bad config")))
        result = run_cmd(cmd_list)
        assert result.success is False
        assert "bad config" in result.output["errors"][0]
