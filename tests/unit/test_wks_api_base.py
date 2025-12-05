"""Unit tests for wks.api.base module."""

import typer

from wks.api import base as api_base


def test_stage_result_success_inferred():
    """Test that StageResult infers success from output."""
    result = api_base.StageResult(announce="a", result="r", output={"success": False})
    assert result.success is False
    assert result.output["success"] is False


def test_inject_config_injects(monkeypatch):
    """Test that inject_config decorator injects config."""
    cfg = object()

    @api_base.inject_config
    def fn(config):
        return config

    monkeypatch.setattr("wks.api.base.WKSConfig.load", lambda: cfg)
    assert fn() is cfg


def test_get_typer_command_schema_skips_config_and_marks_required():
    """Test that get_typer_command_schema skips config and marks required params."""
    app = typer.Typer()

    def sample(config, path: str, optional: int = 3):  # type: ignore[unused-argument]
        return path, optional

    app.command(name="sample")(sample)

    schema = api_base.get_typer_command_schema(app, "sample")
    assert "config" not in schema["properties"]
    assert "path" in schema["required"]
    assert "optional" not in (schema["required"] or [])

