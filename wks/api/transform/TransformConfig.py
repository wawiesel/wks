from pydantic import BaseModel, ValidationError, field_validator, model_validator

from ._CacheConfig import _CacheConfig
from ._EngineConfig import _EngineConfig
from ._RouteEngineConfig import _RouteEngineConfig

TransformEngineConfig = _EngineConfig | _RouteEngineConfig


class TransformConfig(BaseModel):
    cache: _CacheConfig
    default_engine: str
    engines: dict[str, TransformEngineConfig]

    @field_validator("engines", mode="before")
    @classmethod
    def parse_engines(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value

        parsed: dict[str, TransformEngineConfig] = {}
        for name, raw in value.items():
            if isinstance(raw, (_EngineConfig, _RouteEngineConfig)):
                parsed[name] = raw
                continue
            if not isinstance(raw, dict):
                parsed[name] = _EngineConfig.model_validate(raw)
                continue

            try:
                if raw.get("type") == "route":
                    parsed[name] = _RouteEngineConfig.model_validate(raw)
                else:
                    parsed[name] = _EngineConfig.model_validate(raw)
            except ValidationError as exc:
                raise ValueError(f"transform.engines.{name}: {exc}") from exc

        return parsed

    @model_validator(mode="after")
    def validate_engine_graph(self) -> "TransformConfig":
        if self.default_engine not in self.engines:
            raise ValueError(
                f"transform.default_engine '{self.default_engine}' must reference a configured engine "
                f"(available: {list(self.engines.keys())})"
            )

        for engine_name, engine_config in self.engines.items():
            if not isinstance(engine_config, _RouteEngineConfig):
                continue

            for target_name in engine_config.data.order:
                if target_name not in self.engines:
                    raise ValueError(
                        f"transform.engines.{engine_name}.data.order references unknown engine "
                        f"'{target_name}' (available: {list(self.engines.keys())})"
                    )
                if target_name == engine_name:
                    raise ValueError(f"transform.engines.{engine_name}.data.order cannot reference itself")
                target_config = self.engines[target_name]
                if isinstance(target_config, _RouteEngineConfig):
                    raise ValueError(
                        f"transform.engines.{engine_name}.data.order cannot reference route engine '{target_name}'"
                    )
                if target_config.type == "null":
                    raise ValueError(
                        f"transform.engines.{engine_name}.data.order cannot reference null engine "
                        f"'{target_name}'; use reject_binary instead"
                    )
        return self
