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
                    "filter": {},
                    "priority": {},
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
                    "filter": {},
                    "priority": "not a dict",
                    "sync": {"database": "wks.monitor"},
                }
            }
        )
    assert isinstance(exc.value, ValidationError)
