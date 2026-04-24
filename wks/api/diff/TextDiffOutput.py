from dataclasses import dataclass


@dataclass(frozen=True)
class TextDiffOutput:
    unified_diff: str
    patch_format: str = "unified"
