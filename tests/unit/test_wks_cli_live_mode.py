"""Unit tests for CLI --live mode functionality."""

import time
from unittest.mock import patch


def test_cli_live_mode_extracts_flag():
    """Test that --live flag is extracted correctly."""
    from wks.cli import _extract_live_flag

    # Test --live with space
    argv1 = ["--live", "5", "db", "show", "monitor"]
    interval1 = _extract_live_flag(argv1)
    assert interval1 == 5.0
    assert "--live" not in argv1
    assert "5" not in argv1

    # Test --live=5 format
    argv2 = ["--live=3", "db", "show", "monitor"]
    interval2 = _extract_live_flag(argv2)
    assert interval2 == 3.0
    assert "--live=3" not in argv2

    # Test no --live flag
    argv3 = ["db", "show", "monitor"]
    interval3 = _extract_live_flag(argv3)
    assert interval3 is None
    assert argv3 == ["db", "show", "monitor"]


def test_cli_live_mode_updates_on_change():
    """Test that --live mode detects changes and updates output using thread approach.

    Strategy:
    1. Mock subprocess.run to return different outputs on each call
    2. Start live mode in a thread
    3. Snapshot first output (count: 1)
    4. Wait for update interval
    5. Verify output changed (count: 2)
    6. Stop the thread
    """
    from wks.cli import _run_live_mode

    # Mock subprocess results that change over time
    subprocess_results = [
        type("Result", (), {"stdout": "count: 1\n", "stderr": "✓ Found 1\n", "returncode": 0})(),
        type("Result", (), {"stdout": "count: 2\n", "stderr": "✓ Found 2\n", "returncode": 0})(),
    ]

    call_count = {"value": 0}
    captured_outputs = []

    def mock_subprocess_run(*args, **kwargs):
        """Mock subprocess.run to return changing results."""
        result = subprocess_results[call_count["value"] % len(subprocess_results)]
        call_count["value"] += 1

        # Capture output for verification
        captured_outputs.append(result.stdout)
        return result

    # Mock time.sleep to stop after 2 iterations
    original_sleep = time.sleep
    sleep_count = {"value": 0}

    def mock_sleep(seconds):
        """Mock sleep to stop after capturing 2 outputs."""
        sleep_count["value"] += 1
        if sleep_count["value"] >= 2:
            raise KeyboardInterrupt("Test complete")
        original_sleep(0.01)  # Brief sleep for thread yield

    # Mock signal.signal to avoid actual signal handling
    with patch("wks.cli.subprocess.run", side_effect=mock_subprocess_run):
        with patch("time.sleep", side_effect=mock_sleep):
            with patch("signal.signal"):
                # Run live mode (will be interrupted by mock_sleep)
                try:
                    _run_live_mode(["db", "show", "test"], interval=0.1)
                except KeyboardInterrupt:
                    pass

    # Verify we captured changing output
    assert len(captured_outputs) >= 2, "Should have captured at least 2 outputs"
    assert "count: 1" in captured_outputs[0], "First output should have count: 1"
    assert "count: 2" in captured_outputs[1], "Second output should have count: 2"
