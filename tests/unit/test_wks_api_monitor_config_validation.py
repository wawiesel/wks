"""Unit tests for MonitorConfig validation error handling."""

import pytest
from pydantic import ValidationError

from wks.api.monitor.MonitorConfig import MonitorConfig

pytestmark = pytest.mark.monitor


def test_monitor_config_validation_error_re_raise():
    """Test that MonitorConfig.from_config_dict re-raises ValidationError."""
    # Create config that will cause ValidationError (missing required sync.database)
    with pytest.raises(ValidationError) as exc:
        MonitorConfig.from_config_dict(
            {
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
                    # Missing sync section
                }
            }
        )
    # Should raise ValidationError (not KeyError)
    assert isinstance(exc.value, ValidationError)


def test_monitor_config_invalid_priority_type():
    """Test MonitorConfig validation with invalid priority type."""
    with pytest.raises(ValidationError) as exc:
        MonitorConfig.from_config_dict(
            {
                "monitor": {
                    "filter": {
                    "include_paths": [],
                    "exclude_paths": [],
                    "include_dirnames": [],
                    "exclude_dirnames": [],
                    "include_globs": [],
                    "exclude_globs": [],
                },
                    "priority": "not a dict",
                    "database": "monitor",
                "sync": {
                    "max_documents": 1000000,
                    "min_priority": 0.0,
                    "prune_interval_secs": 300.0,
                },
                }
            }
        )
    assert isinstance(exc.value, ValidationError)
