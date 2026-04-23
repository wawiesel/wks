"""Resolve a configured transform engine name into an executable selection."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._auto_engine import classify_input_kind
from ._EngineConfig import _EngineConfig
from ._get_engine_by_type import _get_engine_by_type
from ._supports_file import supports_file
from ._TransformEngine import _TransformEngine


@dataclass(frozen=True)
class ResolvedEngineSelection:
    """Concrete engine selection for a specific file."""

    configured_name: str
    selected_type: str
    cache_engine_name: str
    options: dict[str, Any]
    engine: _TransformEngine
    kind: str | None = None


def resolve_engine_selection(
    engines: dict[str, _EngineConfig],
    engine_name: str,
    file_path: Path,
    overrides: dict[str, Any] | None = None,
) -> ResolvedEngineSelection:
    """Resolve engine_name against file_path and config-defined routing."""
    if engine_name == "auto":
        raise ValueError(
            "Engine name 'auto' is not supported directly. "
            "Define a named transform engine with type 'route' and use that name."
        )

    if engine_name not in engines:
        raise ValueError(f"Engine '{engine_name}' not found in config. Available engines: {list(engines.keys())}")

    engine_config = engines[engine_name]
    if not supports_file(engine_config.supported_types, file_path):
        raise ValueError(f"Unsupported file type for engine '{engine_name}': {file_path.suffix or '<none>'}")

    overrides = overrides or {}

    if engine_config.type == "route":
        kind = classify_input_kind(file_path)
        route_spec = engine_config.data.get(kind)
        if not isinstance(route_spec, dict):
            raise ValueError(f"Route engine '{engine_name}' missing route for kind '{kind}'")

        route_type = route_spec.get("type")
        if not isinstance(route_type, str) or not route_type:
            raise ValueError(f"Route engine '{engine_name}' has invalid type for kind '{kind}'")
        if route_type == "route":
            raise ValueError(f"Route engine '{engine_name}' cannot nest route kind '{kind}'")

        route_data = route_spec.get("data", {})
        if route_data is None:
            route_data = {}
        if not isinstance(route_data, dict):
            raise ValueError(f"Route engine '{engine_name}' data for kind '{kind}' must be a dict")

        engine = _get_engine_by_type(route_type)
        merged_options = {**route_data, **overrides}
        if route_type == "treesitter" and "language" not in merged_options:
            merged_options["language"] = "auto"

        return ResolvedEngineSelection(
            configured_name=engine_name,
            selected_type=route_type,
            cache_engine_name=f"{engine_name}:{kind}:{route_type}",
            options=merged_options,
            engine=engine,
            kind=kind,
        )

    engine = _get_engine_by_type(engine_config.type)
    merged_options = {**engine_config.data, **overrides}
    if engine_config.type == "treesitter" and "language" not in merged_options:
        merged_options["language"] = "auto"

    return ResolvedEngineSelection(
        configured_name=engine_name,
        selected_type=engine_config.type,
        cache_engine_name=engine_name,
        options=merged_options,
        engine=engine,
        kind=None,
    )


__all__ = ["ResolvedEngineSelection", "resolve_engine_selection"]
