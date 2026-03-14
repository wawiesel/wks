"""Index configuration for WKSConfig."""

from pydantic import BaseModel, model_validator

from ._IndexSpec import _IndexSpec
from ._StrategySpec import _StrategySpec


class IndexConfig(BaseModel):
    """Index section of WKS configuration."""

    default_index: str
    default_strategy: str | None = None
    strategies: dict[str, _StrategySpec] = {}
    indexes: dict[str, _IndexSpec]

    @model_validator(mode="after")
    def validate_strategies(self) -> "IndexConfig":
        """Validate that strategy index names exist and default_strategy is defined."""
        for name, strategy in self.strategies.items():
            for idx in strategy.indexes:
                if idx not in self.indexes:
                    raise ValueError(f"Strategy '{name}' references unknown index '{idx}'")
        if self.default_strategy is not None and self.default_strategy not in self.strategies:
            raise ValueError(
                f"default_strategy '{self.default_strategy}' not defined in strategies "
                f"(available: {list(self.strategies.keys())})"
            )
        return self
