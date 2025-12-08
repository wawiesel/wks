"""Database configuration with Pydantic validation."""

from typing import Any

from pydantic import BaseModel, Field, model_validator

from ._mongo._DbConfigData import _DbConfigData as _MongoDbConfigData
from ._mongomock._DbConfigData import _DbConfigData as _MongoMockDbConfigData

# Registry: add new backends here (ONLY place backend types are enumerated)
_BACKEND_REGISTRY: dict[str, type[BaseModel]] = {
    "mongo": _MongoDbConfigData,
    "mongomock": _MongoMockDbConfigData,
}


class DatabaseConfig(BaseModel):
    _BACKEND_REGISTRY: dict[str, type[BaseModel]] = _BACKEND_REGISTRY

    type: str = Field(..., description="Database backend type")
    prefix: str = Field(..., description="Database prefix for collection names")
    data: BaseModel = Field(..., description="Backend-specific configuration data")

    @model_validator(mode="before")
    @classmethod
    def validate_and_populate_data(cls, values: Any) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise ValueError(f"database config must be a dict, got {type(values).__name__}")
        db_type = values.get("type")
        if not db_type:
            raise ValueError("database.type is required")
        # Access module-level registry (single source of truth)
        backend_registry = _BACKEND_REGISTRY
        config_data_class = backend_registry.get(db_type)
        if not config_data_class:
            raise ValueError(f"Unknown backend type: {db_type!r} (supported: {list(backend_registry.keys())})")
        data_dict = values.get("data")
        if data_dict is None:
            raise ValueError("database.data is required")
        # Allow empty dict - backend config classes can have defaults
        values["data"] = config_data_class(**data_dict)
        return values

    def get_uri(self) -> str:
        """Get database connection URI from backend-specific config data.

        Returns:
            Connection URI string

        Raises:
            AttributeError: If the backend doesn't have a uri attribute
        """
        from ._mongo._DbConfigData import _DbConfigData as _MongoDbConfigData

        if isinstance(self.data, _MongoDbConfigData):
            return self.data.uri
        raise AttributeError(f"Backend type '{self.type}' does not have a uri attribute")

