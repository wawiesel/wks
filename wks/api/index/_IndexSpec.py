"""Per-index specification."""

from typing import Literal

from pydantic import BaseModel, model_validator


class _IndexSpec(BaseModel):
    """Configuration for a single named index."""

    max_tokens: int = 256
    overlap_tokens: int = 64
    min_priority: float = 0.0
    engine: str
    embedding_model: str | None = None
    embedding_mode: Literal["text", "image_text_combo"] = "text"
    image_text_weight: float | None = None

    @model_validator(mode="after")
    def validate_embedding_model(self) -> "_IndexSpec":
        """Validate semantic embedding configuration."""
        if self.embedding_model is not None and not self.embedding_model.strip():
            raise ValueError("index.embedding_model must be a non-empty string when provided")
        if self.embedding_mode == "image_text_combo":
            if self.embedding_model is None:
                raise ValueError("index.embedding_model is required when embedding_mode is 'image_text_combo'")
            if self.image_text_weight is None:
                raise ValueError("index.image_text_weight is required when embedding_mode is 'image_text_combo'")
            if not 0.0 <= self.image_text_weight <= 1.0:
                raise ValueError("index.image_text_weight must be in [0,1]")
        elif self.image_text_weight is not None:
            raise ValueError("index.image_text_weight is only valid when embedding_mode is 'image_text_combo'")
        return self
