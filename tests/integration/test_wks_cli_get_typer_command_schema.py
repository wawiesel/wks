"""Integration tests for wks.cli.get_typer_command_schema module."""

import typer

from wks.cli.get_typer_command_schema import get_typer_command_schema


def test_get_typer_command_schema_returns_schema():
    """Test that get_typer_command_schema returns a schema dict."""
    app = typer.Typer()

    def sample(path: str, optional: int = 3):  # type: ignore[unused-argument]
        return path, optional

    app.command(name="sample")(sample)

    schema = get_typer_command_schema(app, "sample")
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "required" in schema


def test_get_typer_command_schema_raises_on_missing_command():
    """Test that get_typer_command_schema raises on missing command."""
    app = typer.Typer()

    try:
        get_typer_command_schema(app, "nonexistent")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "nonexistent" in str(e)
