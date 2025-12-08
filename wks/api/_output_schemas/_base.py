"""Base output schema with standard errors and warnings fields."""

from pydantic import BaseModel, Field


class BaseOutputSchema(BaseModel):
    """Base schema for all API command outputs.

    All commands must include errors and warnings lists for consistency.
    """

    errors: list[str] = Field(default_factory=list, description="List of error messages, empty list if no errors")
    warnings: list[str] = Field(default_factory=list, description="List of warning messages, empty list if no warnings")

