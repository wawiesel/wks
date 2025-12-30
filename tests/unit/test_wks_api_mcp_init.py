"""Unit tests for wks.api.mcp.__init__ module."""

from tests.unit.utils import verify_domain_init


def test_mcp_init_exports():
    verify_domain_init("mcp")
