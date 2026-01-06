"""Direction enum for link queries."""

from enum import Enum


class Direction(str, Enum):
    TO = "to"
    FROM = "from"
    BOTH = "both"
