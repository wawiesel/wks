"""Transform result model."""

from pydantic import BaseModel


class _TransformResult(BaseModel):
    """Result of a transform operation."""
    
    source_uri: str
    engine: str
    status: str
    checksum: str
    output_path: str
