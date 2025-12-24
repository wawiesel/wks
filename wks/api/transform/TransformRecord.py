"""Transform record model."""

from dataclasses import dataclass


@dataclass
class TransformRecord:
    """Transform cache record from wks.transform collection."""

    file_uri: str
    checksum: str
    size_bytes: int
    last_accessed: str  # ISO timestamp
    created_at: str  # ISO timestamp
    engine: str
    options_hash: str
    cache_location: str

    @classmethod
    def from_dict(cls, data: dict) -> "TransformRecord":
        """Create TransformRecord from MongoDB document."""
        return cls(
            file_uri=data["file_uri"],
            checksum=data["checksum"],
            size_bytes=data["size_bytes"],
            last_accessed=data["last_accessed"],
            created_at=data["created_at"],
            engine=data["engine"],
            options_hash=data["options_hash"],
            cache_location=data["cache_location"],
        )

    def to_dict(self) -> dict:
        """Convert to MongoDB document."""
        return {
            "file_uri": self.file_uri,
            "checksum": self.checksum,
            "size_bytes": self.size_bytes,
            "last_accessed": self.last_accessed,
            "created_at": self.created_at,
            "engine": self.engine,
            "options_hash": self.options_hash,
            "cache_location": self.cache_location,
        }
