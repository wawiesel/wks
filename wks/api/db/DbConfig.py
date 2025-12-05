"""Database configuration with Pydantic validation."""

from typing import Any, Type

from pydantic import BaseModel, Field, model_validator

from ._mongo._DbConfigData import _DbConfigData as _MongoDbConfigData
from ._mongomock._DbConfigData import _DbConfigData as _MongoMockDbConfigData


class DbConfig(BaseModel):
    # Registry: add new backends here (ONLY place backend types are enumerated)
    _BACKEND_REGISTRY: dict[str, Type[BaseModel]] = {
        "mongo": _MongoDbConfigData,
        "mongomock": _MongoMockDbConfigData,
    }

    type: str = Field(..., description="Database backend type")
    prefix: str = Field(default="wks", description="Database prefix for collection names")
    data: BaseModel = Field(..., description="Backend-specific configuration data")

    @model_validator(mode="before")
    @classmethod
    def validate_and_populate_data(cls, values: Any) -> dict[str, Any]:
        if isinstance(values, dict):
            db_type = values.get("type")
            if not db_type:
                raise ValueError("db.type is required")
            config_data_class = cls._BACKEND_REGISTRY.get(db_type)
            if not config_data_class:
                raise ValueError(f"Unknown backend type: {db_type!r} (supported: {list(cls._BACKEND_REGISTRY.keys())})")
            data_dict = values.get("data", {})
            if not data_dict:
                raise ValueError("db.data is required")
            values["data"] = config_data_class(**data_dict)
        return values
