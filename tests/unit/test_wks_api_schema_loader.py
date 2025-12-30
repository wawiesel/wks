"""Unit tests for wks.api.schema_loader module."""

from wks.api.schema_loader import SchemaLoader


def test_schema_loader_loads_config_schema() -> None:
    schema = SchemaLoader.load_schema("config")
    assert isinstance(schema, dict)
    assert "definitions" in schema
    assert "ConfigListOutput" in schema["definitions"]


def test_schema_loader_load_models_returns_output_models() -> None:
    models = SchemaLoader.load_models("config")
    assert "ConfigListOutput" in models
    assert "ConfigShowOutput" in models
