"""Unit tests for wks.api.config.__init__ module."""

from tests.unit.utils import verify_domain_init


def test_config_init_exports():
    verify_domain_init("config")
