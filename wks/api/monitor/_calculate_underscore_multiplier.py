"""Underscore multiplier helpers for priority calculation."""


def _calculate_underscore_multiplier(name: str, underscore_divisor: float, only_underscore_multiplier: float) -> float:
    """Calculate underscore multiplier for a path component."""
    from ._priority_count_leading_underscores import _priority_count_leading_underscores

    if name == "_":
        return only_underscore_multiplier

    underscore_count = _priority_count_leading_underscores(name)
    if underscore_count == 0:
        return 1.0

    return 1.0 / (underscore_divisor**underscore_count)

