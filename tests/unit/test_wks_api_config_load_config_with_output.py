"""Unit tests for wks.api.config.load_config_with_output.load_config_with_output."""

import pytest

from wks.api.config import ConfigShowOutput
from wks.api.config.load_config_with_output import load_config_with_output
from wks.api.config.WKSConfig import WKSConfig

pytestmark = pytest.mark.config


def test_load_config_with_output_returns_error_output_when_config_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    config, output = load_config_with_output("monitor", ConfigShowOutput)
    assert config is None
    assert isinstance(output, dict)

    assert output["section"] == "monitor"
    assert isinstance(output["errors"], list)
    assert len(output["errors"]) >= 1
    assert output["warnings"] == []
    assert output["content"] == {}

    # Ensure config_path is present and is the actual config.json path string.
    assert output["config_path"] == str(WKSConfig.get_config_path())
    assert "None" not in output["config_path"]
