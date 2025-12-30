"""Unit tests for wks.api.vault.__init__ module."""

from tests.unit.utils import verify_domain_init


def test_vault_init_exports():
    verify_domain_init("vault")
