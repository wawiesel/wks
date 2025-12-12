"""Calculate priority score for a file according to monitor specification.

Priority Calculation (from spec):
1. Match file to deepest priority directory entry (e.g., ~/Documents → 100.0)
2. For each path component after the managed base: multiply by depth_multiplier
3. For each leading _ in a component: multiply by underscore_multiplier per underscore
4. If the component is exactly _: multiply by only_underscore_multiplier
5. Multiply by extension weight from extension_weights map (unspecified extensions use 1.0)
6. Final priority remains a float; round/format only at presentation time
"""

from pathlib import Path
from typing import Any

from ._calculate_underscore_multiplier import _calculate_underscore_multiplier
from .find_priority_dir import find_priority_dir


def calculate_priority(path: Path, priority_dirs: dict[str, float], weights: dict[str, Any]) -> float:
    """Calculate priority score for a file.

    Args:
        path: File path to calculate priority for
        priority_dirs: Dict mapping directory paths to base priority floats (from priority.dirs)
        weights: Dict with priority weights (from priority.weights):
            - depth_multiplier: float
            - underscore_multiplier: float
            - only_underscore_multiplier: float
            - extension_weights: dict[str, float] (unspecified extensions use 1.0)

    Returns:
        Priority score as float (minimum 0.0)

    Raises:
        KeyError: If required keys are missing in weights (config validation should prevent this)
        TypeError/ValueError: If values can't be converted to float (config validation should prevent this)
    """
    path = path.resolve()

    priority_dir, base_priority = find_priority_dir(path, priority_dirs)

    # If file is not within any priority directory, return 0.0
    if priority_dir is None:
        return 0.0

    depth_multiplier = float(weights["depth_multiplier"])
    underscore_multiplier = float(weights["underscore_multiplier"])
    only_underscore_multiplier = float(weights["only_underscore_multiplier"])
    extension_weights = weights["extension_weights"]

    score = float(base_priority)

    # Get relative path parts from priority directory
    # ValueError can occur if paths are on different drives (Windows) or unrelated
    # In that case, fall back to full path parts (shouldn't happen with validated config)
    try:
        relative_parts = path.relative_to(priority_dir).parts
    except ValueError:
        relative_parts = path.parts

    # Apply depth and underscore multipliers for directory components
    for component in relative_parts[:-1]:
        score *= depth_multiplier
        score *= _calculate_underscore_multiplier(component, underscore_multiplier, only_underscore_multiplier)

    # Apply underscore penalty for filename stem
    filename_stem = path.stem
    if filename_stem and (filename_stem.startswith("_") or filename_stem == "_"):
        score *= depth_multiplier
        score *= _calculate_underscore_multiplier(filename_stem, underscore_multiplier, only_underscore_multiplier)

    extension = path.suffix.lower()
    weight = float(extension_weights.get(extension, 1.0))
    score *= weight

    return score
