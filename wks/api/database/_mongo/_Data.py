"""MongoDB-specific configuration data."""

from pydantic import BaseModel, Field, model_validator
from pymongo.uri_parser import parse_uri


class _Data(BaseModel):
    uri: str = Field(
        ...,
        description="MongoDB connection URI (required).",
    )
    local: bool = Field(
        default=False,
        description="If true, use a locally started mongod with the provided URI/host/port.",
    )

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def validate_fields(self) -> "_Data":
        if not (
            self.uri.startswith("mongodb://") or self.uri.startswith("mongodb+srv://") or self.uri.startswith("mongodb")
        ):
            raise ValueError(f"database.uri must start with 'mongodb://' (found: {self.uri!r})")
        if self.local:
            parsed = parse_uri(self.uri)
            if not parsed.get("nodelist"):
                raise ValueError("database.uri must include host when local=true")
        return self
