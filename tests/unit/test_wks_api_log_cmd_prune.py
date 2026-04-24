from datetime import datetime, timedelta, timezone

from tests.unit.conftest import run_cmd
from wks.api.log.cmd_prune import cmd_prune


def test_cmd_prune_no_log(tracked_wks_config, isolated_wks_home):
    from wks.api.config.WKSConfig import WKSConfig

    log_path = WKSConfig.get_logfile_path()
    if log_path.exists():
        log_path.unlink()

    result = run_cmd(cmd_prune)
    assert result.success is True
    assert result.output["pruned_debug"] == 0


def test_cmd_prune_success(tracked_wks_config, isolated_wks_home):
    from wks.api.config.WKSConfig import WKSConfig

    log_path = WKSConfig.get_logfile_path()
    if not log_path.parent.exists():
        log_path.parent.mkdir(parents=True)

    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=10)).isoformat()
    log_path.write_text(f"[{old}] [test] INFO: old\nLegacy INFO entry\n", encoding="utf-8")

    result = run_cmd(cmd_prune, prune_info=True)
    assert result.success is True
    assert result.output["pruned_info"] >= 1
    assert "old" not in log_path.read_text()


def test_cmd_prune_all_levels(tracked_wks_config, isolated_wks_home):
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


def test_cmd_prune_write_error(tracked_wks_config, isolated_wks_home, monkeypatch):
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


def test_cmd_prune_os_error_read(tracked_wks_config, isolated_wks_home, monkeypatch):
    from wks.api.config.WKSConfig import WKSConfig

    log_path = WKSConfig.get_logfile_path()
    if not log_path.parent.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("some content", encoding="utf-8")

    from pathlib import Path

    def mock_read_text(*args, **kwargs):
        raise OSError("fail read")

    monkeypatch.setattr(Path, "read_text", mock_read_text)

    result = run_cmd(cmd_prune)
    assert result.success is False
    assert "fail read" in result.output["errors"][0]
