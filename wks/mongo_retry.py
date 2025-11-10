"""Retry logic for MongoDB operations."""

import logging
import time
from functools import wraps
from typing import Any, Callable, TypeVar, Optional

import pymongo.errors

logger = logging.getLogger(__name__)

T = TypeVar('T')


def mongo_retry(
    max_attempts: int = 3,
    delay_secs: float = 0.5,
    backoff_multiplier: float = 2.0,
    exceptions: tuple = (pymongo.errors.ConnectionFailure, pymongo.errors.ServerSelectionTimeoutError)
):
    """
    Decorator to retry MongoDB operations on transient failures.

    Args:
        max_attempts: Maximum number of retry attempts
        delay_secs: Initial delay between retries in seconds
        backoff_multiplier: Multiplier for exponential backoff
        exceptions: Tuple of exception types to retry on

    Example:
        @mongo_retry(max_attempts=3, delay_secs=0.5)
        def get_document(collection, doc_id):
            return collection.find_one({"_id": doc_id})
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            attempt = 0
            current_delay = delay_secs

            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(
                            f"MongoDB operation failed after {max_attempts} attempts: {func.__name__}",
                            exc_info=True,
                            extra={"operation": func.__name__, "attempts": attempt}
                        )
                        raise

                    logger.warning(
                        f"MongoDB operation failed (attempt {attempt}/{max_attempts}): {func.__name__}. "
                        f"Retrying in {current_delay}s...",
                        extra={"operation": func.__name__, "attempt": attempt, "delay": current_delay}
                    )

                    time.sleep(current_delay)
                    current_delay *= backoff_multiplier

            # Should never reach here, but for type safety
            raise RuntimeError(f"Unexpected exit from retry loop: {func.__name__}")

        return wrapper
    return decorator


class MongoRetryWrapper:
    """
    Wrapper class that adds retry logic to MongoDB collection methods.

    Example:
        collection = db["my_collection"]
        safe_collection = MongoRetryWrapper(collection)
        doc = safe_collection.find_one({"_id": "123"})  # Automatically retries on failure
    """

    def __init__(self, collection, max_attempts: int = 3, delay_secs: float = 0.5):
        """
        Args:
            collection: PyMongo collection object
            max_attempts: Maximum retry attempts for operations
            delay_secs: Initial delay between retries
        """
        self._collection = collection
        self._max_attempts = max_attempts
        self._delay_secs = delay_secs

    def __getattr__(self, name: str) -> Any:
        """
        Wrap collection methods with retry logic.

        Read operations (find_one, find, count_documents) get retry logic.
        Write operations (insert_one, update_one, etc.) pass through without retry
        to avoid duplicate writes on transient failures.
        """
        attr = getattr(self._collection, name)

        if not callable(attr):
            return attr

        # Only retry read operations
        read_ops = {
            "find_one", "find", "count_documents", "estimated_document_count",
            "distinct", "aggregate", "find_one_and_update", "find_one_and_replace",
            "find_one_and_delete"
        }

        if name in read_ops:
            return mongo_retry(max_attempts=self._max_attempts, delay_secs=self._delay_secs)(attr)

        return attr

    @property
    def name(self) -> str:
        """Pass through collection name."""
        return self._collection.name

    def __repr__(self) -> str:
        return f"MongoRetryWrapper({self._collection!r}, max_attempts={self._max_attempts})"
