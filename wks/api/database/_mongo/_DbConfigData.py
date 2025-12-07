"""MongoDB-specific configuration data."""

from pydantic import BaseModel, Field, field_validator


class _DbConfigData(BaseModel):
    uri: str = Field(..., description="MongoDB connection URI")

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, v: str) -> str:
        if not v:
            raise ValueError("db.uri is required when db.type is 'mongo'")
        if not (v.startswith("mongodb://") or v.startswith("mongodb+srv://") or v.startswith("mongodb")):
            raise ValueError(f"db.uri must start with 'mongodb://' (found: {v!r})")
        return v
