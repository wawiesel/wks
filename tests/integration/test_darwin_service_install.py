import os
import platform
import shutil
import subprocess
import sys
from contextlib import suppress
from pathlib import Path

import pytest

from tests.conftest import build_service_test_config, run_cmd


def _check_launchctl_available() -> bool:
    if platform.system() != "Darwin":
        return False
    try:
        result = subprocess.run(
            ["launchctl", "version"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


@pytest.mark.integration
@pytest.mark.darwin_service
def test_darwin_service_install_lifecycle(tmp_path, monkeypatch):
    """Test full lifecycle: install, start, status, stop, uninstall.

    This test REQUIRES macOS (Darwin) and launchctl.
    On non-macOS platforms, this test is skipped (we test platform-specific code on the appropriate platform).
    """

    def _wait_for_status(service, running: bool, timeout_sec: int = 10):
        import time

        start = time.time()
        while time.time() - start < timeout_sec:
            status = service.get_service_status()
            if status.installed and status.running == running:
                return status
            time.sleep(0.5)
        status = service.get_service_status()
        assert status.installed is True
        assert status.running is running, f"Service failed to reach running={running} within {timeout_sec}s"
        return status

    if platform.system() != "Darwin":
        pytest.skip(f"macOS service tests only run on macOS (current platform: {platform.system()})")

    if not _check_launchctl_available():
        pytest.fail(
            "launchctl not available - this test requires macOS with launchctl "
            "(run on macOS or in a macOS CI environment)"
        )

    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    config = build_service_test_config(
        tmp_path,
        service_type="darwin",
        service_data={"label": "com.test.wks.integration", "keep_alive": False, "run_at_load": False},
        log_overrides={
            "debug_retention_days": 1.0,
            "info_retention_days": 1.0,
            "warning_retention_days": 1.0,
            "error_retention_days": 1.0,
        },
    )
    config.save()

    plist_path = Path.home() / "Library" / "LaunchAgents" / "com.test.wks.integration.plist"
    uid = os.getuid()
    service_domain = f"gui/{uid}/com.test.wks.integration"

    with suppress(Exception):
        subprocess.run(
            ["launchctl", "bootout", service_domain],
            capture_output=True,
            text=True,
            check=False,
        )
    if plist_path.exists():
        plist_path.unlink()

    venv_bin = Path(sys.executable).parent
    if str(venv_bin) not in os.environ.get("PATH", ""):
        monkeypatch.setenv("PATH", f"{venv_bin}:{os.environ.get('PATH', '')}")

    wksc_path = shutil.which("wksc")
    if not wksc_path:
        pytest.skip("wksc command not found in PATH - install package with 'pip install -e .'")

    from wks.api.service.cmd_install import cmd_install
    from wks.api.service.cmd_start import cmd_start
    from wks.api.service.cmd_status import cmd_status
    from wks.api.service.cmd_stop import cmd_stop
    from wks.api.service.cmd_uninstall import cmd_uninstall

    result = run_cmd(cmd_install)
    assert result.success is True
    assert result.output["installed"] is True
    assert plist_path.exists()

    result = run_cmd(cmd_status)
    assert result.success is True
    assert result.output["installed"] is True
    assert result.output["running"] is False

    result = run_cmd(cmd_start)

    import time

    time.sleep(0.5)  # Give launchctl time to register the service

    proc_result = subprocess.run(
        ["launchctl", "print", service_domain],
        capture_output=True,
        text=True,
        check=False,
    )

    if proc_result.returncode != 0:
        error_msg = result.result
        log_path = wks_home / "logs" / "service.log"
        log_content = ""
        if log_path.exists():
            log_content = f"\nLog file contents:\n{log_path.read_text()[-500:]}"
        pytest.fail(f"Service not loaded in launchctl: {error_msg}{log_content}")

    assert result.success is True

    def _wait_for_cmd_status(running: bool, timeout_sec: int = 10):
        start = time.time()
        while time.time() - start < timeout_sec:
            res = run_cmd(cmd_status)
            if res.output["installed"] and res.output["running"] == running:
                return res
            time.sleep(0.5)
        res = run_cmd(cmd_status)
        assert res.output["installed"] is True
        assert res.output["running"] is running, f"Service failed to reach running={running} within {timeout_sec}s"
        return res

    result = _wait_for_cmd_status(running=True)
    assert result.output["pid"] is not None

    result = run_cmd(cmd_stop)
    assert result.success is True

    result = _wait_for_cmd_status(running=False)
    assert result.output["installed"] is True
    assert result.output["running"] is False

    result = run_cmd(cmd_uninstall)
    assert result.success is True

    result = run_cmd(cmd_status)
    assert result.output["installed"] is False
    assert not plist_path.exists()
