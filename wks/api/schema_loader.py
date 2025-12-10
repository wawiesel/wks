"""Helpers to load and register output schemas from packaged specifications."""

import json
from importlib import resources
from typing import Any

from pydantic import BaseModel, ConfigDict, create_model

from .BaseOutputSchema import BaseOutputSchema
from .schema_registry import register_output_schema


def load_schema(domain: str) -> dict[str, Any]:
    """Load a domain's output schema JSON from packaged specifications."""
    with resources.files("docs.specifications").joinpath(f"{domain}_output.schema.json").open("r") as fh:  # type: ignore[attr-defined]
        return json.load(fh)


def build_model(schema: dict[str, Any], def_name: str) -> type[BaseModel]:
    """Create a Pydantic model from a definition within a loaded schema.
    
    All fields are required - the JSON schema must list all fields in the 'required' array.
    This enforces the rule: no optional fields, all fields must always be present.
    """
    definition = schema["definitions"][def_name]
    props: dict[str, tuple[type[Any], Any]] = {}

    def _collect(defn: dict[str, Any]) -> None:
        for prop_name in defn.get("properties", {}):
            props[prop_name] = (Any, ...)
        for sub in defn.get("allOf", []):
            if isinstance(sub, dict):
                _collect(sub)

    _collect(definition)
    
    return create_model(  # type: ignore[arg-type]
        def_name,
        __base__=BaseOutputSchema,
        __config__=ConfigDict(extra="forbid"),
        **props,
    )


def load_models(domain: str) -> dict[str, type[BaseModel]]:
    """Load all *Output models for a domain without registering."""
    schema = load_schema(domain)
    prefix = domain.capitalize()
    models: dict[str, type[BaseModel]] = {}
    for def_name in schema.get("definitions", {}):
        if not def_name.startswith(prefix) or not def_name.endswith("Output"):
            continue
        cmd_name = def_name[len(prefix): -len("Output")].lower()
        model = build_model(schema, def_name)
        models[def_name] = model
    return models


def register_from_schema(domain: str) -> dict[str, type[BaseModel]]:
    """Auto-register all *Output definitions for a domain. Returns the models mapping."""
    models = load_models(domain)
    prefix = domain.capitalize()
    for def_name, model in models.items():
        cmd_name = def_name[len(prefix): -len("Output")].lower()
        register_output_schema(domain, cmd_name, model)
    return models
