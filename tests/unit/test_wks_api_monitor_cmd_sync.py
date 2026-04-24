import os
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.unit._monitor_test_helpers import create_watch_dir, include_watch_dir
from tests.unit.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.monitor.cmd_sync import cmd_sync


@pytest.mark.monitor
@pytest.mark.parametrize(
    ("mode", "build", "expected"),
    [
        (
            "file",
            lambda watch_dir: (
                (watch_dir / "sync_me.txt").write_text("Sync Content", encoding="utf-8"),
                watch_dir / "sync_me.txt",
            )[1],
            1,
        ),
        (
            "recursive",
            lambda watch_dir: (
                (
                    (watch_dir / "sub").mkdir(),
                    (watch_dir / "f1.txt").write_text("f1"),
                    (watch_dir / "sub" / "f2.txt").write_text("f2"),
                )
                and watch_dir
            ),
            2,
        ),
    ],
)
def test_monitor_cmd_sync_basic_modes(wks_home, build, expected, mode):
    """Requirements:
    - MON-001
    - MON-005"""
    watch_dir = create_watch_dir(wks_home)
    target = build(watch_dir)

    config = WKSConfig.load()
    include_watch_dir(config, watch_dir)

    result = run_cmd(cmd_sync, uri=URI.from_path(target), recursive=mode == "recursive")

    assert result.success is True
    assert result.output["files_synced"] == expected


@pytest.mark.monitor
def test_monitor_cmd_sync_missing_path_removes_from_db(wks_home):
    """Requirements:
    - MON-001
    - MON-005"""
    watch_dir = create_watch_dir(wks_home)
    test_file = watch_dir / "gone.txt"
    test_file.write_text("Temporary", encoding="utf-8")

    config = WKSConfig.load()
    include_watch_dir(config, watch_dir)
    run_cmd(cmd_sync, uri=URI.from_path(test_file))
    test_file.unlink()

    result = run_cmd(cmd_sync, uri=URI.from_path(test_file))

    assert result.success is True
    assert "Removed" in result.result
    with Database(config.database, "nodes") as db:
        assert db.find_one({"local_uri": str(URI.from_path(test_file))}) is None


@pytest.mark.monitor
@pytest.mark.parametrize(
    ("mutate_config", "filename"),
    [
        (lambda config: setattr(config.monitor, "min_priority", 50.0), "low_priority.txt"),
        (lambda config: setattr(config.monitor.filter, "exclude_globs", ["*.tmp"]), "skip_me.tmp"),
    ],
)
def test_monitor_cmd_sync_skips_filtered_targets(wks_home, mutate_config, filename):
    """Requirements:
    - MON-001
    - MON-005"""
    config = WKSConfig.load()
    mutate_config(config)
    watch_dir = create_watch_dir(wks_home)
    include_watch_dir(config, watch_dir)
    target = watch_dir / filename
    target.write_text("ignored", encoding="utf-8")

    result = run_cmd(cmd_sync, uri=URI.from_path(target))

    assert result.success is True
    assert result.output["files_synced"] == 0
    assert result.output["files_skipped"] == 1


@pytest.mark.monitor
def test_monitor_cmd_sync_enforces_limit(tracked_wks_config, wks_home):
    """Requirements:
    - MON-001
    - MON-005"""
    tracked_wks_config.monitor.max_documents = 2
    watch_dir = create_watch_dir(wks_home)
    tracked_wks_config.monitor.filter.include_paths.append(str(watch_dir))

    with Database(tracked_wks_config.database, "nodes") as db:
        db.insert_one({"local_uri": "file:///low", "priority": 1.0, "checksum": "abc"})
        db.insert_one({"local_uri": "file:///mid", "priority": 2.0, "checksum": "def"})
        db.insert_one({"local_uri": "file:///high", "priority": 100.0, "checksum": "ghi"})

    test_file = watch_dir / "1.txt"
    test_file.write_text("1")

    with patch("wks.api.monitor._sync_uri.calculate_priority", return_value=200.0):
        result = run_cmd(cmd_sync, uri=URI.from_path(test_file))

    assert result.success is True
    with Database(tracked_wks_config.database, "nodes") as db:
        assert db.count_documents({"doc_type": {"$ne": "meta"}}) <= 2
        assert db.find_one({"local_uri": "file:///low"}) is None
        assert db.find_one({"local_uri": "file:///mid"}) is None
        assert db.find_one({"local_uri": "file:///high"}) is not None


@pytest.mark.monitor
def test_monitor_cmd_sync_loop_exception(wks_home):
    """Requirements:
    - MON-001
    - MON-008"""
    watch_dir = create_watch_dir(wks_home)
    unreadable = watch_dir / "unreadable.txt"
    unreadable.write_text("Secret", encoding="utf-8")
    unreadable.chmod(0o000)

    try:
        config = WKSConfig.load()
        include_watch_dir(config, watch_dir)

        result = run_cmd(cmd_sync, uri=URI.from_path(watch_dir), recursive=True)

        assert result.success is False
        assert len(result.output["errors"]) == 1
        assert "unreadable.txt" in result.output["errors"][0]
    finally:
        unreadable.chmod(0o644)


@pytest.mark.monitor
def test_monitor_cmd_sync_directory_processes_newest_first(wks_home):
    """Requirements:
    - MON-001
    - MON-005"""
    watch_dir = create_watch_dir(wks_home)
    config = WKSConfig.load()
    include_watch_dir(config, watch_dir)

    old_file = watch_dir / "old.txt"
    mid_file = watch_dir / "mid.txt"
    new_file = watch_dir / "new.txt"
    for path in (old_file, mid_file, new_file):
        path.write_text(path.stem)

    base_time = 1_700_000_000.0
    os.utime(old_file, (base_time, base_time))
    os.utime(mid_file, (base_time + 100, base_time + 100))
    os.utime(new_file, (base_time + 200, base_time + 200))

    processed: list[Path] = []
    from wks.api.config import file_checksum as checksum_module

    original = checksum_module.file_checksum

    def capturing(path: Path) -> str:
        processed.append(path)
        return original(path)

    with patch.object(checksum_module, "file_checksum", side_effect=capturing):
        result = run_cmd(cmd_sync, uri=URI.from_path(watch_dir), recursive=True)

    assert result.success is True
    assert result.output["files_synced"] == 3
    assert processed == [new_file, mid_file, old_file]
