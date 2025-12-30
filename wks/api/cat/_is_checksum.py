import re


def _is_checksum(target: str) -> bool:
    """Check if target is a 64-character hex checksum."""
    return bool(re.match(r"^[a-f0-9]{64}$", target))
