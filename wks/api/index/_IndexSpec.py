"""Per-index specification."""

from pydantic import BaseModel, model_validator


class _IndexSpec(BaseModel):
    """Configuration for a single named index."""

    max_tokens: int = 256
    overlap_tokens: int = 64
    min_priority: float = 0.0
    engine: str
    embedding_model: str | None = None

    @model_validator(mode="after")
    def validate_embedding_model(self) -> "_IndexSpec":
        """Ensure embedding_model is a non-empty string when configured."""
        if self.embedding_model is not None and not self.embedding_model.strip():
            raise ValueError("index.embedding_model must be a non-empty string when provided")
        return self
