"""Unit test fixtures.

Most configuration helpers are in tests/conftest.py.
This file contains unit-test-specific helpers for mocking/patching.
"""

import pytest

# Re-export commonly used helpers from root conftest
from tests.conftest import (
    minimal_config_dict,
    minimal_wks_config,
    run_cmd,
)
from wks.api.config.WKSConfig import WKSConfig

__all__ = [
    "TrackedConfig",
    "create_patched_config",
    "minimal_config_dict",
    "minimal_wks_config",
    "patch_wks_config",
    "run_cmd",
    "standard_config_dict",
]


@pytest.fixture
def standard_config_dict(minimal_config_dict: dict) -> dict:
    """Backward compatibility alias for minimal_config_dict."""
    return minimal_config_dict


class TrackedConfig:
    """Wrapper around WKSConfig that tracks save() calls.

    Use this when you need to verify that a command calls save().
    Delegates attribute access to the underlying config.
    """

    def __init__(self, config: WKSConfig):
        object.__setattr__(self, "_config", config)
        object.__setattr__(self, "save_calls", 0)
        object.__setattr__(self, "errors", [])
        object.__setattr__(self, "warnings", [])

    def __getattr__(self, name: str):
        return getattr(self._config, name)

    def __setattr__(self, name: str, value):
        if name in ("_config", "save_calls", "errors", "warnings"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._config, name, value)

    def save(self) -> None:
        self.save_calls += 1


def create_patched_config(monkeypatch, monitor_config_data: dict | None = None) -> TrackedConfig:
    """Patch WKSConfig.load to return a TrackedConfig instance.

    Args:
        monkeypatch: pytest monkeypatch fixture
        monitor_config_data: Optional dictionary to update monitor config with.
            Can include 'filter' dict to update filter settings.

    Returns:
        TrackedConfig instance that tracks save() calls.
    """
    base_config = minimal_config_dict()

    if monitor_config_data:
        # Deep merge monitor config data
        if "filter" in monitor_config_data:
            base_config["monitor"]["filter"].update(monitor_config_data["filter"])
        for key, value in monitor_config_data.items():
            if key != "filter":
                base_config["monitor"][key] = value

    config = WKSConfig(**base_config)
    tracked = TrackedConfig(config)
    monkeypatch.setattr(WKSConfig, "load", lambda: tracked)
    return tracked


@pytest.fixture
def patch_wks_config(monkeypatch) -> TrackedConfig:
    """Fixture that patches WKSConfig with default settings."""
    return create_patched_config(monkeypatch)
