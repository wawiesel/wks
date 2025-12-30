"""Unit tests for wks.api.cat.__init__ module."""

from tests.unit.utils import verify_domain_init


def test_cat_init_exports():
    verify_domain_init("cat")
