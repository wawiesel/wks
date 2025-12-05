"""Priority directories result model."""

from pydantic import BaseModel

from ._ManagedDirectoryInfo import _ManagedDirectoryInfo


class _PriorityDirectoriesResult(BaseModel):
    """Result of get_priority_directories()."""

    priority_directories: dict[str, float]
    count: int
    validation: dict[str, _ManagedDirectoryInfo]
