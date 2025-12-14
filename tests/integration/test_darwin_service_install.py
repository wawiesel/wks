"""Integration test for macOS launchd service installation.

This test verifies that the macOS service backend can actually install, start, stop,
and uninstall launchd user services.

Requires macOS (Darwin) platform.
"""

import os
import platform
import shutil
import subprocess
from contextlib import suppress
from pathlib import Path

import pytest

from wks.api.config.WKSConfig import WKSConfig
from wks.api.service.Service import Service


def _check_launchctl_available() -> bool:
    """Check if launchctl is available (macOS only).

    This check verifies that launchctl command exists and can be used.
    """
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
    # Only run on macOS - test platform-specific code on the appropriate platform
    if platform.system() != "Darwin":
        pytest.skip(f"macOS service tests only run on macOS (current platform: {platform.system()})")

    # On macOS, launchctl must be available
    if not _check_launchctl_available():
        pytest.fail(
            "launchctl not available - this test requires macOS with launchctl "
            "(run on macOS or in a macOS CI environment)"
        )

    # Set up WKS_HOME
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # Create minimal config with macOS service backend
    config_dict = {
        "monitor": {
            "filter": {
                "include_paths": [],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": [],
                "exclude_globs": [],
            },
            "priority": {
                "dirs": {},
                "weights": {
                    "depth_multiplier": 0.9,
                    "underscore_multiplier": 0.5,
                    "only_underscore_multiplier": 0.1,
                    "extension_weights": {},
                },
            },
            "database": "monitor",
            "sync": {
                "max_documents": 1000000,
                "min_priority": 0.0,
                "prune_interval_secs": 300.0,
            },
        },
        "database": {
            "type": "mongomock",
            "prefix": "wks",
            "data": {},
        },
        "service": {
            "type": "darwin",
            "sync_interval_secs": 60.0,
            "data": {
                "label": "com.test.wks.integration",
                "keep_alive": False,
                "run_at_load": False,
            },
        },
        "daemon": {
            "sync_interval_secs": 0.1,
        },
    }

    config = WKSConfig.model_validate(config_dict)
    config.save()

    # Get expected plist path
    plist_path = Path.home() / "Library" / "LaunchAgents" / "com.test.wks.integration.plist"
    uid = os.getuid()
    service_domain = f"gui/{uid}/com.test.wks.integration"

    # Clean up any existing service before starting
    with suppress(Exception):
        subprocess.run(
            ["launchctl", "bootout", service_domain],
            capture_output=True,
            text=True,
            check=False,
        )
    if plist_path.exists():
        plist_path.unlink()

    # Ensure wksc is available in PATH for the service installation
    # The service needs to find wksc command
    import sys

    venv_bin = Path(sys.executable).parent
    if str(venv_bin) not in os.environ.get("PATH", ""):
        monkeypatch.setenv("PATH", f"{venv_bin}:{os.environ.get('PATH', '')}")

    # Verify wksc is available
    wksc_path = shutil.which("wksc")
    if not wksc_path:
        pytest.skip("wksc command not found in PATH - install package with 'pip install -e .'")

    # Initialize service
    with Service(config.service) as service:
        # 1. Install service
        install_result = service.install_service()
        assert install_result["success"] is True
        assert install_result["type"] == "darwin"
        assert install_result["label"] == "com.test.wks.integration"
        assert Path(install_result["plist_path"]).exists()
        assert plist_path.exists()

        # 2. Check status (should be installed but may or may not be running depending on run_at_load)
        status = service.get_service_status()
        assert status["installed"] is True
        # run_at_load is False, so it should not be running initially
        assert status.get("running", False) is False

        # 3. Start service
        # Note: The service might fail to actually run the daemon (due to config issues),
        # but we're testing the service lifecycle, not the daemon functionality
        start_result = service.start_service()
        if not start_result.get("success"):
            # Print error for debugging
            error_msg = start_result.get("error", "Unknown error")
            log_path = wks_home / "logs" / "service.log"
            log_content = ""
            if log_path.exists():
                log_content = f"\nLog file contents:\n{log_path.read_text()[-500:]}"
            pytest.fail(f"Service start failed: {error_msg}{log_content}")
        assert start_result["success"] is True

        # 4. Check status
        # The service might not have a PID if the daemon failed to start,
        # but we can verify the service was at least loaded in launchctl
        import time

        time.sleep(0.5)  # Give launchctl time to register the service
        status = service.get_service_status()
        assert status["installed"] is True

        # Verify service is loaded in launchctl (even if daemon failed to run)
        result = subprocess.run(
            ["launchctl", "print", service_domain],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            pytest.fail(f"Service not loaded in launchctl after start. launchctl output: {result.stderr}")

        # If we got a PID, verify it's valid
        if "pid" in status and status["pid"] is not None:
            assert status["pid"] > 0

        # 5. Stop service
        stop_result = service.stop_service()
        assert stop_result["success"] is True

        # 6. Check status (should be installed but not running)
        status = service.get_service_status()
        assert status["installed"] is True
        assert status.get("running", False) is False

        # 7. Uninstall service
        uninstall_result = service.uninstall_service()
        assert uninstall_result["success"] is True

        # 8. Check status (should not be installed)
        status = service.get_service_status()
        assert status["installed"] is False
        assert not plist_path.exists()
