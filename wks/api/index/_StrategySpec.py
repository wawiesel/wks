from typing import Literal

from pydantic import BaseModel


class _StrategySpec(BaseModel):
    indexes: list[str]
    merge: Literal["rrf"]
