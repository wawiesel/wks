import pytest

from tests.conftest import (
    TrackedConfig,
    build_service_test_config,
    create_tracked_wks_config,
    ensure_watch_dir,
    minimal_config_dict,
    minimal_wks_config,
    run_cmd,
    tracked_wks_config,
    write_watched_file,
)

__all__ = [
    "TrackedConfig",
    "build_service_test_config",
    "create_tracked_wks_config",
    "ensure_watch_dir",
    "minimal_config_dict",
    "minimal_wks_config",
    "run_cmd",
    "tracked_wks_config",
    "write_watched_file",
]


@pytest.fixture(autouse=True)
def reset_mongomock():
    import wks.api.database._mongomock._client as mock_client

    mock_client._shared_mongomock_client = None
