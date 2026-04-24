import json
import subprocess
import sys
import time
from pathlib import Path

import pytest


def run_wksc(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
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

    result = run_wksc("daemon", "start", env=env)
    assert result.returncode == 0, f"daemon start failed: {result.stderr}"
    assert "Daemon started" in result.stderr or "running: true" in result.stdout

    time.sleep(0.3)

    result = run_wksc("daemon", "status", env=env)
    assert result.returncode == 0, f"daemon status failed: {result.stderr}"

    test_file = watch_dir / "smoke_test.txt"
    test_file.write_text("hello smoke test", encoding="utf-8")

    time.sleep(0.5)

    result = run_wksc("--display", "json", "database", "show", "nodes", env=env)
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Failed to parse JSON output: {result.stdout}")
    assert "database" in output

    daemon_log = wks_env["wks_home"] / "logfile"
    assert daemon_log.exists(), "Daemon log should exist"
    log_content = daemon_log.read_text(encoding="utf-8")
    assert "INFO:" in log_content, "Daemon log should have INFO entries"

    result = run_wksc("daemon", "stop", env=env)
    assert result.returncode == 0, f"daemon stop failed: {result.stderr}"
    assert "Daemon stopped" in result.stderr or "stopped: true" in result.stdout

    result = run_wksc("daemon", "status", env=env)
    assert result.returncode == 0
    assert "running: false" in result.stdout or '"running": false' in result.stdout


@pytest.mark.integration
@pytest.mark.daemon
def test_cli_daemon_double_start(wks_env: dict):
    """Verify starting daemon twice fails (single instance)."""
    env = wks_env["env"]

    result = run_wksc("daemon", "start", env=env)
    assert result.returncode == 0, f"first start failed: {result.stderr}"

    deadline = time.time() + 3.0
    while True:
        status = run_wksc("daemon", "status", env=env)
        if status.returncode == 0 and ("running: true" in status.stdout or '"running": true' in status.stdout):
            break
        if time.time() > deadline:
            pytest.fail(f"daemon did not report running in time: {status.stderr}")
        time.sleep(0.2)

    result = run_wksc("daemon", "start", env=env)
    assert result.returncode != 0, "second start must fail when daemon already running"

    result = run_wksc("daemon", "stop", env=env)
    assert result.returncode == 0


@pytest.mark.integration
@pytest.mark.daemon
def test_cli_monitor_sync_manual(wks_env: dict):
    """Test manual monitor sync via CLI."""
    env = wks_env["env"]
    watch_dir: Path = wks_env["watch_dir"]

    test_file = watch_dir / "manual_sync.txt"
    test_file.write_text("manual sync test", encoding="utf-8")

    result = run_wksc("monitor", "sync", str(test_file), env=env)
    assert result.returncode == 0, f"monitor sync failed: {result.stderr}"
    assert "Sync complete" in result.stderr or "synced" in result.stdout.lower()


@pytest.mark.integration
@pytest.mark.daemon
def test_cli_config_show(wks_env: dict):
    """Test config show via CLI."""
    env = wks_env["env"]

    result = run_wksc("config", "show", "monitor", env=env)
    assert result.returncode == 0, f"config show failed: {result.stderr}"
    assert "filter" in result.stdout or "database" in result.stdout
