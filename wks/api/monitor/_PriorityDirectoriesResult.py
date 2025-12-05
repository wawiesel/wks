"""Priority directories result model."""

from pydantic import BaseModel

from ._PriorityDirectoryInfo import _PriorityDirectoryInfo


class _PriorityDirectoriesResult(BaseModel):
    """Result of get_priority_directories()."""

    priority_directories: dict[str, float]
    count: int
    validation: dict[str, _PriorityDirectoryInfo]

