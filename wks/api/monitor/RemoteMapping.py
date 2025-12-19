from pydantic import BaseModel, ConfigDict


class RemoteMapping(BaseModel):
    """Mapping between a local path and a remote URI."""

    model_config = ConfigDict(extra="forbid")

    local_path: str
    remote_uri: str
    type: str = "generic"  # onedrive, sharepoint, etc.
