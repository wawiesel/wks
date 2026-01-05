from datetime import datetime, timedelta, timezone

from tests.unit.conftest import run_cmd
from wks.api.log.cmd_status import cmd_status


def test_cmd_status_no_log(tracked_wks_config, isolated_wks_home):
    """Test status when log file does not exist (lines 35-43)."""
    from wks.api.config.WKSConfig import WKSConfig

    log_path = WKSConfig.get_logfile_path()
    if log_path.exists():
        log_path.unlink()

    result = run_cmd(cmd_status)
    assert result.success is True
    assert result.output["entry_counts"]["info"] == 0


def test_cmd_status_success(tracked_wks_config, isolated_wks_home):
    """Test successful status with entries (lines 45-136)."""
    from wks.api.config.WKSConfig import WKSConfig

    log_path = WKSConfig.get_logfile_path()
    if not log_path.parent.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=10)).isoformat()

    log_path.write_text(
        f"[{now.isoformat()}] [test] INFO: msg1\n"
        f"[{now.isoformat()}] [test] ERROR: msg2\n"
        f"[{old}] [test] INFO: expired\n"
        "Legacy WARN entry\n"
        "DEBUG: legacy debug\n",
        encoding="utf-8",
    )

    result = run_cmd(cmd_status)
    assert result.success is True
    # Info: 1 kept, 1 expired
    assert result.output["entry_counts"]["info"] == 1
    # Error: 1 kept
    assert result.output["entry_counts"]["error"] == 1
    # Warn: 1 legacy kept
    assert result.output["entry_counts"]["warn"] == 1
    # Debug: 1 legacy kept
    assert result.output["entry_counts"]["debug"] == 1

    assert result.output["size_bytes"] > 0
    assert result.output["oldest_entry"] is not None


def test_cmd_status_parse_error(tracked_wks_config, isolated_wks_home):
    """Test unparseable date (lines 84-85)."""
    from wks.api.config.WKSConfig import WKSConfig

    log_path = WKSConfig.get_logfile_path()
    if not log_path.parent.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("[BAD_DATE] [test] INFO: msg\n", encoding="utf-8")

    result = run_cmd(cmd_status)
    assert result.success is True
    assert result.output["entry_counts"]["info"] == 1


def test_cmd_status_read_error(tracked_wks_config, isolated_wks_home, monkeypatch):
    """Test error during read (lines 61-68)."""
    from wks.api.config.WKSConfig import WKSConfig

    log_path = WKSConfig.get_logfile_path()
    if not log_path.parent.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("content", encoding="utf-8")

    from pathlib import Path

    def mock_read_text(*args, **kwargs):
        raise Exception("read fail")

    monkeypatch.setattr(Path, "read_text", mock_read_text)

    result = run_cmd(cmd_status)
    assert result.success is False
    assert "read fail" in result.output["errors"][0]
