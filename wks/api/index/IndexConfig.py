"""Index configuration for WKSConfig."""

from pydantic import BaseModel

from ._IndexSpec import _IndexSpec


class IndexConfig(BaseModel):
    """Index section of WKS configuration."""

    default_index: str
    indexes: dict[str, _IndexSpec]
