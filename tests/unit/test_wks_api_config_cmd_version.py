"""Unit tests for wks.api.config.cmd_version module."""

from unittest.mock import patch

import pytest

from tests.unit.conftest import run_cmd
from wks.api.config import cmd_version

pytestmark = pytest.mark.config


def test_cmd_version_with_git_sha(monkeypatch):
    """Test cmd_version when git SHA is available."""
    monkeypatch.setattr("wks.api.config.cmd_version.get_package_version", lambda: "0.4.0")

    # Mock subprocess to return git SHA
    mock_output = b"abc1234\n"
    monkeypatch.setattr("wks.api.config.cmd_version.subprocess.check_output", lambda *args, **kwargs: mock_output)

    result = run_cmd(cmd_version.cmd_version)
    assert result.success is True
    assert result.output["version"] == "0.4.0"
    assert result.output["git_sha"] == "abc1234"
    assert result.output["full_version"] == "0.4.0 (abc1234)"
    assert result.output["errors"] == []
    assert result.output["warnings"] == []


def test_cmd_version_without_git_sha(monkeypatch):
    """Test cmd_version when git SHA is not available."""
    monkeypatch.setattr("wks.api.config.cmd_version.get_package_version", lambda: "0.4.0")

    # Mock subprocess to raise exception (git not available)
    monkeypatch.setattr("wks.api.config.cmd_version.subprocess.check_output", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("git not found")))

    result = run_cmd(cmd_version.cmd_version)
    assert result.success is True
    assert result.output["version"] == "0.4.0"
    assert result.output["git_sha"] == ""
    assert result.output["full_version"] == "0.4.0"
    assert result.output["errors"] == []
    assert result.output["warnings"] == []
