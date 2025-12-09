"""Mock MongoDB-specific configuration data for testing."""

from pydantic import BaseModel


class _Data(BaseModel):
    """MongoMock configuration data.

    Note: MongoMock doesn't require a URI since it's an in-memory database.
    The implementation creates a shared client without connection parameters.
    """
    pass

