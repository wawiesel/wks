"""Per-index specification."""

from pydantic import BaseModel


class _IndexSpec(BaseModel):
    """Configuration for a single named index."""

    max_tokens: int = 256
    overlap_tokens: int = 64
    min_priority: float = 0.0
    engine: str
