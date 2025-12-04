"""Tests for wks/monitor/config.py - MonitorConfig dataclass."""

import pytest

from wks.monitor.config import MonitorConfig, ValidationError


@pytest.mark.unit
class TestMonitorConfig:
    """Tests for MonitorConfig dataclass and validation."""

    @pytest.fixture
    def valid_monitor_dict(self):
        """Minimal valid monitor config dict."""
        return {
            "include_paths": ["~"],
            "exclude_paths": [],
            "include_dirnames": [],
            "exclude_dirnames": [],
            "include_globs": [],
            "exclude_globs": [],
            "managed_directories": {"~": 100},
            "database": "wks.monitor",
        }

    def test_valid_config(self, valid_monitor_dict):
        cfg = MonitorConfig(**valid_monitor_dict)
        assert cfg.database == "wks.monitor"
        assert cfg.include_paths == ["~"]

    def test_from_config_dict_valid(self, valid_monitor_dict):
        cfg = MonitorConfig.from_config_dict({"monitor": valid_monitor_dict})
        assert cfg.database == "wks.monitor"

    def test_from_config_dict_missing_section(self):
        with pytest.raises(KeyError) as exc:
            MonitorConfig.from_config_dict({})
        assert "monitor section is required" in str(exc.value)

    def test_from_config_dict_unsupported_key(self, valid_monitor_dict):
        valid_monitor_dict["unsupported_key"] = "value"
        # Pydantic allows extra fields by default, so this won't raise
        # If we want to reject extra fields, we'd need to set model_config
        cfg = MonitorConfig.from_config_dict({"monitor": valid_monitor_dict})
        assert cfg.database == "wks.monitor"

    # List field validation
    def test_invalid_include_paths_type(self, valid_monitor_dict):
        valid_monitor_dict["include_paths"] = "not a list"
        with pytest.raises(ValidationError) as exc:
            MonitorConfig(**valid_monitor_dict)
        assert "include_paths" in str(exc.value)
        assert "Input should be a valid list" in str(exc.value)

    def test_invalid_exclude_paths_type(self, valid_monitor_dict):
        valid_monitor_dict["exclude_paths"] = "not a list"
        with pytest.raises(ValidationError) as exc:
            MonitorConfig(**valid_monitor_dict)
        assert "exclude_paths" in str(exc.value)
        assert "Input should be a valid list" in str(exc.value)

    def test_invalid_include_dirnames_type(self, valid_monitor_dict):
        valid_monitor_dict["include_dirnames"] = "not a list"
        with pytest.raises(ValidationError) as exc:
            MonitorConfig(**valid_monitor_dict)
        assert "include_dirnames" in str(exc.value)
        assert "Input should be a valid list" in str(exc.value)

    def test_invalid_exclude_dirnames_type(self, valid_monitor_dict):
        valid_monitor_dict["exclude_dirnames"] = "not a list"
        with pytest.raises(ValidationError) as exc:
            MonitorConfig(**valid_monitor_dict)
        assert "exclude_dirnames" in str(exc.value)
        assert "Input should be a valid list" in str(exc.value)

    def test_invalid_include_globs_type(self, valid_monitor_dict):
        valid_monitor_dict["include_globs"] = "not a list"
        with pytest.raises(ValidationError) as exc:
            MonitorConfig(**valid_monitor_dict)
        assert "include_globs" in str(exc.value)
        assert "Input should be a valid list" in str(exc.value)

    def test_invalid_exclude_globs_type(self, valid_monitor_dict):
        valid_monitor_dict["exclude_globs"] = "not a list"
        with pytest.raises(ValidationError) as exc:
            MonitorConfig(**valid_monitor_dict)
        assert "exclude_globs" in str(exc.value)
        assert "Input should be a valid list" in str(exc.value)

    def test_invalid_managed_directories_type(self, valid_monitor_dict):
        valid_monitor_dict["managed_directories"] = "not a dict"
        with pytest.raises(ValidationError) as exc:
            MonitorConfig(**valid_monitor_dict)
        assert "managed_directories" in str(exc.value)
        assert "Input should be a valid dictionary" in str(exc.value)

    # Database format validation
    def test_invalid_database_no_dot(self, valid_monitor_dict):
        valid_monitor_dict["database"] = "nodot"
        with pytest.raises(ValidationError) as exc:
            MonitorConfig(**valid_monitor_dict)
        assert "must be in format 'database.collection'" in str(exc.value)

    def test_invalid_database_empty_parts(self, valid_monitor_dict):
        valid_monitor_dict["database"] = ".collection"
        with pytest.raises(ValidationError) as exc:
            MonitorConfig(**valid_monitor_dict)
        assert "must be in format 'database.collection'" in str(exc.value)

    def test_invalid_database_not_string(self, valid_monitor_dict):
        valid_monitor_dict["database"] = 123
        with pytest.raises(ValidationError) as exc:
            MonitorConfig(**valid_monitor_dict)
        assert "database" in str(exc.value)
        assert "Input should be a valid string" in str(exc.value)

    # Numeric field validation
    def test_invalid_touch_weight_too_low(self, valid_monitor_dict):
        valid_monitor_dict["touch_weight"] = 0.0001
        with pytest.raises(ValidationError) as exc:
            MonitorConfig(**valid_monitor_dict)
        assert "touch_weight" in str(exc.value)
        assert "greater than or equal to 0.001" in str(exc.value)

    def test_invalid_touch_weight_too_high(self, valid_monitor_dict):
        valid_monitor_dict["touch_weight"] = 1.5
        with pytest.raises(ValidationError) as exc:
            MonitorConfig(**valid_monitor_dict)
        assert "touch_weight" in str(exc.value)
        assert "less than or equal to 1" in str(exc.value)

    def test_invalid_touch_weight_not_number(self, valid_monitor_dict):
        valid_monitor_dict["touch_weight"] = "high"
        with pytest.raises(ValidationError) as exc:
            MonitorConfig(**valid_monitor_dict)
        assert "touch_weight" in str(exc.value)
        assert "Input should be a valid number" in str(exc.value)

    def test_invalid_max_documents_negative(self, valid_monitor_dict):
        valid_monitor_dict["max_documents"] = -1
        with pytest.raises(ValidationError) as exc:
            MonitorConfig(**valid_monitor_dict)
        assert "max_documents" in str(exc.value)
        assert "greater than or equal to 0" in str(exc.value)

    def test_invalid_max_documents_not_int(self, valid_monitor_dict):
        valid_monitor_dict["max_documents"] = "many"
        with pytest.raises(ValidationError) as exc:
            MonitorConfig(**valid_monitor_dict)
        assert "max_documents" in str(exc.value)
        assert "Input should be a valid integer" in str(exc.value)

    def test_invalid_prune_interval_zero(self, valid_monitor_dict):
        valid_monitor_dict["prune_interval_secs"] = 0
        with pytest.raises(ValidationError) as exc:
            MonitorConfig(**valid_monitor_dict)
        assert "prune_interval_secs" in str(exc.value)
        assert "greater than 0" in str(exc.value)

    def test_invalid_prune_interval_not_number(self, valid_monitor_dict):
        valid_monitor_dict["prune_interval_secs"] = "fast"
        with pytest.raises(ValidationError) as exc:
            MonitorConfig(**valid_monitor_dict)
        assert "prune_interval_secs" in str(exc.value)
        assert "Input should be a valid number" in str(exc.value)

    # Multiple errors collected
    def test_multiple_errors_collected(self, valid_monitor_dict):
        valid_monitor_dict["include_paths"] = "not list"
        valid_monitor_dict["database"] = "nodot"
        valid_monitor_dict["touch_weight"] = 99
        with pytest.raises(ValidationError) as exc:
            MonitorConfig(**valid_monitor_dict)
        # Should contain all three errors
        assert "include_paths" in str(exc.value)
        assert "database" in str(exc.value)
        assert "touch_weight" in str(exc.value)

    # Defaults
    def test_defaults(self, valid_monitor_dict):
        cfg = MonitorConfig(**valid_monitor_dict)
        assert cfg.touch_weight == 0.1
        assert cfg.max_documents == 1000000
        assert cfg.prune_interval_secs == 300.0
        assert cfg.priority == {}


@pytest.mark.unit
class TestValidationError:
    """Tests for Pydantic ValidationError exception."""

    def test_validation_error_has_errors(self):
        """Pydantic ValidationError contains error details."""
        with pytest.raises(ValidationError) as exc_info:
            MonitorConfig(
                database="invalid",
                touch_weight=0.1,
                max_documents=1000000,
                prune_interval_secs=300.0,
            )  # Missing required list fields
        # Pydantic ValidationError has errors() method
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert isinstance(errors, list)

    def test_validation_error_message_format(self):
        """Pydantic ValidationError has descriptive message."""
        with pytest.raises(ValidationError) as exc_info:
            MonitorConfig(
                database="invalid",
                include_paths=["~"],  # Valid list
                touch_weight=0.1,
                max_documents=1000000,
                prune_interval_secs=300.0,
            )
        error_str = str(exc_info.value)
        assert "validation error" in error_str.lower()
        assert "MonitorConfig" in error_str
