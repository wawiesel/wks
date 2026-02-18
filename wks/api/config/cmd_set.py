"""Set or remove a configuration value by dot-path key."""

import json
from collections.abc import Iterator
from typing import Any

from ..config.StageResult import StageResult
from . import ConfigSetOutput
from .WKSConfig import WKSConfig


def _parse_value(raw: str) -> Any:
    """Parse a value string as JSON, falling back to plain string."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw


def _deep_set(d: dict, keys: list[str], value: Any) -> None:
    """Set a nested dict value by key path."""
    for key in keys[:-1]:
        if key not in d or not isinstance(d[key], dict):
            d[key] = {}
        d = d[key]
    d[keys[-1]] = value


def _deep_delete(d: dict, keys: list[str]) -> bool:
    """Delete a nested dict value by key path. Returns True if deleted."""
    for key in keys[:-1]:
        if key not in d or not isinstance(d[key], dict):
            return False
        d = d[key]
    return d.pop(keys[-1], _SENTINEL) is not _SENTINEL


_SENTINEL = object()


def cmd_set(key: str, value: str = "", delete: bool = False) -> StageResult:
    """Set, modify, or remove a configuration value by dot-path key."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()
        config_dict = config.to_dict()

        keys = key.split(".")
        if not keys or not all(keys):
            yield (1.0, "Complete")
            result_obj.result = f"Invalid key: {key}"
            result_obj.output = ConfigSetOutput(
                errors=[f"Invalid key path: {key}"],
                warnings=[],
                key=key,
                value=None,
                config_path=str(config.path),
            ).model_dump(mode="python")
            result_obj.success = False
            return

        if delete:
            yield (0.4, f"Removing {key}...")
            if not _deep_delete(config_dict, keys):
                yield (1.0, "Complete")
                result_obj.result = f"Key not found: {key}"
                result_obj.output = ConfigSetOutput(
                    errors=[f"Key not found: {key}"],
                    warnings=[],
                    key=key,
                    value=None,
                    config_path=str(config.path),
                ).model_dump(mode="python")
                result_obj.success = False
                return
            action = "Removed"
            result_value = None
        else:
            if not value and value != "0":
                yield (1.0, "Complete")
                result_obj.result = "No value provided (use --delete to remove a key)"
                result_obj.output = ConfigSetOutput(
                    errors=["No value provided"],
                    warnings=[],
                    key=key,
                    value=None,
                    config_path=str(config.path),
                ).model_dump(mode="python")
                result_obj.success = False
                return
            parsed = _parse_value(value)
            yield (0.4, f"Setting {key}...")
            _deep_set(config_dict, keys, parsed)
            action = "Set"
            result_value = parsed

        # Validate by loading modified dict through Pydantic
        yield (0.6, "Validating configuration...")
        try:
            new_config = WKSConfig(**config_dict)
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = f"Validation failed: {e}"
            result_obj.output = ConfigSetOutput(
                errors=[str(e)],
                warnings=[],
                key=key,
                value=result_value,
                config_path=str(config.path),
            ).model_dump(mode="python")
            result_obj.success = False
            return

        yield (0.8, "Saving configuration...")
        new_config.save()

        yield (1.0, "Complete")
        msg = f"{action} {key}" + (f" = {json.dumps(result_value)}" if result_value is not None else "")
        result_obj.result = msg
        result_obj.output = ConfigSetOutput(
            errors=[],
            warnings=[],
            key=key,
            value=result_value,
            config_path=str(config.path),
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce=f"Updating {key}...",
        progress_callback=do_work,
    )
