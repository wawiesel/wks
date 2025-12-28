"""Cat configuration for WKSConfig."""

from typing import Optional

from pydantic import BaseModel


class CatConfig(BaseModel):
    """Cat section of WKS configuration."""

    default_engine: Optional[str] = None
