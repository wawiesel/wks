"""Cat configuration for WKSConfig."""

from pydantic import BaseModel


class CatConfig(BaseModel):
    """Cat section of WKS configuration."""

    default_engine: str
    mime_engines: dict[str, str] | None = None
