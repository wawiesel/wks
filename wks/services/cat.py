"""Shared cat service logic."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from wks.api.cat._format_target_for_display import format_target_for_display
from wks.api.config.normalize_path import normalize_path
from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.api.transform import MAX_GENERATOR_ITERATIONS
from wks.api.transform._get_controller import _get_controller

from ._models import FailureKind, ServiceResponse


class CatRequest(BaseModel):
    """Inputs for cached content retrieval."""

    model_config = ConfigDict(extra="forbid")

    target: str
    output_path: Path | None = None
    engine: str | None = None


class CatResponse(ServiceResponse):
    """Cat service output."""

    model_config = ConfigDict(extra="forbid")

    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    content: str | None = None
    target: str
    checksum: str | None = None
    output_path: str | None = None


def read_content(request: CatRequest, *, config: WKSConfig | None = None) -> CatResponse:
    """Retrieve transformed or cached content for a target."""
    loaded_config = config or WKSConfig.load()
    display_target = format_target_for_display(request.target)
    try:
        cache_key = request.target
        with _get_controller(loaded_config) as controller:
            if not _is_checksum(request.target):
                file_path = _resolve_file_path(request.target, loaded_config)
                if not file_path.exists():
                    return _error_response(
                        message=f"File not found: {file_path}",
                        failure_kind="not_found",
                        target=request.target,
                        output_path=request.output_path,
                        errors=[f"File not found: {file_path}"],
                    )
                selected_engine = _select_engine(file_path, request.engine, loaded_config)
                cache_key = _transform_file(controller, file_path, selected_engine)

            content = controller.get_content(cache_key, request.output_path)
        return CatResponse(
            success=True,
            message=f"Retrieved content for {display_target}",
            errors=[],
            warnings=[],
            content=content,
            target=request.target,
            checksum=cache_key,
            output_path=str(request.output_path) if request.output_path else None,
        )
    except Exception as exc:
        return _error_response(
            message=str(exc),
            failure_kind="runtime",
            target=request.target,
            output_path=request.output_path,
            errors=[str(exc)],
        )


def _is_checksum(target: str) -> bool:
    """Return whether the target is a checksum key."""
    from wks.api.cat._is_checksum import _is_checksum as is_checksum

    return is_checksum(target)


def _select_engine(file_path: Path, engine: str | None, config: WKSConfig) -> str:
    """Select the transform engine for a file."""
    from wks.api.cat._select_engine import _select_engine as select_engine

    return select_engine(file_path, engine, config)


def _transform_file(controller, file_path: Path, engine: str) -> str:
    """Transform a file through the shared controller and return its cache key."""
    generator = controller.transform(file_path, engine, {})
    try:
        for _ in range(MAX_GENERATOR_ITERATIONS):
            next(generator)
        next(generator)
        raise RuntimeError("Transform generator exceeded MAX_GENERATOR_ITERATIONS")
    except StopIteration as exc:
        cache_key, _cached = exc.value
        return cache_key


def _resolve_file_path(target: str, config: WKSConfig) -> Path:
    """Resolve a target string to a real filesystem path."""
    if "://" in target:
        return URI.from_any(target, vault_path=Path(config.vault.base_dir)).to_path(Path(config.vault.base_dir))
    return normalize_path(target)


def _error_response(
    *,
    message: str,
    failure_kind: FailureKind,
    target: str,
    output_path: Path | None,
    errors: list[str],
) -> CatResponse:
    """Build a failed cat response."""
    return CatResponse(
        success=False,
        message=message,
        failure_kind=failure_kind,
        errors=errors,
        warnings=[],
        content=None,
        target=target,
        checksum=None,
        output_path=str(output_path) if output_path else None,
    )
