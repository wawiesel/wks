from pydantic import BaseModel, ConfigDict, Field

from .RemoteMapping import RemoteMapping


class RemoteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mappings: list[RemoteMapping] = Field(...)
