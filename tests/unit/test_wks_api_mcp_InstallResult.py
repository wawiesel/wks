"""Unit tests for wks.api.mcp.InstallResult."""

from pathlib import Path

from wks.api.mcp.InstallResult import InstallResult


def test_install_result_creation():
    """Test InstallResult instantiation."""
    result = InstallResult(
        client="vscode",
        path=Path("/tmp/foo"),
        status="installed",
        message="OK",
    )
    assert result.client == "vscode"
    assert result.status == "installed"
    assert str(result.path) == "/tmp/foo"
