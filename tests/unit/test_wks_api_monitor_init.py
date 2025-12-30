"""Unit tests for wks.api.monitor.__init__ module."""

from tests.unit.utils import verify_domain_init


def test_monitor_init_exports():
    verify_domain_init("monitor")
