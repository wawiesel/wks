"""Transform controller factory."""

from collections.abc import Iterator
from contextlib import contextmanager

from ...api.database.Database import Database
from ._TransformController import _TransformController


@contextmanager
def _get_controller() -> Iterator[_TransformController]:
    """Get transform controller with active database connection.

    Yields:
        TransformController instance
    """
    from ..config.WKSConfig import WKSConfig

    wks_config = WKSConfig.load()
    transform_config = wks_config.transform

    # We use the 'transform' collection/database name as per spec
    with Database(wks_config.database, "transform") as db:
        yield _TransformController(db, transform_config, wks_config.cat.default_engine)
