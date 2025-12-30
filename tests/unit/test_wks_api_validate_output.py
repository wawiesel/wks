"""Unit tests for wks.api.validate_output."""

import pytest
from pydantic import BaseModel

from wks.api.validate_output import validate_output


class MockOutput(BaseModel):
    key: str
    optional: str = "default"


def mock_cmd_func():
    """Mock command function."""
    pass


# Monkeypunch module to resemble wks.api.domain
mock_cmd_func.__module__ = "wks.api.test_domain"
mock_cmd_func.__name__ = "cmd_mock_command"


def test_validate_output_success(monkeypatch):
    """Test successful validation."""
    from wks.api.schema_registry import schema_registry

    # Register mock schema
    monkeypatch.setattr(schema_registry, "get_output_schema", lambda d, c: MockOutput)

    output = {"key": "value"}
    validated = validate_output(mock_cmd_func, output)

    assert validated == {"key": "value", "optional": "default"}


def test_validate_output_failure(monkeypatch):
    """Test validation failure."""
    from wks.api.schema_registry import schema_registry

    # Register mock schema
    monkeypatch.setattr(schema_registry, "get_output_schema", lambda d, c: MockOutput)

    # Missing required 'key'
    output = {"wrong": "value"}

    with pytest.raises(ValueError, match="Output validation failed"):
        validate_output(mock_cmd_func, output)


def test_validate_output_skip_non_api():
    """Test skipping validation for non-API modules."""

    def non_api_func():
        pass

    non_api_func.__module__ = "other.module"
    output = {"foo": "bar"}
    assert validate_output(non_api_func, output) == output


def test_validate_output_skip_non_cmd():
    """Test skipping validation for non-cmd functions."""

    def mock_helper():
        pass

    mock_helper.__module__ = "wks.api.test_domain"
    output = {"foo": "bar"}
    assert validate_output(mock_helper, output) == output


def test_validate_output_no_schema(monkeypatch):
    """Test validation when no schema is registered."""
    from wks.api.schema_registry import schema_registry

    monkeypatch.setattr(schema_registry, "get_output_schema", lambda d, c: None)

    output = {"key": "value"}
    # Should simply return input
    assert validate_output(mock_cmd_func, output) == output


def test_normalize_output_logic():
    """Test the internal normalize_output logic."""
    from wks.api._normalize_output import normalize_output

    output = {"error": "Something went wrong", "data": "value"}
    result = normalize_output(output)
    assert result["errors"] == ["Something went wrong"]
    assert "error" not in result

    output_with_errors = {"errors": ["e1"]}
    result2 = normalize_output(output_with_errors)
    assert result2["errors"] == ["e1"]
