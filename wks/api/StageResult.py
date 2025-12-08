"""StageResult dataclass for 4-stage command pattern."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field


@dataclass
class StageResult:
    """Result from a command function following the 4-stage pattern.

    ALL fields are required. No exceptions.
    """

    announce: str
    progress_callback: Callable[["StageResult"], Iterator[tuple[float, str]]]
    result: str = ""
    output: dict = field(default_factory=dict)
    success: bool = False

