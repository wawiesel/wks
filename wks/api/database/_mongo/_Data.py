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
    db_path: str | None = Field(
        default=None,
        description="Filesystem path for local mongod data (required when local=true).",
    )
    port: int | None = Field(
        default=None,
        ge=1,
        le=65535,
        description="Port for local mongod (required when local=true).",
    )
    bind_ip: str | None = Field(
        default=None,
        description="Bind address for local mongod (required when local=true).",
    )

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
            if not self.db_path:
                raise ValueError("database.data.db_path is required when database.data.local=true")
            if not self.port:
                raise ValueError("database.data.port is required when database.data.local=true")
            if not self.bind_ip:
                raise ValueError("database.data.bind_ip is required when database.data.local=true")
        return self
