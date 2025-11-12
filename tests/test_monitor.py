
import unittest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path
import os
import time
import json
from datetime import datetime, timedelta

from wks.monitor import WKSFileMonitor, start_monitoring
import wks.monitor
from watchdog.events import FileSystemEvent, DirCreatedEvent, FileCreatedEvent, FileModifiedEvent, FileMovedEvent, FileDeletedEvent, DirDeletedEvent, DirModifiedEvent, DirMovedEvent

class TestWKSFileMonitor(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path('/tmp/wks_test_monitor')
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.temp_dir / 'state.json'
        self.on_change_mock = MagicMock()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        monitor = WKSFileMonitor(self.state_file)
        self.assertEqual(monitor.state_file, self.state_file)
        self.assertIsNotNone(monitor.ignore_patterns)
        self.assertIsNotNone(monitor.ignore_dirs)

    def test_load_state_no_file(self):
        monitor = WKSFileMonitor(self.state_file)
        self.assertEqual(monitor.state, {"files": {}, "last_update": None})

    def test_load_state_with_file(self):
        state = {"files": {"/tmp/wks_test_monitor/a.txt": {}}, "last_update": "2025-01-01T00:00:00"}
        with open(self.state_file, 'w') as f:
            json.dump(state, f)
        monitor = WKSFileMonitor(self.state_file)
        self.assertEqual(monitor.state, state)

    def test_load_state_corrupted_file(self):
        with open(self.state_file, 'w') as f:
            f.write("corrupted")
        monitor = WKSFileMonitor(self.state_file)
        self.assertEqual(monitor.state, {"files": {}, "last_update": None})
        self.assertTrue((self.state_file.with_suffix('.json.backup')).exists())

    def test_save_state(self):
        monitor = WKSFileMonitor(self.state_file)
        monitor.state = {"files": {"/tmp/wks_test_monitor/a.txt": {}}, "last_update": None}
        monitor._save_state()
        with open(self.state_file, 'r') as f:
            state = json.load(f)
        self.assertIn("last_update", state)
        self.assertIsNotNone(state["last_update"])

    def test_should_ignore(self):
        monitor = WKSFileMonitor(self.state_file, ignore_globs=['*.log'])
        self.assertTrue(monitor._should_ignore('/tmp/wks_test_monitor/.git/hooks'))
        self.assertTrue(monitor._should_ignore('/tmp/wks_test_monitor/node_modules/lib'))
        self.assertTrue(monitor._should_ignore('/tmp/wks_test_monitor/test.log'))
        self.assertFalse(monitor._should_ignore('/tmp/wks_test_monitor/a.txt'))

    def test_track_change(self):
        monitor = WKSFileMonitor(self.state_file, on_change=self.on_change_mock)
        file_path = self.temp_dir / 'a.txt'
        file_path.touch()
        monitor._track_change('created', str(file_path))
        self.assertIn(str(file_path.resolve()), monitor.state['files'])
        self.on_change_mock.assert_called_with('created', str(file_path.resolve()))

    def test_on_created(self):
        monitor = WKSFileMonitor(self.state_file, on_change=self.on_change_mock)
        file_path = self.temp_dir / 'a.txt'
        file_path.touch()
        event = FileCreatedEvent(str(file_path))
        monitor.on_created(event)
        self.assertIn(str(file_path.resolve()), monitor.state['files'])
        self.on_change_mock.assert_called_with('created', str(file_path.resolve()))

    def test_on_modified(self):
        monitor = WKSFileMonitor(self.state_file, on_change=self.on_change_mock)
        file_path = self.temp_dir / 'a.txt'
        file_path.touch()
        monitor._track_change('created', str(file_path))
        event = FileModifiedEvent(str(file_path))
        monitor.on_modified(event)
        self.assertEqual(len(monitor.state['files'][str(file_path.resolve())]['modifications']), 2)
        self.on_change_mock.assert_called_with('modified', str(file_path.resolve()))

    def test_on_moved(self):
        monitor = WKSFileMonitor(self.state_file, on_change=self.on_change_mock)
        src_path = self.temp_dir / 'a.txt'
        src_path.touch()
        monitor._track_change('created', str(src_path))
        dest_path = self.temp_dir / 'b.txt'
        event = FileMovedEvent(str(src_path), str(dest_path))
        monitor.on_moved(event)
        self.assertIn(str(dest_path.resolve()), monitor.state['files'])
        self.on_change_mock.assert_called_with('moved', (str(src_path.resolve()), str(dest_path.resolve())))

    def test_on_deleted(self):
        monitor = WKSFileMonitor(self.state_file, on_change=self.on_change_mock)
        file_path = self.temp_dir / 'a.txt'
        file_path.touch()
        monitor._track_change('created', str(file_path))
        event = FileDeletedEvent(str(file_path))
        monitor.on_deleted(event)
        self.assertEqual(len(monitor.state['files'][str(file_path.resolve())]['modifications']), 2)
        self.on_change_mock.assert_called_with('deleted', str(file_path.resolve()))

    def test_get_recent_changes(self):
        monitor = WKSFileMonitor(self.state_file)
        file_path = self.temp_dir / 'a.txt'
        file_path.touch()
        monitor._track_change('created', str(file_path))
        time.sleep(0.1)
        recent_changes = monitor.get_recent_changes(hours=1)
        self.assertIn(str(file_path.resolve()), recent_changes)

class TestStartMonitoring(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path('/tmp/wks_test_monitor_start')
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.temp_dir / 'state.json'

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    @patch('wks.monitor.PollingObserver')
    @patch('wks.monitor.KqueueObserver')
    @patch('wks.monitor.FSEventsObserver')
    @patch('wks.monitor.Observer')
    def test_start_monitoring(self, mock_observer, mock_fsevents, mock_kqueue, mock_polling):
        # Make all observers available
        wks.monitor.FSEventsObserver = mock_fsevents
        wks.monitor.KqueueObserver = mock_kqueue
        wks.monitor.PollingObserver = mock_polling
        wks.monitor.Observer = mock_observer
        
        mock_observer_instance = mock_observer.return_value
        mock_fsevents_instance = mock_fsevents.return_value
        mock_kqueue_instance = mock_kqueue.return_value
        mock_polling_instance = mock_polling.return_value

        observer = start_monitoring([self.temp_dir], self.state_file)
        self.assertIsNotNone(observer)

        # Check that one of the observers was used
        scheduled = False
        for instance in [mock_observer_instance, mock_fsevents_instance, mock_kqueue_instance, mock_polling_instance]:
            if instance.schedule.called:
                scheduled = True
                break
        self.assertTrue(scheduled)

        started = False
        for instance in [mock_observer_instance, mock_fsevents_instance, mock_kqueue_instance, mock_polling_instance]:
            if instance.start.called:
                started = True
                break
        self.assertTrue(started)


if __name__ == '__main__':
    unittest.main()
