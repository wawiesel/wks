"""Linux (systemd) specific service configuration data."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Data(BaseModel):
    """Linux systemd service configuration data."""

    model_config = ConfigDict(extra="forbid")

    unit_name: str = Field(..., description="Systemd unit name (e.g., 'wks.service')")
    enabled: bool = Field(..., description="Whether service should start automatically on boot")

    @field_validator("unit_name")
    @classmethod
    def validate_unit_name(cls, v: str) -> str:
        if not v:
            raise ValueError("service.data.unit_name is required when service.type is 'linux'")
        # Basic validation: should end with .service
        if not v.endswith(".service"):
            raise ValueError(f"service.data.unit_name must end with '.service' (e.g., 'wks.service'), got: {v!r}")
        # Basic validation: should be a valid systemd unit name
        if not v.replace(".service", "").replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                f"service.data.unit_name must be a valid systemd unit name "
                f"(alphanumeric, hyphens, underscores), got: {v!r}"
            )
        return v
