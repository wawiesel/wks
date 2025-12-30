"""Unit tests for wks.api.log.cmd_prune."""

from tests.unit.conftest import run_cmd
from wks.api.log.cmd_prune import cmd_prune


def test_cmd_prune_no_logfile(monkeypatch, tmp_path):
    """Test pruning when no log file exists."""
    from wks.api.config.WKSConfig import WKSConfig

    log_path = tmp_path / "wks.log"
    monkeypatch.setattr(WKSConfig, "get_logfile_path", lambda: log_path)

    result = run_cmd(cmd_prune)
    assert result.success
    assert result.output["message"] == "No log file found"


def test_cmd_prune_filters(monkeypatch, tmp_path):
    """Test pruning entries by level."""
    from wks.api.config.WKSConfig import WKSConfig

    log_path = tmp_path / "wks.log"
    monkeypatch.setattr(WKSConfig, "get_logfile_path", lambda: log_path)

    # Create log with various levels
    content = """
2025-01-01 12:00:00 [INFO] Keep me
2025-01-01 12:00:01 [DEBUG] Prune me
2025-01-01 12:00:02 [WARN] Keep me
2025-01-01 12:00:03 [ERROR] Keep me
Legacy debug line that might be pruned if content matches
"""
    log_path.write_text(content.strip(), encoding="utf-8")

    # Prune DEBUG only (default behaviour)
    # prune_info=True by default? docstring says yes.
    # cmd_prune(prune_info=True, prune_warnings=False, prune_errors=False, prune_debug=True)
    # Let's call with specific args to be sure
    result = run_cmd(lambda: cmd_prune(prune_info=False, prune_warnings=False, prune_errors=False, prune_debug=True))

    assert result.success
    assert result.output["pruned_debug"] > 0
    assert result.output["pruned_info"] == 0

    new_content = log_path.read_text(encoding="utf-8")
    assert "[DEBUG]" not in new_content
    assert "[INFO]" in new_content
    assert "[WARN]" in new_content


def test_cmd_prune_error_reading(monkeypatch, tmp_path):
    """Test handling of read errors."""
    from wks.api.config.WKSConfig import WKSConfig

    log_path = tmp_path / "wks.log"
    monkeypatch.setattr(WKSConfig, "get_logfile_path", lambda: log_path)

    log_path.write_text("content")
    log_path.chmod(0o000)

    try:
        result = run_cmd(cmd_prune)
        assert not result.success
        assert "Failed to read log" in result.output["message"]
    finally:
        log_path.chmod(0o644)
