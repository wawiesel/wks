from pydantic import BaseModel, ConfigDict, Field

from .McpInstallation import McpInstallation


class McpConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    installs: dict[str, McpInstallation] = Field(
        default_factory=dict,
        description="Named MCP installations",
    )
