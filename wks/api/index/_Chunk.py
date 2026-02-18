"""Chunk dataclass for index storage."""

from dataclasses import dataclass


@dataclass
class _Chunk:
    """A text chunk produced by the sliding window."""

    text: str
    uri: str
    chunk_index: int
    tokens: int
    is_continuation: bool
