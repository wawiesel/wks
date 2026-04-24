from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class _RouteEngineData(BaseModel):
    order: list[str] = Field(default_factory=list)
    passthrough_text: bool = False
    reject_binary: bool = False

    @field_validator("order")
    @classmethod
    def validate_order_entries(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str) or item.strip() == "":
                raise ValueError("route order entries must be non-empty engine names")
            cleaned = item.strip()
            if cleaned in seen:
                raise ValueError(f"route order contains duplicate engine '{cleaned}'")
            seen.add(cleaned)
            normalized.append(cleaned)
        return normalized

    @model_validator(mode="after")
    def validate_has_behavior(self) -> "_RouteEngineData":
        if len(self.order) == 0 and not self.passthrough_text and not self.reject_binary:
            raise ValueError("route engine must define order and/or a fallback policy")
        return self


class _RouteEngineConfig(BaseModel):
    type: Literal["route"] = "route"
    data: _RouteEngineData
