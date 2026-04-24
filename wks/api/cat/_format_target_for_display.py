from __future__ import annotations

from pathlib import Path

from wks.api.config.URI import URI


def format_target_for_display(target: str) -> str:
    if _is_checksum(target):
        return target

    try:
        if "://" in target:
            uri = URI.from_any(target)
            label = str(uri.path) if uri.is_file else str(uri)
        else:
            label = str(Path(target).expanduser().absolute())
    except ValueError:
        label = str(Path(target).expanduser()) or target

    return label


def _is_checksum(target: str) -> bool:
    from wks.api.cat._is_checksum import _is_checksum as is_checksum

    return is_checksum(target)
