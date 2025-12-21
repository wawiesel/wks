"""MCP configuration model."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class McpInstallation(BaseModel):
    """Configuration for a single MCP installation."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(description="Installation type (e.g., 'mcpServersJson')")
    active: bool = Field(default=False, description="Whether WKS is currently installed")
    data: dict[str, Any] = Field(default_factory=dict, description="Type-specific installation data")


class McpConfig(BaseModel):
    """MCP server installation configuration."""

    model_config = ConfigDict(extra="forbid")

    installs: dict[str, McpInstallation] = Field(
        default_factory=dict,
        description="Named MCP installations",
    )
