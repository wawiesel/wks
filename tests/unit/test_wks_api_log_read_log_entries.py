from pathlib import Path

from wks.api.log.read_log_entries import read_log_entries


def test_read_log_entries_no_log(tmp_path):
    """Test read_log_entries when no log file exists (lines 24-25)."""
    assert read_log_entries(tmp_path / "missing.log") == ([], [])


def test_read_log_entries_success(tmp_path):
    """Test successful reading, filtering and categorization (lines 38-70)."""
    log_path = tmp_path / "test.log"
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    old = "2020-01-01T10:00:00+00:00"

    log_path.write_text(
        f"[{now}] [test] ERROR: New Error\n"
        "\n"  # Empty line (line 41)
        f"[{now}] [test] WARN: New Warn\n"
        f"[{old}] [test] ERROR: Old Error\n"
        "Legacy WARN entry\n"
        "Legacy ERROR entry\n"
        "Legacy INFO entry\n"
        f"[{now}] [test] DEBUG: New Debug\n",
        encoding="utf-8",
    )

    # Use default retention (0.5d, 1d, 2d, 7d)
    warnings, errors = read_log_entries(log_path)
    # Old Error (7d retention) should be KEPT if < 7 days old.
    # 2020 is definitely > 7 days old from 2025. So it's EXPIRED.

    assert len(errors) == 2  # New Error, Legacy ERROR
    assert len(warnings) == 2  # New Warn, Legacy WARN

    # Check if file was pruned (line 72)
    content = log_path.read_text(encoding="utf-8")
    assert "Old Error" not in content


def test_read_log_entries_invalid_date(tmp_path):
    """Test handling of invalid date (lines 50-51)."""
    log_path = tmp_path / "junk.log"
    log_path.write_text("[INVALID_DATE] [test] ERROR: msg\n", encoding="utf-8")
    _warnings, errors = read_log_entries(log_path)
    assert len(errors) == 1  # Treated as 'now', so not expired


def test_read_log_entries_os_error(tmp_path, monkeypatch):
    """Test OSError handling (lines 73-75)."""
    log_path = tmp_path / "fail.log"
    log_path.touch()

    def mock_read_text(*args, **kwargs):
        raise OSError("read fail")

    monkeypatch.setattr(Path, "read_text", mock_read_text)

    warnings, _errors = read_log_entries(log_path)
    assert any("read fail" in w for w in warnings)
