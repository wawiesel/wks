"""Unit tests for wks.api.daemon.__init__ module."""

from tests.unit.utils import verify_domain_init


def test_daemon_init_exports():
    verify_domain_init("daemon")
