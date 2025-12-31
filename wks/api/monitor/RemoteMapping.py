from pydantic import BaseModel, ConfigDict, field_validator


class RemoteMapping(BaseModel):
    """Mapping between a local path and a remote URI."""

    model_config = ConfigDict(extra="forbid")

    local_path: str
    remote_uri: str
    type: str = "generic"  # onedrive, sharepoint, etc.

    @field_validator("local_path")
    @classmethod
    def _normalize_local_path(cls, v: str) -> str:
        from wks.utils.normalize_path import normalize_path

        return str(normalize_path(v))
