"""Load and register output schemas from packaged specifications."""

import json
from importlib import resources
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, create_model

from .BaseOutputSchema import BaseOutputSchema
from .schema_registry import schema_registry


class SchemaLoader:
    @classmethod
    def load_schema(cls, domain: str) -> dict[str, Any]:
        if domain == "mcp":
            # MCCP is top-level
            root = resources.files("wks.mcp")
        else:
            root = resources.files(f"wks.api.{domain}")

        path = root.joinpath("schema.json")
        with cast(Any, path).open("r") as fh:
            return json.load(fh)

    @classmethod
    def build_model(cls, schema: dict[str, Any], def_name: str) -> type[BaseModel]:
        definition = schema["definitions"][def_name]
        props: dict[str, tuple[type[Any], Any]] = {}

        def _collect(defn: dict[str, Any]) -> None:
            if "properties" in defn:
                for prop_name in defn["properties"]:
                    props[prop_name] = (Any, ...)
            if "allOf" in defn:
                for sub in defn["allOf"]:
                    if isinstance(sub, dict):
                        _collect(sub)

        _collect(definition)

        return create_model(  # type: ignore[call-overload,arg-type]
            def_name,
            __base__=BaseOutputSchema,
            __config__=ConfigDict(extra="forbid"),
            **props,
        )

    @classmethod
    def load_models(cls, domain: str) -> dict[str, type[BaseModel]]:
        schema = cls.load_schema(domain)
        prefix = domain.capitalize()
        models: dict[str, type[BaseModel]] = {}
        if "definitions" in schema:
            for def_name in schema["definitions"]:
                if not def_name.startswith(prefix) or not def_name.endswith("Output"):
                    continue
                model = cls.build_model(schema, def_name)
                models[def_name] = model
        return models

    @classmethod
    def register_from_schema(cls, domain: str) -> dict[str, type[BaseModel]]:
        # Backward compatibility or if we still need domain-based lookup
        if domain == "mcp":
            package = "wks.mcp"
        else:
            package = f"wks.api.{domain}"
        return cls.register_from_package(package)

    @classmethod
    def register_from_package(cls, package_name: str) -> dict[str, type[BaseModel]]:
        # Load schema from the package
        root = resources.files(package_name)
        path = root.joinpath("schema.json")
        with cast(Any, path).open("r") as fh:
            schema = json.load(fh)

        # Build models
        prefix = package_name.split(".")[-1].capitalize()
        models: dict[str, type[BaseModel]] = {}
        if "definitions" in schema:
            for def_name in schema["definitions"]:
                if not def_name.startswith(prefix) or not def_name.endswith("Output"):
                    continue
                model = cls.build_model(schema, def_name)
                models[def_name] = model

        # Register in registry
        domain = package_name.split(".")[-1] # infer domain from package last part
        for def_name, model in models.items():
            cmd_name = def_name[len(prefix) : -len("Output")].lower()
            schema_registry.register_output_schema(domain, cmd_name, model)

        return models
