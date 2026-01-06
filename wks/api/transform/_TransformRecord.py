"""Transform record model."""

from pydantic import BaseModel, field_serializer, field_validator

from ..config.URI import URI


class _TransformRecord(BaseModel):
    """Transform cache record from wks.transform collection."""

    file_uri: URI
    cache_uri: URI
    checksum: str
    size_bytes: int
    last_accessed: str
    created_at: str
    engine: str
    options_hash: str
    referenced_uris: list[URI]

    @field_validator("file_uri", "cache_uri", mode="before")
    @classmethod
    def validate_uri(cls, v: str | URI) -> URI:
        """Convert string to URI if needed."""
        return URI(v) if isinstance(v, str) else v

    @field_validator("referenced_uris", mode="before")
    @classmethod
    def validate_referenced_uris(cls, v: list[str] | list[URI]) -> list[URI]:
        """Convert list of strings to list of URIs if needed."""
        if not v:
            return []
        return [URI(item) if isinstance(item, str) else item for item in v]

    @field_serializer("file_uri", "cache_uri")
    def serialize_uri(self, uri: URI) -> str:
        """Serialize URI to string for MongoDB storage."""
        return str(uri)

    @field_serializer("referenced_uris")
    def serialize_referenced_uris(self, uris: list[URI]) -> list[str]:
        """Serialize list of URIs to list of strings for MongoDB storage."""
        return [str(uri) for uri in uris]

    @classmethod
    def from_dict(cls, data: dict) -> "_TransformRecord":
        """Create TransformRecord from MongoDB document."""
        return cls(
            file_uri=data["file_uri"],
            cache_uri=data["cache_uri"],
            checksum=data["checksum"],
            size_bytes=data["size_bytes"],
            last_accessed=data["last_accessed"],
            created_at=data["created_at"],
            engine=data["engine"],
            options_hash=data["options_hash"],
            referenced_uris=data["referenced_uris"],
        )

    def to_dict(self) -> dict:
        """Convert to MongoDB document."""
        return self.model_dump()

    def cache_path_from_uri(self) -> str:
        """Get local path from cache_uri using standard URI parsing."""
        try:
            return str(self.cache_uri.path)
        except Exception:
            return str(self.cache_uri)
