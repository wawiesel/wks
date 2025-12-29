"""Transform controller factory."""

from collections.abc import Iterator
from contextlib import contextmanager

from ...api.database.Database import Database
from ..config.WKSConfig import WKSConfig
from ._TransformConfig import _TransformConfig
from ._TransformController import _TransformController


@contextmanager
def _get_controller() -> Iterator[_TransformController]:
    """Get transform controller with active database connection.

    Yields:
        TransformController instance
    """
    wks_config = WKSConfig.load()
    transform_config = _TransformConfig.from_config_dict(wks_config.model_dump())

    # We use the 'transform' collection/database name as per spec
    with Database(wks_config.database, "transform") as db:
        # Cast to Any to satisfy Mypy as _TransformController expects a raw pymongo Database
        yield _TransformController(db.get_database(), transform_config)
