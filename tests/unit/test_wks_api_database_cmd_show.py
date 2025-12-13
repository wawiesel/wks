"""Unit tests for database cmd_show."""

import json
from unittest.mock import patch

import pytest

from tests.unit.conftest import run_cmd
from wks.api.database.cmd_show import cmd_show
from wks.api.database.Database import Database

pytestmark = pytest.mark.db


class TestCmdShow:
    def test_cmd_show_success(self, tracked_wks_config):
        mock_result = {"results": [{"_id": "1", "path": "/test"}], "count": 1}
        with patch.object(Database, "query", return_value=mock_result) as mock_query:
            result = run_cmd(cmd_show, database="monitor", query='{"status": "active"}', limit=10)
            assert result.success
            assert result.output["count"] == 1
            assert result.output["database"] == "monitor"
            mock_query.assert_called_once_with(tracked_wks_config.database, "monitor", {"status": "active"}, 10)

    def test_cmd_show_no_filter(self, tracked_wks_config):
        with patch.object(Database, "query", return_value={"results": [], "count": 0}) as mock_query:
            result = run_cmd(cmd_show, database="monitor", query=None, limit=50)
            assert result.success
            assert result.output["count"] == 0
            mock_query.assert_called_once_with(tracked_wks_config.database, "monitor", None, 50)

    def test_cmd_show_invalid_json(self, tracked_wks_config):
        result = run_cmd(cmd_show, database="monitor", query='{"invalid": json}', limit=50)
        assert not result.success
        assert "Invalid JSON" in result.result
        assert result.output["errors"]

    def test_cmd_show_empty_string_filter(self, tracked_wks_config):
        with patch.object(Database, "query", return_value={"results": [], "count": 0}) as mock_query:
            result = run_cmd(cmd_show, database="monitor", query="", limit=50)
            assert result.success
            mock_query.assert_called_once_with(tracked_wks_config.database, "monitor", None, 50)

    def test_cmd_show_query_fails(self, tracked_wks_config):
        with patch.object(Database, "query", side_effect=Exception("Connection failed")):
            result = run_cmd(cmd_show, database="monitor", query='{"status": "active"}', limit=50)
            assert not result.success
            assert "Connection failed" in result.output["errors"][0]

    def test_cmd_show_complex_filter(self, tracked_wks_config):
        complex_filter = '{"age": {"$gt": 18}, "name": {"$regex": "^A"}}'
        with patch.object(Database, "query", return_value={"results": [{"_id": "1"}], "count": 1}) as mock_query:
            result = run_cmd(cmd_show, database="users", query=complex_filter, limit=100)
            assert result.success
            mock_query.assert_called_once_with(tracked_wks_config.database, "users", json.loads(complex_filter), 100)
