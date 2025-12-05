import json
import shutil
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from watchdog.events import FileCreatedEvent, FileDeletedEvent, FileModifiedEvent, FileMovedEvent

from wks.monitor import WKSFileMonitor, start_monitoring
from wks.monitor_rules import MonitorRules

pytestmark = pytest.mark.monitor


class TestWKSFileMonitor(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path("/tmp/wks_test_monitor")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.temp_dir / "state.json"
        self.on_change_mock = MagicMock()
        self.rules = MonitorRules(
            include_paths=[str(self.temp_dir)],
            exclude_paths=[],
            include_dirnames=[],
            exclude_dirnames=[],
            include_globs=[],
            exclude_globs=[],
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _build_monitor(self, rules: MonitorRules | None = None):
        return WKSFileMonitor(self.state_file, rules or self.rules, on_change=self.on_change_mock)

    def test_initialization_loads_empty_state(self):
        monitor = self._build_monitor()
        self.assertEqual(monitor.state_file, self.state_file)
        self.assertEqual(monitor.state, {"files": {}, "last_update": None})

    def test_load_state_from_disk(self):
        stored = {
            "files": {str(self.temp_dir / "foo.md"): {}},
            "last_update": "2025-01-01T00:00:00",
        }
        self.state_file.write_text(json.dumps(stored))
        monitor = self._build_monitor()
        self.assertEqual(monitor.state, stored)

    def test_corrupted_state_creates_backup(self):
        self.state_file.write_text("corrupted")
        monitor = self._build_monitor()
        self.assertEqual(monitor.state, {"files": {}, "last_update": None})
        self.assertTrue(self.state_file.with_suffix(".json.backup").exists())

    def test_save_state_updates_timestamp(self):
        monitor = self._build_monitor()
        monitor.state["files"][str(self.temp_dir / "keep.md")] = {"modifications": []}
        monitor._save_state()
        saved = json.loads(self.state_file.read_text())
        self.assertIn("last_update", saved)
        self.assertIsNotNone(saved["last_update"])

    def test_should_ignore_respects_dirnames_and_globs(self):
        rules = MonitorRules(
            include_paths=[str(self.temp_dir)],
            exclude_paths=[],
            include_dirnames=[],
            exclude_dirnames=["node_modules"],
            include_globs=[],
            exclude_globs=["*.log"],
        )
        monitor = self._build_monitor(rules)
        self.assertTrue(monitor._should_ignore(str(self.temp_dir / "node_modules" / "pkg")))
        self.assertTrue(monitor._should_ignore(str(self.temp_dir / "error.log")))
        self.assertFalse(monitor._should_ignore(str(self.temp_dir / "notes.md")))

    def test_include_dirname_overrides_exclusion(self):
        rules = MonitorRules(
            include_paths=[str(self.temp_dir)],
            exclude_paths=[],
            include_dirnames=["_inbox"],
            exclude_dirnames=["_build"],
            include_globs=[],
            exclude_globs=["**/_*"],
        )
        monitor = self._build_monitor(rules)
        forced = self.temp_dir / "_inbox" / "keep.txt"
        forced.parent.mkdir(exist_ok=True)
        forced.touch()
        rejected = self.temp_dir / "_build" / "skip.txt"
        rejected.parent.mkdir(exist_ok=True)
        rejected.touch()
        self.assertFalse(monitor._should_ignore(str(forced)))
        self.assertTrue(monitor._should_ignore(str(rejected)))

    def test_reserved_dot_directories_always_ignored(self):
        monitor = self._build_monitor()
        path = self.temp_dir / ".wks" / "artifact.txt"
        path.parent.mkdir(exist_ok=True)
        path.touch()
        self.assertTrue(monitor._should_ignore(str(path)))

    def test_track_change_records_modification(self):
        monitor = self._build_monitor()
        file_path = self.temp_dir / "a.txt"
        file_path.touch()
        monitor._track_change("created", str(file_path))
        key = str(file_path.resolve())
        self.assertIn(key, monitor.state["files"])
        self.on_change_mock.assert_called_with("created", key)

    def test_event_handlers(self):
        monitor = self._build_monitor()
        file_path = self.temp_dir / "doc.md"
        file_path.touch()

        monitor.on_created(FileCreatedEvent(str(file_path)))
        monitor.on_modified(FileModifiedEvent(str(file_path)))
        monitor.on_moved(FileMovedEvent(str(file_path), str(self.temp_dir / "moved.md")))
        monitor.on_deleted(FileDeletedEvent(str(file_path)))

        key = str((self.temp_dir / "moved.md").resolve())
        self.assertIn(key, monitor.state["files"])
        self.assertTrue(monitor.state["files"][key]["modifications"])

    def test_get_recent_changes_filters_by_time(self):
        monitor = self._build_monitor()
        file_path = self.temp_dir / "recent.txt"
        file_path.touch()
        monitor._track_change("created", str(file_path))
        time.sleep(0.1)
        recent = monitor.get_recent_changes(hours=1)
        self.assertIn(str(file_path.resolve()), recent)


class TestStartMonitoring(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path("/tmp/wks_test_monitor_start")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.temp_dir / "state.json"
        self.rules = MonitorRules(
            include_paths=[str(self.temp_dir)],
            exclude_paths=[],
            include_dirnames=[],
            exclude_dirnames=[],
            include_globs=[],
            exclude_globs=[],
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    @patch("wks.filesystem_monitor.PollingObserver")
    @patch("wks.filesystem_monitor.KqueueObserver")
    @patch("wks.filesystem_monitor.FSEventsObserver")
    @patch("wks.filesystem_monitor.Observer")
    def test_start_monitoring_selects_available_observer(self, mock_observer, mock_fsevents, mock_kqueue, mock_polling):
        import wks.filesystem_monitor as monitor_mod

        monitor_mod.FSEventsObserver = mock_fsevents
        monitor_mod.KqueueObserver = mock_kqueue
        monitor_mod.PollingObserver = mock_polling
        monitor_mod.Observer = mock_observer

        observer = start_monitoring(
            [self.temp_dir],
            self.state_file,
            monitor_rules=self.rules,
        )
        self.assertIsNotNone(observer)
        scheduled = any(
            instance.schedule.called
            for instance in [
                mock_observer.return_value,
                mock_fsevents.return_value,
                mock_kqueue.return_value,
                mock_polling.return_value,
            ]
        )
        self.assertTrue(scheduled)


if __name__ == "__main__":
    unittest.main()
