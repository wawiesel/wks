from datetime import datetime, timedelta, timezone

from tests.unit.conftest import run_cmd
from wks.api.log.cmd_prune import cmd_prune


def test_cmd_prune_no_log(tracked_wks_config, monkeypatch, tmp_path):
    """Test prune when no log file exists (lines 38-51)."""
    from wks.api.config.WKSConfig import WKSConfig

    log_path = WKSConfig.get_logfile_path()
    if log_path.exists():
        log_path.unlink()

    result = run_cmd(cmd_prune)
    assert result.success is True
    assert result.output["pruned_debug"] == 0


def test_cmd_prune_success(tracked_wks_config, tmp_path):
    """Test successful pruning (lines 53-150)."""
    from wks.api.config.WKSConfig import WKSConfig

    log_path = WKSConfig.get_logfile_path()
    if not log_path.parent.exists():
        log_path.parent.mkdir(parents=True)

    # 1. Format that matches LOG_PATTERN
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=10)).isoformat()
    log_path.write_text(f"[{old}] [test] INFO: old\nLegacy INFO entry\n", encoding="utf-8")

    # Prune info
    result = run_cmd(cmd_prune, prune_info=True)
    assert result.success is True
    # Default retention for INFO is 2d, so old is gone.
    # Legacy INFO should also be gone if upper contains INFO
    assert result.output["pruned_info"] >= 1
    assert "old" not in log_path.read_text()


def test_cmd_prune_all_levels(tracked_wks_config, tmp_path):
    """Test pruning all levels (lines 100-112)."""
    from wks.api.config.WKSConfig import WKSConfig

    log_path = WKSConfig.get_logfile_path()
    log_path.write_text("DEBUG: d\nINFO: i\nWARN: w\nERROR: e\n", encoding="utf-8")

    result = run_cmd(
        cmd_prune,
        prune_debug=True,
        prune_info=True,
        prune_warnings=True,
        prune_errors=True,
    )
    assert result.success is True
    assert result.output["pruned_debug"] == 1
    assert result.output["pruned_info"] == 1
    assert result.output["pruned_warnings"] == 1
    assert result.output["pruned_errors"] == 1
    assert log_path.read_text() == ""


def test_cmd_prune_write_error(tracked_wks_config, tmp_path, monkeypatch):
    """Test error during write (lines 121-134)."""
    from wks.api.config.WKSConfig import WKSConfig

    log_path = WKSConfig.get_logfile_path()
    log_path.write_text("content", encoding="utf-8")

    from pathlib import Path

    def mock_write_text(*args, **kwargs):
        raise Exception("write fail")

    monkeypatch.setattr(Path, "write_text", mock_write_text)

    result = run_cmd(cmd_prune)
    assert result.success is False
    assert "write fail" in result.output["errors"][0]


def test_cmd_prune_os_error_read(tracked_wks_config, tmp_path, monkeypatch):
    """Test OSError handling (lines 55-57)."""
    from wks.api.config.WKSConfig import WKSConfig

    log_path = WKSConfig.get_logfile_path()
    if not log_path.parent.exists():
        log_path.parent.mkdir(parents=True)
    log_path.write_text("some content", encoding="utf-8")

    from pathlib import Path

    def mock_read_text(*args, **kwargs):
        raise OSError("fail read")

    monkeypatch.setattr(Path, "read_text", mock_read_text)

    result = run_cmd(cmd_prune)
    assert result.success is False
    assert "fail read" in result.output["errors"][0]
