from pathlib import Path

from wks.api.log.read_log_entries import read_log_entries


def test_read_log_entries_no_log(tmp_path):
    assert read_log_entries(tmp_path / "missing.log") == ([], [])


def test_read_log_entries_success(tmp_path):
    from datetime import datetime, timezone

    log_path = tmp_path / "test.log"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
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

    warnings, errors = read_log_entries(log_path)

    assert len(errors) == 2  # New Error, Legacy ERROR
    assert len(warnings) == 2  # New Warn, Legacy WARN

    content = log_path.read_text(encoding="utf-8")
    assert "Old Error" not in content


def test_read_log_entries_invalid_date(tmp_path):
    log_path = tmp_path / "junk.log"
    log_path.write_text("[INVALID_DATE] [test] ERROR: msg\n", encoding="utf-8")
    _warnings, errors = read_log_entries(log_path)
    assert len(errors) == 1  # Treated as 'now', so not expired


def test_read_log_entries_dotted_domain_pruned(tmp_path):
    from datetime import datetime, timezone

    log_path = tmp_path / "test.log"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    old = "2020-01-01T10:00:00+00:00"

    log_path.write_text(
        f"[{now}] [link.sync] ERROR: Recent sync failure\n[{old}] [link.sync] ERROR: Old sync failure\n",
        encoding="utf-8",
    )

    _warnings, errors = read_log_entries(log_path)
    assert len(errors) == 1  # Only recent error kept
    assert "Recent sync failure" in errors[0]

    content = log_path.read_text(encoding="utf-8")
    assert "Old sync failure" not in content


def test_read_log_entries_os_error(tmp_path, monkeypatch):
    log_path = tmp_path / "fail.log"
    log_path.touch()

    def mock_read_text(*args, **kwargs):
        raise OSError("read fail")

    monkeypatch.setattr(Path, "read_text", mock_read_text)

    warnings, _errors = read_log_entries(log_path)
    assert any("read fail" in w for w in warnings)
