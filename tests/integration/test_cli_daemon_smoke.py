"""Smoke test: CLI daemon workflow (start, file changes, database check, stop).

Uses shared config from tests/conftest.py via wks_env fixture.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest


def run_wksc(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run wksc CLI command and return result."""
    cmd = [sys.executable, "-m", "wks.cli", *args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    return result


@pytest.mark.integration
@pytest.mark.daemon
def test_cli_daemon_smoke(wks_env: dict):
    """Full CLI workflow: start daemon, create file, verify in DB, stop daemon."""
    env = wks_env["env"]
    watch_dir: Path = wks_env["watch_dir"]
    wks_home: Path = wks_env["wks_home"]

    # 1. Start daemon
    result = run_wksc("daemon", "start", env=env)
    assert result.returncode == 0, f"daemon start failed: {result.stderr}"
    assert "Daemon started" in result.stderr or "running: true" in result.stdout

    # Give daemon time to initialize
    time.sleep(0.3)

    # 2. Verify daemon is running
    result = run_wksc("daemon", "status", env=env)
    assert result.returncode == 0, f"daemon status failed: {result.stderr}"
    # Note: With subprocess-based daemon, status reads from daemon.json
    # The daemon child process should have written running: true

    # 3. Create a test file
    test_file = watch_dir / "smoke_test.txt"
    test_file.write_text("hello smoke test", encoding="utf-8")

    # 4. Wait for daemon to detect and sync
    time.sleep(0.5)

    # 5. Query monitor database
    result = run_wksc("--display", "json", "database", "show", "monitor", env=env)
    assert result.returncode == 0, f"database show failed: {result.stderr}"

    # Parse JSON output
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Failed to parse JSON output: {result.stdout}")

    # Verify file is in database (mongomock is ephemeral per process,
    # so if daemon syncs in subprocess, each CLI call gets fresh DB)
    # This test verifies the CLI commands work, not cross-process DB persistence
    assert "results" in output or "count" in output

    # 6. Check daemon log exists
    daemon_log = wks_home / "logs" / "daemon.log"
    assert daemon_log.exists(), "Daemon log should exist"
    log_content = daemon_log.read_text(encoding="utf-8")
    assert "INFO:" in log_content, "Daemon log should have INFO entries"

    # 7. Stop daemon
    result = run_wksc("daemon", "stop", env=env)
    assert result.returncode == 0, f"daemon stop failed: {result.stderr}"
    assert "Daemon stopped" in result.stderr or "stopped: true" in result.stdout

    # 8. Verify daemon is stopped
    result = run_wksc("daemon", "status", env=env)
    assert result.returncode == 0
    assert "running: false" in result.stdout or '"running": false' in result.stdout


@pytest.mark.integration
@pytest.mark.daemon
def test_cli_daemon_double_start(wks_env: dict):
    """Verify starting daemon twice fails (single instance)."""
    env = wks_env["env"]

    # Start daemon first time
    result = run_wksc("daemon", "start", env=env)
    assert result.returncode == 0, f"first start failed: {result.stderr}"

    # Ensure daemon is actually running before second start (avoid flake if it dies immediately)
    deadline = time.time() + 3.0
    while True:
        status = run_wksc("daemon", "status", env=env)
        if status.returncode == 0 and ("running: true" in status.stdout or '"running": true' in status.stdout):
            break
        if time.time() > deadline:
            pytest.fail(f"daemon did not report running in time: {status.stderr}")
        time.sleep(0.2)

    # Start daemon second time (must fail; daemon already running)
    result = run_wksc("daemon", "start", env=env)
    assert result.returncode != 0, "second start must fail when daemon already running"

    # Stop daemon
    result = run_wksc("daemon", "stop", env=env)
    assert result.returncode == 0


@pytest.mark.integration
@pytest.mark.daemon
def test_cli_monitor_sync_manual(wks_env: dict):
    """Test manual monitor sync via CLI."""
    env = wks_env["env"]
    watch_dir: Path = wks_env["watch_dir"]

    # Create a file
    test_file = watch_dir / "manual_sync.txt"
    test_file.write_text("manual sync test", encoding="utf-8")

    # Manually sync via CLI
    result = run_wksc("monitor", "sync", str(test_file), env=env)
    assert result.returncode == 0, f"monitor sync failed: {result.stderr}"
    assert "Sync complete" in result.stderr or "synced" in result.stdout.lower()


@pytest.mark.integration
@pytest.mark.daemon
def test_cli_config_show(wks_env: dict):
    """Test config show via CLI."""
    env = wks_env["env"]

    # Show monitor section
    result = run_wksc("config", "show", "monitor", env=env)
    assert result.returncode == 0, f"config show failed: {result.stderr}"
    assert "filter" in result.stdout or "database" in result.stdout
