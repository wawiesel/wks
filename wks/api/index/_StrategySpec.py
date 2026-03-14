"""Search strategy specification."""

from typing import Literal

from pydantic import BaseModel


class _StrategySpec(BaseModel):
    """Configuration for a named search strategy."""

    indexes: list[str]
    merge: Literal["rrf"]
