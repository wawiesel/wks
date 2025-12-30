"""Unit tests for wks.api.link.__init__ module."""

from tests.unit.utils import verify_domain_init


def test_link_init_exports():
    verify_domain_init("link")
