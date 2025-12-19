from pydantic import BaseModel, ConfigDict


class RemoteMapping(BaseModel):
    """Mapping between a local path and a remote URI."""

    model_config = ConfigDict(extra="forbid")

    local_path: str
    remote_uri: str
    type: str = "generic"  # onedrive, sharepoint, etc.


class RemoteConfig(BaseModel):
    """Configuration for remote integrations (local-first cloud support)."""

    model_config = ConfigDict(extra="forbid")

    mappings: list[RemoteMapping] = []
