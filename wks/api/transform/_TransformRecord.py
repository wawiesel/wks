"""Transform record model."""

from pydantic import BaseModel, Field


class _TransformRecord(BaseModel):
    """Transform cache record from wks.transform collection."""

    file_uri: str
    cache_uri: str
    checksum: str
    size_bytes: int = Field(default=0)
    last_accessed: str
    created_at: str
    engine: str
    options_hash: str
    referenced_uris: list[str] = Field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "_TransformRecord":
        """Create TransformRecord from MongoDB document.

        Handles backward compatibility for old records with cache_location.
        """
        # Backward compat: old records have cache_location, new have cache_uri
        cache_uri = data.get("cache_uri")
        if not cache_uri and "cache_location" in data:
            # Convert old path to URI format
            from pathlib import Path

            from ...utils.path_to_uri import path_to_uri

            cache_uri = path_to_uri(Path(data["cache_location"]))

        return cls(
            file_uri=data["file_uri"],
            cache_uri=cache_uri or "",
            checksum=data["checksum"],
            size_bytes=data.get("size_bytes") or 0,
            last_accessed=data["last_accessed"],
            created_at=data["created_at"],
            engine=data["engine"],
            options_hash=data["options_hash"],
            referenced_uris=data.get("referenced_uris") or [],
        )

    def to_dict(self) -> dict:
        """Convert to MongoDB document."""
        return self.model_dump()

    def cache_path_from_uri(self) -> str:
        """Get local path from cache_uri using standard URI parsing."""
        from ...utils.uri_to_path import uri_to_path

        try:
            return str(uri_to_path(self.cache_uri))
        except Exception:
            return self.cache_uri
