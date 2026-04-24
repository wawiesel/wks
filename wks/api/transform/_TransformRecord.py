from pydantic import BaseModel, field_serializer, field_validator

from ..config.URI import URI


class _TransformRecord(BaseModel):
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
        return URI(v) if isinstance(v, str) else v

    @field_validator("referenced_uris", mode="before")
    @classmethod
    def validate_referenced_uris(cls, v: list[str] | list[URI]) -> list[URI]:
        if not v:
            return []
        return [URI(item) if isinstance(item, str) else item for item in v]

    @field_serializer("file_uri", "cache_uri")
    def serialize_uri(self, uri: URI) -> str:
        return str(uri)

    @field_serializer("referenced_uris")
    def serialize_referenced_uris(self, uris: list[URI]) -> list[str]:
        return [str(uri) for uri in uris]

    @classmethod
    def from_dict(cls, data: dict) -> "_TransformRecord":
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
        return self.model_dump()

    def cache_path_from_uri(self) -> str:
        try:
            return str(self.cache_uri.path)
        except Exception:
            return str(self.cache_uri)
