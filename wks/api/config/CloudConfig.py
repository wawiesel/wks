from pydantic import BaseModel, ConfigDict


class CloudMapping(BaseModel):
    """Mapping between a local path and a remote URL."""

    model_config = ConfigDict(extra="forbid")

    local_path: str
    remote_url: str
    type: str = "onedrive"


class CloudConfig(BaseModel):
    """Configuration for cloud integrations."""

    model_config = ConfigDict(extra="forbid")

    mappings: list[CloudMapping] = []
