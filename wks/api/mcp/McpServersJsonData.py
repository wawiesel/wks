"""Data for mcpServersJson installation type."""

from pydantic import BaseModel, ConfigDict, Field


class McpServersJsonData(BaseModel):
    """Data for mcpServersJson installation type."""

    model_config = ConfigDict(extra="forbid")

    settings_path: str = Field(description="Path to the MCP servers JSON settings file")
