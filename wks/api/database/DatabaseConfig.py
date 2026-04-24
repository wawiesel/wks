from typing import Any

from pydantic import BaseModel, Field, model_validator

from ._mongo._Data import _Data as _MongoData
from ._mongomock._Data import _Data as _MongomockData

_BACKEND_REGISTRY: dict[str, type[BaseModel]] = {
    "mongo": _MongoData,
    "mongomock": _MongomockData,
}


class DatabaseConfig(BaseModel):
    _BACKEND_REGISTRY: dict[str, type[BaseModel]] = _BACKEND_REGISTRY

    type: str = Field(..., description="Database backend type")
    prefix: str = Field(..., description="Database prefix for collection names")
    prune_frequency_secs: float = Field(3600, description="Seconds between auto-prune runs; 0 disables auto-prune")
    data: BaseModel = Field(..., description="Backend-specific configuration data")

    @model_validator(mode="before")
    @classmethod
    def validate_and_populate_data(cls, values: Any) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise ValueError(f"database config must be a dict, got {type(values).__name__}")
        database_type = values.get("type")
        if not database_type:
            raise ValueError("database.type is required")
        backend_registry = _BACKEND_REGISTRY
        config_data_class = backend_registry.get(database_type)
        if not config_data_class:
            raise ValueError(f"Unknown backend type: {database_type!r} (supported: {list(backend_registry.keys())})")
        data_dict = values.get("data")
        if data_dict is None:
            raise ValueError("database.data is required")
        values["data"] = config_data_class(**data_dict)
        return values

    def model_dump(self, **kwargs) -> dict[str, Any]:
        result = super().model_dump(**kwargs)
        if isinstance(self.data, BaseModel):
            result["data"] = self.data.model_dump(**kwargs)
        return result
