"""Configuration for mcpServersJson installation type (UNO: single model)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .McpServersJsonData import McpServersJsonData


class McpServersJsonInstall(BaseModel):
    """Configuration for mcpServersJson installation type."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["mcpServersJson"] = Field(description="Installation type")
    active: bool = Field(default=False, description="Whether WKS is currently installed")
    data: McpServersJsonData = Field(description="Type-specific installation data")
