"""Shared pytest configuration and fixtures."""

import pytest


def pytest_collection_modifyitems(config, items):
    """Automatically apply markers based on test file location."""
    for item in items:
        path_str = str(item.fspath)
        if "/smoke/" in path_str:
            item.add_marker(pytest.mark.smoke)
        elif "/unit/" in path_str:
            item.add_marker(pytest.mark.unit)
        elif "/integration/" in path_str:
            item.add_marker(pytest.mark.integration)
