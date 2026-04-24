from dataclasses import dataclass


@dataclass
class _Chunk:
    text: str
    uri: str
    chunk_index: int
    tokens: int
    is_continuation: bool
