"""Unit tests for wks.api.schema_registry module."""

import pytest

from wks.api.config.schema_registry import schema_registry


def test_schema_registry_can_query_for_registered_command() -> None:
    # Import the public domain module to ensure schemas are registered.
    import wks.api.config  # noqa: F401

    schema_cls = schema_registry.get_output_schema("config", "list")
    assert schema_cls is not None
    assert schema_cls.__name__ == "ConfigListOutput"


def test_schema_registry_rejects_double_registration() -> None:
    from pydantic import BaseModel

    from wks.api.config.schema_registry import SchemaRegistry

    class DummyOutput(BaseModel):
        pass

    local_registry = SchemaRegistry()
    local_registry.register_output_schema("unit_test", "dummy", DummyOutput)
    with pytest.raises(ValueError):
        local_registry.register_output_schema("unit_test", "dummy", DummyOutput)
