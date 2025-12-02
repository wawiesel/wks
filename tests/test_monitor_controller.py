"""
Unit tests for MonitorController.

Tests the core business logic for monitor operations without
requiring CLI or display infrastructure.
"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from wks.monitor import MonitorController


def build_config(**monitor_overrides):
    """Return a fully-populated monitor config dict with overrides."""
    monitor = {
        "include_paths": ["~"],
        "exclude_paths": [],
        "include_dirnames": [],
        "exclude_dirnames": [],
        "include_globs": [],
        "exclude_globs": [],
        "managed_directories": {},
        "database": "wks.monitor",
        "touch_weight": 0.1,
        "priority": {
            "depth_multiplier": 0.9,
            "underscore_divisor": 2,
            "single_underscore_divisor": 64,
            "extension_weights": {"default": 1.0},
        },
        "max_documents": 100000,
        "prune_interval_secs": 300.0,
    }
    monitor.update(monitor_overrides)
    return {
        "monitor": monitor,
        "db": {"uri": "mongodb://localhost:27017/"},
    }


class TestMonitorController(unittest.TestCase):
    """Test MonitorController methods."""

    def test_get_status_basic(self):
        """Test get_status with minimal config."""
        config = build_config(
            managed_directories={"~/Documents": 100},
            exclude_dirnames=["node_modules"],
            exclude_globs=["*.tmp"],
        )

        result = MonitorController.get_status(config)

        self.assertIsNotNone(result.tracked_files)
        self.assertIsNotNone(result.managed_directories)
        self.assertIsNotNone(result.include_paths)
        self.assertIsNotNone(result.exclude_paths)
        self.assertIsInstance(result.issues, list)
        self.assertIsInstance(result.redundancies, list)
        self.assertIsInstance(result.exclude_dirnames, list)

    def test_get_status_detects_vault_redundancy(self):
        """Test that vault.base_dir in exclude_paths triggers redundancy warning."""
        config = build_config(exclude_paths=["/vault"])
        config["vault"] = {"base_dir": "/vault"}

        result = MonitorController.get_status(config)

        # Should detect redundancy
        self.assertTrue(any("vault.base_dir is managed separately" in r for r in result.redundancies))

    def test_get_status_detects_wks_home_redundancy(self):
        """Test that ~/.wks in exclude_paths triggers redundancy warning."""
        config = build_config(exclude_paths=["~/.wks"])

        result = MonitorController.get_status(config)

        # Should detect redundancy
        self.assertTrue(any("WKS home is automatically ignored" in r for r in result.redundancies))

    def test_validate_config_no_issues(self):
        """Test validate_config with clean configuration."""
        config = build_config(
            exclude_paths=["~/Downloads"],
            managed_directories={"~/Documents": 100},
        )

        result = MonitorController.validate_config(config)

        self.assertEqual(len(result.issues), 0)
        self.assertEqual(len(result.redundancies), 0)

    def test_validate_config_detects_conflicts(self):
        """Test that paths in both include and exclude are detected."""
        config = build_config(
            include_paths=["~/Documents"],
            exclude_paths=["~/Documents"],
        )

        result = MonitorController.validate_config(config)

        self.assertGreater(len(result.issues), 0)
        self.assertTrue(any("both include_paths and exclude_paths" in issue for issue in result.issues))

    def test_check_path_included(self):
        """Test check_path for an included path."""
        config = build_config(
            include_paths=["~/Documents"],
            managed_directories={"~/Documents": 100},
        )

        result = MonitorController.check_path(config, "~/Documents/test.txt")

        self.assertTrue(result["is_monitored"])
        self.assertIsNotNone(result["priority"])
        self.assertGreater(len(result["decisions"]), 0)

    def test_check_path_excluded(self):
        """Test check_path for an excluded path."""
        config = build_config(
            include_paths=["~"],
            exclude_paths=["~/Library"],
            managed_directories={"~": 100},
        )

        result = MonitorController.check_path(config, "~/Library/test.txt")

        self.assertFalse(result["is_monitored"])
        self.assertIn("Excluded", result["reason"])
        self.assertIsNone(result["priority"])

    def test_check_path_excluded_dirname(self):
        """Test check_path for path with excluded dirname."""
        config = build_config(
            managed_directories={"~": 100},
            exclude_dirnames=["node_modules"],
        )

        result = MonitorController.check_path(config, "~/project/node_modules/test.js")

        self.assertFalse(result["is_monitored"])
        self.assertIn("excluded", result["reason"].lower())

    def test_check_path_excluded_glob(self):
        """Test check_path for path matching exclude_globs."""
        config = build_config(
            managed_directories={"~": 100},
            exclude_globs=["*.tmp"],
        )

        result = MonitorController.check_path(config, "~/test.tmp")

        self.assertFalse(result["is_monitored"])
        self.assertIn("glob", result["reason"].lower())

    @patch("wks.monitor.controller.MonitorRules.from_config")
    @patch("wks.uri_utils.uri_to_path")
    @patch("pymongo.MongoClient")
    def test_prune_ignored_files_deletes_matching_docs(self, mock_client, mock_uri_to_path, mock_rules):
        """Ensure prune_ignored_files removes entries matched by ignore rules."""
        config = build_config(
            include_paths=["~/Documents"],
            managed_directories={"~/Documents": 100},
        )
        mock_client_instance = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.find.return_value = [{"_id": 1, "path": "file://ignored"}]
        mock_db.__getitem__.return_value = mock_collection
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.server_info.return_value = {}
        mock_client.return_value = mock_client_instance

        fake_rules = MagicMock()
        fake_rules.allows.return_value = False
        mock_rules.return_value = fake_rules
        mock_uri_to_path.return_value = Path("/tmp/ignored.txt")

        result = MonitorController.prune_ignored_files(config)

        self.assertTrue(result["success"])
        self.assertEqual(result["pruned_count"], 1)
        mock_collection.delete_one.assert_called_once()

    @patch("wks.uri_utils.uri_to_path")
    @patch("pymongo.MongoClient")
    def test_prune_deleted_files_deletes_missing_docs(self, mock_client, mock_uri_to_path):
        """Ensure prune_deleted_files removes documents pointing to missing files."""
        config = build_config(
            include_paths=["~/Documents"],
            managed_directories={"~/Documents": 100},
        )
        mock_client_instance = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.find.return_value = [{"_id": 1, "path": "file://missing"}]
        mock_db.__getitem__.return_value = mock_collection
        mock_client_instance.__getitem__.return_value = mock_db
        mock_client_instance.server_info.return_value = {}
        mock_client.return_value = mock_client_instance

        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_uri_to_path.return_value = mock_path

        result = MonitorController.prune_deleted_files(config)

        self.assertTrue(result["success"])
        self.assertEqual(result["pruned_count"], 1)
        mock_collection.delete_one.assert_called_once()

    def test_get_list_include_paths(self):
        """Test get_list for include_paths."""
        config = build_config(include_paths=["~/Documents", "~/Projects"])
        
        result = MonitorController.get_list(config, "include_paths")
        
        self.assertEqual(result["list_name"], "include_paths")
        self.assertEqual(result["count"], 2)
        self.assertEqual(set(result["items"]), {"~/Documents", "~/Projects"})

    def test_get_list_unknown_list_name(self):
        """Test get_list raises ValueError for unknown list_name."""
        config = build_config()
        
        with self.assertRaises(ValueError) as cm:
            MonitorController.get_list(config, "unknown_list")
        
        self.assertIn("Unknown list_name", str(cm.exception))

    def test_get_list_with_dirname_validation(self):
        """Test get_list includes validation for dirname lists."""
        config = build_config(
            include_dirnames=["node_modules", "invalid/.dirname"],
            include_globs=["**/node_modules/**"]
        )
        
        result = MonitorController.get_list(config, "include_dirnames")
        
        self.assertEqual(result["list_name"], "include_dirnames")
        self.assertIn("validation", result)
        self.assertIsInstance(result["validation"], dict)

    def test_get_list_with_glob_validation(self):
        """Test get_list includes validation for glob lists."""
        config = build_config(exclude_globs=["*.tmp", "[invalid"])
        
        result = MonitorController.get_list(config, "exclude_globs")
        
        self.assertEqual(result["list_name"], "exclude_globs")
        self.assertIn("validation", result)
        self.assertIsInstance(result["validation"], dict)

    def test_get_managed_directories(self):
        """Test get_managed_directories returns managed directories with validation."""
        config = build_config(
            managed_directories={"~/Documents": 100, "~/Projects": 200}
        )
        
        result = MonitorController.get_managed_directories(config)
        
        self.assertEqual(result.count, 2)
        self.assertIn("~/Documents", result.managed_directories)
        self.assertIn("~/Projects", result.managed_directories)
        self.assertIn("~/Documents", result.validation)
        self.assertIn("~/Projects", result.validation)

    def test_get_managed_directories_empty(self):
        """Test get_managed_directories with no managed directories."""
        config = build_config(managed_directories={})
        
        result = MonitorController.get_managed_directories(config)
        
        self.assertEqual(result.count, 0)
        self.assertEqual(len(result.managed_directories), 0)



if __name__ == "__main__":
    unittest.main()
