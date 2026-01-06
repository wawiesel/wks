"""Text diff output dataclass."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TextDiffOutput:
    """Text diff output (unified diff)."""

    unified_diff: str
    patch_format: str = "unified"
