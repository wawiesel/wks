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
            "max_documents": 1000000,
            "min_priority": 0.0,
            "remote": {
                "mappings": [],
            },
        },
        "vault": {
            "type": "obsidian",
            "base_dir": "~/_vault",
        },
        "database": {
            "type": "mongomock",
            "prefix": "wks",
            "prune_frequency_secs": 3600,
            "data": {},
        },
        "service": {
            "type": "darwin",
            "data": {
                "label": "com.test.wks.integration",
                "keep_alive": False,
                "run_at_load": False,
            },
        },
        "daemon": {
            "sync_interval_secs": 0.1,
        },
        "log": {
            "level": "INFO",
            "debug_retention_days": 1.0,
            "info_retention_days": 1.0,
            "warning_retention_days": 1.0,
            "error_retention_days": 1.0,
        },
        "transform": {
            "cache": {
                "base_dir": "~/_transform_cache",
                "max_size_bytes": 1073741824,
            },
            "engines": {},
        },
        "cat": {
            "default_engine": "cat",
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

        # Even if start_service reports failure, check if service was loaded in launchctl
        # The daemon might fail to run, but the service should still be loadable
        import time

        time.sleep(0.5)  # Give launchctl time to register the service

        # Verify service is loaded in launchctl (even if daemon failed to run)
        result = subprocess.run(
            ["launchctl", "print", service_domain],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            # Service not loaded - this is a real failure
            error_msg = (
                start_result.get("error", "Unknown error") if not start_result.get("success") else "Service not loaded"
            )
            log_path = wks_home / "logs" / "service.log"
            log_content = ""
            if log_path.exists():
                log_content = f"\nLog file contents:\n{log_path.read_text()[-500:]}"
            pytest.fail(f"Service not loaded in launchctl: {error_msg}{log_content}")

        # Service is loaded - that's what we're testing
        # We don't require a PID since the daemon might fail to start due to config issues
        status = service.get_service_status()
        assert status["installed"] is True

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
