"""MongoDB-specific configuration data."""

from pydantic import BaseModel, Field, field_validator


class _Data(BaseModel):
    uri: str = Field(..., description="MongoDB connection URI")

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, v: str) -> str:
        if not v:
            raise ValueError("database.uri is required when database.type is 'mongo'")
        if not (v.startswith("mongodb://") or v.startswith("mongodb+srv://") or v.startswith("mongodb")):
            raise ValueError(f"database.uri must start with 'mongodb://' (found: {v!r})")
        return v

