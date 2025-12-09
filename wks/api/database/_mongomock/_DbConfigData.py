"""Mock MongoDB-specific configuration data for testing."""

from pydantic import BaseModel, Field, field_validator


class _DbConfigData(BaseModel):
    uri: str = Field(..., description="Mock connection URI")

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, v: str) -> str:
        if not v:
            raise ValueError("db.uri is required when db.type is 'mongomock'")
        return v
