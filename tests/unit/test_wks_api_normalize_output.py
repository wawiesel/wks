"""Unit tests for wks.api._normalize_output."""

from wks.api._normalize_output import normalize_output


def test_normalize_output_converts_error_to_errors():
    """Test converting error string to errors list."""
    output = {"error": "Something went wrong", "data": "value"}

    result = normalize_output(output)

    assert "error" not in result
    assert result["errors"] == ["Something went wrong"]
    assert result["warnings"] == []
    assert result["data"] == "value"


def test_normalize_output_handles_empty_error():
    """Test handling empty error string."""
    output = {"error": ""}

    result = normalize_output(output)

    assert result["errors"] == []
    assert result["warnings"] == []


def test_normalize_output_keeps_existing_errors():
    """Test that existing errors list is preserved."""
    output = {"errors": ["error1", "error2"]}

    result = normalize_output(output)

    assert result["errors"] == ["error1", "error2"]


def test_normalize_output_adds_missing_errors():
    """Test adding errors list when missing."""
    output = {"data": "value"}

    result = normalize_output(output)

    assert result["errors"] == []
    assert result["warnings"] == []


def test_normalize_output_adds_missing_warnings():
    """Test adding warnings list when missing."""
    output: dict[str, list[str]] = {"errors": []}

    result = normalize_output(output)

    assert result["warnings"] == []
