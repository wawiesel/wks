"""Priority calculation helpers for monitor API."""

from pathlib import Path

from ._priority_find_priority_dir import _priority_find_priority_dir
from ._calculate_underscore_multiplier import _calculate_underscore_multiplier


def _calculate_priority(path: Path, managed_dirs: dict[str, float], priority_config: dict) -> float:
    """Calculate priority score for a file."""
    path = path.resolve()

    priority_dir, base_priority = _priority_find_priority_dir(path, managed_dirs)

    depth_multiplier = float(priority_config["depth_multiplier"])
    underscore_divisor = float(priority_config["underscore_divisor"])
    only_underscore_multiplier = float(priority_config["single_underscore_divisor"])
    extension_weights = priority_config["extension_weights"]
    default_weight = float(extension_weights["default"])

    score = float(base_priority)

    if priority_dir:
        try:
            relative_parts = path.relative_to(priority_dir).parts
        except ValueError:
            relative_parts = path.parts
    else:
        relative_parts = path.parts

    # Apply depth and underscore multipliers for directory components
    for component in relative_parts[:-1]:
        score *= depth_multiplier
        score *= _calculate_underscore_multiplier(component, underscore_divisor, only_underscore_multiplier)

    # Apply underscore penalty for filename stem
    filename_stem = path.stem
    if filename_stem and (filename_stem.startswith("_") or filename_stem == "_"):
        score *= depth_multiplier
        score *= _calculate_underscore_multiplier(filename_stem, underscore_divisor, only_underscore_multiplier)

    extension = path.suffix.lower()
    weight = float(extension_weights.get(extension, default_weight))
    score *= weight

    return max(0.0, score)

