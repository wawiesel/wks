"""Unit tests for wks.api.transform.__init__ module."""

from tests.unit.utils import verify_domain_init


def test_transform_init_exports():
    verify_domain_init("transform")
