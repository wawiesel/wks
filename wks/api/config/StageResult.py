from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import TypeAlias

StyledSegment: TypeAlias = tuple[str, str | None]


@dataclass
class StageResult:
    announce: str
    progress_callback: Callable[["StageResult"], Iterator[tuple[float, str]]]
    result: str = ""
    output: dict = field(default_factory=dict)
    success: bool = False
    announce_segments: tuple[StyledSegment, ...] = ()
