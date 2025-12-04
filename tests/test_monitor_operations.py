from pathlib import Path

import pytest

from wks.monitor.config import MonitorConfig
from wks.monitor.operations import MonitorOperations, _canonicalize_path, _find_matching_path_key


class TestMonitorOperations:
    @pytest.fixture
    def monitor_config(self) -> MonitorConfig:
        return MonitorConfig(
            include_paths=[],
            exclude_paths=[],
            include_dirnames=[],
            exclude_dirnames=[],
            include_globs=[],
            exclude_globs=[],
            database="test.monitor",
            managed_directories={},
        )

    def test_canonicalize_path(self, tmp_path):
        p = tmp_path / "test"
        assert _canonicalize_path(str(p)) == str(p.resolve(strict=False))

        # Test tilde expansion
        assert _canonicalize_path("~") == str(Path.home())

    def test_find_matching_path_key(self, tmp_path):
        p = tmp_path / "test"
        path_map = {str(p): 1}

        assert _find_matching_path_key(path_map, str(p)) == str(p)
        assert _find_matching_path_key(path_map, str(p) + "/../test") == str(p)
        assert _find_matching_path_key(path_map, "/nonexistent") is None

    def test_add_to_list_path(self, monitor_config: MonitorConfig, tmp_path):
        p = tmp_path / "test"
        result = MonitorOperations.add_to_list(monitor_config, "include_paths", str(p))

        assert result.success
        assert str(p.resolve(strict=False)) in monitor_config.include_paths

        # Add duplicate
        result = MonitorOperations.add_to_list(monitor_config, "include_paths", str(p))
        assert not result.success
        assert result.already_exists

    def test_add_to_list_dirname(self, monitor_config: MonitorConfig):
        result = MonitorOperations.add_to_list(monitor_config, "include_dirnames", "node_modules")
        assert result.success
        assert "node_modules" in monitor_config.include_dirnames

        # Invalid dirname
        result = MonitorOperations.add_to_list(monitor_config, "include_dirnames", "invalid/name")
        assert not result.success
        assert result.validation_failed

    def test_add_to_list_glob(self, monitor_config: MonitorConfig):
        result = MonitorOperations.add_to_list(monitor_config, "include_globs", "*.py")
        assert result.success
        assert "*.py" in monitor_config.include_globs

    def test_remove_from_list(self, monitor_config: MonitorConfig, tmp_path):
        p = tmp_path / "test"
        p_str = str(p.resolve(strict=False))
        monitor_config.include_paths.append(p_str)

        result = MonitorOperations.remove_from_list(monitor_config, "include_paths", str(p))
        assert result.success
        assert p_str not in monitor_config.include_paths

        # Remove non-existent
        result = MonitorOperations.remove_from_list(monitor_config, "include_paths", str(p))
        assert not result.success
        assert result.not_found

    def test_add_managed_directory(self, monitor_config: MonitorConfig, tmp_path):
        p = tmp_path / "managed"
        result = MonitorOperations.add_managed_directory(monitor_config, str(p), 100)

        assert result["success"]
        assert str(p.resolve(strict=False)) in monitor_config.managed_directories
        assert monitor_config.managed_directories[str(p.resolve(strict=False))] == 100

        # Add duplicate
        result = MonitorOperations.add_managed_directory(monitor_config, str(p), 200)
        assert not result["success"]
        assert result["already_exists"]

    def test_remove_managed_directory(self, monitor_config: MonitorConfig, tmp_path):
        p = tmp_path / "managed"
        p_str = str(p.resolve(strict=False))
        monitor_config.managed_directories[p_str] = 100

        result = MonitorOperations.remove_managed_directory(monitor_config, str(p))
        assert result["success"]
        assert p_str not in monitor_config.managed_directories

        # Remove non-existent
        result = MonitorOperations.remove_managed_directory(monitor_config, str(p))
        assert not result["success"]
        assert result["not_found"]

    def test_set_managed_priority(self, monitor_config: MonitorConfig, tmp_path):
        p = tmp_path / "managed"
        p_str = str(p.resolve(strict=False))
        monitor_config.managed_directories[p_str] = 100

        result = MonitorOperations.set_managed_priority(monitor_config, str(p), 200)
        assert result["success"]
        assert monitor_config.managed_directories[p_str] == 200

        # Set non-existent
        result = MonitorOperations.set_managed_priority(monitor_config, "/nonexistent", 200)
        assert not result["success"]
        assert result["not_found"]
