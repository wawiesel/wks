"""Transform record model."""

from pydantic import BaseModel


class _TransformRecord(BaseModel):
    """Transform cache record from wks.transform collection."""

    file_uri: str
    cache_uri: str
    checksum: str
    size_bytes: int
    last_accessed: str
    created_at: str
    engine: str
    options_hash: str
    referenced_uris: list[str]

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
        from ..URI import URI

        try:
            return str(URI(self.cache_uri).path)
        except Exception:
            return self.cache_uri
