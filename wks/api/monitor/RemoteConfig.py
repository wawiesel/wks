from pydantic import BaseModel, ConfigDict

from .RemoteMapping import RemoteMapping


class RemoteConfig(BaseModel):
    """Configuration for remote integrations (local-first cloud support)."""

    model_config = ConfigDict(extra="forbid")

    mappings: list[RemoteMapping] = []
