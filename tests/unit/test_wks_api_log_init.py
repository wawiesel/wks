"""Unit tests for wks.api.log.__init__ module."""

from tests.unit.utils import verify_domain_init


def test_log_init_exports():
    verify_domain_init("log")
