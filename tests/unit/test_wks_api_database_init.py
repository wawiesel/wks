"""Unit tests for wks.api.database.__init__ module."""

from tests.unit.utils import verify_domain_init


def test_database_init_exports():
    verify_domain_init("database")
