from pydantic import BaseModel, ConfigDict, Field, field_validator


class McpServersJsonData(BaseModel):
    """Data for mcpServersJson installation type."""

    model_config = ConfigDict(extra="forbid")

    settings_path: str = Field(description="Path to the MCP servers JSON settings file")

    @field_validator("settings_path")
    @classmethod
    def _normalize_settings_path(cls, v: str) -> str:
        from wks.utils.normalize_path import normalize_path

        return str(normalize_path(v))
