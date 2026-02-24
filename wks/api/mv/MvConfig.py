"""Mv configuration for WKSConfig."""

from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class MvConfig(BaseModel):
    """Mv section of WKS configuration."""

    always_allow_sources: list[str] = Field(
        default_factory=list,
        description="Source directories from which moves are always allowed (e.g., ~/Downloads)",
    )

    @field_validator("always_allow_sources")
    @classmethod
    def _normalize_paths(cls, v: list[str]) -> list[str]:
        """Normalize paths by expanding ~ and making absolute."""
        from wks.api.config.normalize_path import normalize_path

        return [str(normalize_path(p)) for p in v]

    def is_always_allowed_source(self, path: Path) -> bool:
        """Check if a path is within an always-allowed source directory."""
        from wks.api.config.normalize_path import normalize_path

        resolved = normalize_path(path)
        for allowed in self.always_allow_sources:
            allowed_path = Path(allowed)
            if resolved == allowed_path or resolved.is_relative_to(allowed_path):
                return True
        return False
