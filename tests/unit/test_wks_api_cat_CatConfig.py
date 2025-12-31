"""Unit tests for wks.api.cat.CatConfig module."""

import pytest
from pydantic import ValidationError

from wks.api.cat.CatConfig import CatConfig


def test_cat_config_valid():
    cfg = CatConfig(default_engine="dx")
    assert cfg.default_engine == "dx"
    assert cfg.mime_engines is None


def test_cat_config_full():
    cfg = CatConfig(default_engine="dx", mime_engines={"text/plain": "plain"})
    assert cfg.default_engine == "dx"
    assert cfg.mime_engines == {"text/plain": "plain"}


def test_cat_config_required():
    with pytest.raises(ValidationError):
        CatConfig.model_validate({})
