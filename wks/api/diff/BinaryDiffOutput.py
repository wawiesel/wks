"""Binary diff output dataclass."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BinaryDiffOutput:
    """Binary diff output (patch metadata)."""

    patch_path: str
    patch_size_bytes: int
