"""Unit test fixtures.

Most configuration helpers are in tests/conftest.py.
This file contains unit-test-specific helpers for mocking/patching.
"""

import pytest

# Re-export commonly used helpers from root conftest to maintain compatibility
# Re-export the moved TrackedConfig helpers from root conftest to maintain compatibility
from tests.conftest import (
    TrackedConfig,
    create_tracked_wks_config,
    minimal_config_dict,
    minimal_wks_config,
    run_cmd,
    tracked_wks_config,
)

__all__ = [
    "TrackedConfig",
    "create_tracked_wks_config",
    "minimal_config_dict",
    "minimal_wks_config",
    "run_cmd",
    "tracked_wks_config",
]


@pytest.fixture(autouse=True)
def reset_mongomock():
    """Reset shared mongomock client before each test."""
    import wks.api.database._mongomock._client as mock_client

    mock_client._shared_mongomock_client = None
