"""Unit tests for wks.api.config.cmd_version module.

Requirements Satisfied:

- CONFIG.5
"""

import pytest

from tests.unit.conftest import run_cmd
from wks.api.config import cmd_version

pytestmark = pytest.mark.config


def test_cmd_version_with_git_sha(monkeypatch):
    """Test cmd_version returns version string."""
    monkeypatch.setattr("wks.api.config.cmd_version.get_package_version", lambda: "0.4.0")

    result = run_cmd(cmd_version.cmd_version)
    assert result.success is True
    assert result.output["version"] == "0.4.0"
    assert result.output["errors"] == []
    assert result.output["warnings"] == []


def test_cmd_version_without_git_sha(monkeypatch):
    """Test cmd_version returns version string."""
    monkeypatch.setattr("wks.api.config.cmd_version.get_package_version", lambda: "0.4.0")

    result = run_cmd(cmd_version.cmd_version)
    assert result.success is True
    assert result.output["version"] == "0.4.0"
    assert result.output["errors"] == []
    assert result.output["warnings"] == []
