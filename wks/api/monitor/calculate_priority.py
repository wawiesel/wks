from pathlib import Path
from typing import Any

from wks.api.config.normalize_path import normalize_path

from ._calculate_underscore_multiplier import _calculate_underscore_multiplier
from .find_priority_dir import find_priority_dir


def calculate_priority(path: Path, priority_dirs: dict[str, float], weights: dict[str, Any]) -> float:
    path = normalize_path(path)

    priority_dir, base_priority = find_priority_dir(path, priority_dirs)

    if priority_dir is None:
        return 0.0

    depth_multiplier = float(weights["depth_multiplier"])
    underscore_multiplier = float(weights["underscore_multiplier"])
    only_underscore_multiplier = float(weights["only_underscore_multiplier"])
    extension_weights = weights["extension_weights"]

    score = float(base_priority)

    try:
        relative_parts = path.relative_to(priority_dir).parts
    except ValueError:
        relative_parts = path.parts

    for component in relative_parts[:-1]:
        score *= depth_multiplier
        score *= _calculate_underscore_multiplier(component, underscore_multiplier, only_underscore_multiplier)

    filename_stem = path.stem
    if filename_stem and (filename_stem.startswith("_") or filename_stem == "_"):
        score *= depth_multiplier
        score *= _calculate_underscore_multiplier(filename_stem, underscore_multiplier, only_underscore_multiplier)

    extension = path.suffix.lower()
    weight = float(extension_weights[extension]) if extension in extension_weights else 1.0
    score *= weight

    return score
