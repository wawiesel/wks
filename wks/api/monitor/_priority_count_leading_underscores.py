"""Count leading underscores in a path component."""


def _priority_count_leading_underscores(name: str) -> int:
    count = 0
    for char in name:
        if char == "_":
            count += 1
        else:
            break
    return count
