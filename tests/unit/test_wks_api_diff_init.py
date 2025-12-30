"""Unit tests for wks.api.diff.__init__ module."""

from tests.unit.utils import verify_domain_init


def test_diff_init_exports():
    verify_domain_init("diff")
