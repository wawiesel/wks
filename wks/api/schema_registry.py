"""Output schema registry.

This is a kernel module: callers register and query output schemas by (domain, command).
"""

from pydantic import BaseModel


class SchemaRegistry:
    def __init__(self) -> None:
        self._schemas: dict[tuple[str, str], type[BaseModel]] = {}

    def register_output_schema(self, domain: str, command_name: str, schema_class: type[BaseModel]) -> None:
        key = (domain, command_name)
        if key in self._schemas:
            raise ValueError(f"Schema already registered for {domain}.{command_name}")
        self._schemas[key] = schema_class

    def get_output_schema(self, domain: str, command_name: str) -> type[BaseModel] | None:
        return self._schemas.get((domain, command_name))


schema_registry = SchemaRegistry()
