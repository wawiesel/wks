"""Unit tests for wks.api.service.__init__ module."""

from tests.unit.utils import verify_domain_init


def test_service_init_exports():
    verify_domain_init("service")
