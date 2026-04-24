from pydantic import BaseModel, Field


class BaseOutputSchema(BaseModel):
    errors: list[str] = Field(default_factory=list, description="List of error messages, empty list if no errors")
    warnings: list[str] = Field(default_factory=list, description="List of warning messages, empty list if no warnings")
