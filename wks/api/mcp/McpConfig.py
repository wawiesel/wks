"""MCP configuration model."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class McpServersJsonData(BaseModel):
    """Data for mcpServersJson installation type."""

    model_config = ConfigDict(extra="forbid")

    settings_path: str = Field(description="Path to the MCP servers JSON settings file")


class McpServersJsonInstall(BaseModel):
    """Configuration for mcpServersJson installation type."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["mcpServersJson"] = Field(description="Installation type")
    active: bool = Field(default=False, description="Whether WKS is currently installed")
    data: McpServersJsonData = Field(description="Type-specific installation data")


# Union of all installation types - add new types here as they're implemented
McpInstallation = Annotated[
    McpServersJsonInstall,  # Add more types with: Type1 | Type2 | Type3
    Field(discriminator="type"),
]


class McpConfig(BaseModel):
    """MCP server installation configuration."""

    model_config = ConfigDict(extra="forbid")

    installs: dict[str, McpInstallation] = Field(
        default_factory=dict,
        description="Named MCP installations",
    )
