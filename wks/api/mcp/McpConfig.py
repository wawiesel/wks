"""MCP server installation configuration (UNO: single model)."""

from pydantic import BaseModel, ConfigDict, Field

from .McpInstallation import McpInstallation


class McpConfig(BaseModel):
    """MCP server installation configuration."""

    model_config = ConfigDict(extra="forbid")

    installs: dict[str, McpInstallation] = Field(
        default_factory=dict,
        description="Named MCP installations",
    )
