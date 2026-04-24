from dataclasses import dataclass


@dataclass(frozen=True)
class BinaryDiffOutput:
    patch_path: str
    patch_size_bytes: int
