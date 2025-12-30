"""Transform result model."""

from pydantic import BaseModel


class _TransformResult(BaseModel):
    """Result of a transform operation."""

    source_uri: str
    destination_uri: str
    engine: str
    status: str
    checksum: str
    output_content: str | None = None
    processing_time_ms: int | None = None
    cached: bool = False
