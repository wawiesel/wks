def _calculate_underscore_multiplier(
    name: str, underscore_multiplier: float, only_underscore_multiplier: float
) -> float:
    if name == "_":
        return only_underscore_multiplier

    underscore_count = 0
    for char in name:
        if char == "_":
            underscore_count += 1
        else:
            break

    if underscore_count == 0:
        return 1.0

    return underscore_multiplier**underscore_count
