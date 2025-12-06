"""Unit tests for wks.api.config.ConfigError module."""

import pytest

from wks.api.config.ConfigError import ConfigError

pytestmark = pytest.mark.config


class TestConfigError:
    """Test ConfigError exception."""

    def test_config_error_is_exception(self):
        """Test ConfigError is an Exception."""
        assert issubclass(ConfigError, Exception)

    def test_config_error_can_be_raised(self):
        """Test ConfigError can be raised."""
        with pytest.raises(ConfigError):
            raise ConfigError("Test error")

    def test_config_error_message(self):
        """Test ConfigError preserves message."""
        with pytest.raises(ConfigError) as exc_info:
            raise ConfigError("Test error message")
        assert str(exc_info.value) == "Test error message"
