from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._auto_engine import classify_input_kind, is_utf8_text
from ._EngineConfig import _EngineConfig
from ._get_engine_by_type import _get_engine_by_type
from ._RouteEngineConfig import _RouteEngineConfig
from ._supports_file import supports_file
from ._TransformEngine import _TransformEngine
from ._treesitter._language_map import resolve_language
from .mime import normalize_extension

_DEFAULT_IMAGETEXT_TYPES = [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp"]
_ROUTE_REJECT_BINARY_MESSAGE = "No transform available for binary file"


@dataclass(frozen=True)
class ResolvedEngineSelection:
    configured_name: str
    selected_type: str
    cache_engine_name: str
    options: dict[str, Any]
    engine: _TransformEngine
    kind: str | None = None


def resolve_engine_selection(
    engines: dict[str, _EngineConfig | _RouteEngineConfig],
    engine_name: str,
    file_path: Path,
    overrides: dict[str, Any] | None = None,
) -> ResolvedEngineSelection:
    if engine_name == "auto":
        raise ValueError(
            "Engine name 'auto' is not supported directly. "
            "Define a named transform engine with type 'route' and use that name."
        )

    if engine_name not in engines:
        raise ValueError(f"Engine '{engine_name}' not found in config. Available engines: {list(engines.keys())}")

    engine_config = engines[engine_name]
    overrides = overrides or {}

    if isinstance(engine_config, _RouteEngineConfig):
        return _resolve_route_engine_selection(engines, engine_name, engine_config, file_path, overrides)

    merged_options = {**engine_config.data, **overrides}
    if engine_config.type == "treesitter" and "language" not in merged_options:
        merged_options["language"] = "auto"
    if not _engine_supports_file(engine_config, file_path, merged_options):
        raise ValueError(f"Unsupported file type for engine '{engine_name}': {file_path.suffix or '<none>'}")

    engine = _get_engine_by_type(engine_config.type)

    return ResolvedEngineSelection(
        configured_name=engine_name,
        selected_type=engine_config.type,
        cache_engine_name=engine_name,
        options=merged_options,
        engine=engine,
        kind=None,
    )


def _resolve_route_engine_selection(
    engines: dict[str, _EngineConfig | _RouteEngineConfig],
    engine_name: str,
    engine_config: _RouteEngineConfig,
    file_path: Path,
    overrides: dict[str, Any],
) -> ResolvedEngineSelection:
    for target_name in engine_config.data.order:
        target_config = engines[target_name]
        if isinstance(target_config, _RouteEngineConfig):
            raise ValueError(f"Route engine '{engine_name}' cannot reference route engine '{target_name}'")

        merged_options = {**target_config.data, **overrides}
        if target_config.type == "treesitter" and "language" not in merged_options:
            merged_options["language"] = "auto"
        if not _engine_supports_file(target_config, file_path, merged_options):
            continue

        engine = _get_engine_by_type(target_config.type)
        return ResolvedEngineSelection(
            configured_name=engine_name,
            selected_type=target_config.type,
            cache_engine_name=f"{engine_name}:{target_name}",
            options=merged_options,
            engine=engine,
            kind=classify_input_kind(file_path),
        )

    if engine_config.data.passthrough_text and is_utf8_text(file_path):
        return ResolvedEngineSelection(
            configured_name=engine_name,
            selected_type="textpass",
            cache_engine_name=f"{engine_name}:passthrough_text",
            options={},
            engine=_get_engine_by_type("textpass"),
            kind="text",
        )

    if engine_config.data.reject_binary and not is_utf8_text(file_path):
        return ResolvedEngineSelection(
            configured_name=engine_name,
            selected_type="null",
            cache_engine_name=f"{engine_name}:reject_binary",
            options={"message": _ROUTE_REJECT_BINARY_MESSAGE},
            engine=_get_engine_by_type("null"),
            kind="binary",
        )

    raise ValueError(
        f"Route engine '{engine_name}' found no applicable engine or fallback for {file_path.suffix or '<none>'}"
    )


def _engine_supports_file(engine_config: _EngineConfig, file_path: Path, options: dict[str, Any]) -> bool:
    if engine_config.supported_types is not None:
        return supports_file(engine_config.supported_types, file_path)

    if engine_config.type == "docling":
        return classify_input_kind(file_path) == "document"

    if engine_config.type == "pdftext":
        return normalize_extension(file_path.suffix) == ".pdf"

    if engine_config.type == "treesitter":
        try:
            resolve_language(file_path, options)
            return True
        except ValueError:
            return False

    if engine_config.type == "textpass":
        return is_utf8_text(file_path)

    if engine_config.type == "binarypass":
        return not is_utf8_text(file_path)

    if engine_config.type == "imagetext":
        return supports_file(_DEFAULT_IMAGETEXT_TYPES, file_path)

    if engine_config.type == "null":
        return True

    return True


__all__ = ["ResolvedEngineSelection", "resolve_engine_selection"]
