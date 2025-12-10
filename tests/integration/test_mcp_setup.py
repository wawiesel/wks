from pathlib import Path

from wks.api.config.WKSConfig import WKSConfig
from wks.mcp import mcp_socket_path


def test_mcp_socket_path_uses_wks_home(monkeypatch, tmp_path):
    """mcp_socket_path should always resolve under the WKS home directory."""
    monkeypatch.setattr(WKSConfig, "get_home_dir", classmethod(lambda cls: tmp_path))

    path = mcp_socket_path()
    assert isinstance(path, Path)
    assert path == tmp_path / "mcp.sock"
