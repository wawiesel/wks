import re


def _is_checksum(target: str) -> bool:
    return bool(re.match(r"^[a-f0-9]{64}$", target))
