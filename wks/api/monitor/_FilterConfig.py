from pydantic import BaseModel, Field, field_validator


class _FilterConfig(BaseModel):
    """Filter configuration for monitor paths."""

    include_paths: list[str] = Field(...)
    exclude_paths: list[str] = Field(...)
    include_dirnames: list[str] = Field(...)
    exclude_dirnames: list[str] = Field(...)
    include_globs: list[str] = Field(...)
    exclude_globs: list[str] = Field(...)

    @field_validator("include_paths", "exclude_paths")
    @classmethod
    def _normalize_paths(cls, v: list[str]) -> list[str]:
        from wks.api.config.normalize_path import normalize_path

        return [str(normalize_path(p)) for p in v]
