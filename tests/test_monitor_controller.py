"""
Unit tests for MonitorController.

Tests the core business logic for monitor operations without
requiring CLI or display infrastructure.
"""

import unittest
from pathlib import Path
from wks.monitor_controller import MonitorController


class TestMonitorController(unittest.TestCase):
    """Test MonitorController methods."""

    def test_get_status_basic(self):
        """Test get_status with minimal config."""
        config = {
            "monitor": {
                "include_paths": ["~"],
                "exclude_paths": [],
                "managed_directories": {"~/Documents": 100},
                "ignore_dirnames": ["node_modules"],
                "ignore_globs": ["*.tmp"]
            },
            "mongo": {"uri": "mongodb://localhost:27017/"}
        }

        result = MonitorController.get_status(config)

        self.assertIn("tracked_files", result)
        self.assertIn("managed_directories", result)
        self.assertIn("include_paths", result)
        self.assertIn("exclude_paths", result)
        self.assertIn("issues", result)
        self.assertIn("redundancies", result)
        self.assertIsInstance(result["issues"], list)
        self.assertIsInstance(result["redundancies"], list)

    def test_get_status_detects_vault_redundancy(self):
        """Test that vault_path in exclude_paths triggers redundancy warning."""
        config = {
            "vault_path": "~/obsidian",
            "monitor": {
                "include_paths": ["~"],
                "exclude_paths": ["~/obsidian"],  # Redundant - vault auto-excluded
                "managed_directories": {},
                "ignore_dirnames": [],
                "ignore_globs": []
            }
        }

        result = MonitorController.get_status(config)

        # Should detect redundancy
        self.assertTrue(any("vault_path is automatically ignored" in r for r in result["redundancies"]))

    def test_get_status_detects_wks_home_redundancy(self):
        """Test that ~/.wks in exclude_paths triggers redundancy warning."""
        config = {
            "monitor": {
                "include_paths": ["~"],
                "exclude_paths": ["~/.wks"],  # Redundant - WKS home auto-excluded
                "managed_directories": {},
                "ignore_dirnames": [],
                "ignore_globs": []
            }
        }

        result = MonitorController.get_status(config)

        # Should detect redundancy
        self.assertTrue(any("WKS home is automatically ignored" in r for r in result["redundancies"]))

    def test_validate_config_no_issues(self):
        """Test validate_config with clean configuration."""
        config = {
            "monitor": {
                "include_paths": ["~"],
                "exclude_paths": ["~/Downloads"],
                "managed_directories": {"~/Documents": 100}
            }
        }

        result = MonitorController.validate_config(config)

        self.assertFalse(result["has_issues"])
        self.assertFalse(result["has_warnings"])
        self.assertEqual(len(result["issues"]), 0)
        self.assertEqual(len(result["warnings"]), 0)

    def test_validate_config_detects_conflicts(self):
        """Test that paths in both include and exclude are detected."""
        config = {
            "monitor": {
                "include_paths": ["~/Documents"],
                "exclude_paths": ["~/Documents"],  # Conflict!
                "managed_directories": {}
            }
        }

        result = MonitorController.validate_config(config)

        self.assertTrue(result["has_issues"])
        self.assertEqual(len(result["issues"]), 1)
        self.assertIn("both include and exclude", result["issues"][0])

    def test_check_path_included(self):
        """Test check_path for an included path."""
        config = {
            "monitor": {
                "include_paths": ["~/Documents"],
                "exclude_paths": [],
                "managed_directories": {"~/Documents": 100},
                "ignore_dirnames": [],
                "ignore_globs": [],
                "priority": {
                    "depth_multiplier": 0.9,
                    "underscore_divisor": 2,
                    "single_underscore_divisor": 64,
                    "extension_weights": {"default": 1.0}
                }
            }
        }

        result = MonitorController.check_path(config, "~/Documents/test.txt")

        self.assertTrue(result["is_monitored"])
        self.assertIsNotNone(result["priority"])
        self.assertGreater(len(result["decisions"]), 0)

    def test_check_path_excluded(self):
        """Test check_path for an excluded path."""
        config = {
            "monitor": {
                "include_paths": ["~"],
                "exclude_paths": ["~/Library"],
                "managed_directories": {"~": 100},
                "ignore_dirnames": [],
                "ignore_globs": [],
                "priority": {}
            }
        }

        result = MonitorController.check_path(config, "~/Library/test.txt")

        self.assertFalse(result["is_monitored"])
        self.assertIn("exclude_paths", result["reason"])
        self.assertIsNone(result["priority"])

    def test_check_path_ignored_dirname(self):
        """Test check_path for path with ignored dirname."""
        config = {
            "monitor": {
                "include_paths": ["~"],
                "exclude_paths": [],
                "managed_directories": {"~": 100},
                "ignore_dirnames": ["node_modules"],
                "ignore_globs": [],
                "priority": {}
            }
        }

        result = MonitorController.check_path(config, "~/project/node_modules/test.js")

        self.assertFalse(result["is_monitored"])
        self.assertIn("ignored dirname", result["reason"])

    def test_check_path_ignored_glob(self):
        """Test check_path for path matching ignore_globs."""
        config = {
            "monitor": {
                "include_paths": ["~"],
                "exclude_paths": [],
                "managed_directories": {"~": 100},
                "ignore_dirnames": [],
                "ignore_globs": ["*.tmp"],
                "priority": {}
            }
        }

        result = MonitorController.check_path(config, "~/test.tmp")

        self.assertFalse(result["is_monitored"])
        self.assertIn("ignore_globs", result["reason"])


if __name__ == "__main__":
    unittest.main()
