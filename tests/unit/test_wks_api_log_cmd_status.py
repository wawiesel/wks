"""Unit tests for wks.api.log.cmd_status."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from wks.api.log.cmd_status import cmd_status
from wks.api.config.WKSConfig import WKSConfig
from tests.unit.conftest import run_cmd, minimal_wks_config

@pytest.mark.log
def test_cmd_status_success(monkeypatch, tmp_path):
    """Test log status command reads logfile correctly."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    logfile = wks_home / "logfile"
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    logfile.write_text(f"[{now}] [test] INFO: hello\n")

    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # Mock WKSConfig.load to return a valid config
    cfg = minimal_wks_config()
    with patch("wks.api.config.WKSConfig.WKSConfig.load", return_value=cfg):
        result = run_cmd(cmd_status)

    assert result.success is True
    assert result.output["log_path"] == str(logfile)
    assert result.output["entry_counts"]["info"] == 1
    assert result.output["size_bytes"] > 0
