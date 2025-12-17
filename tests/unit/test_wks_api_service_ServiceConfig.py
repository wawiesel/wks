"""Unit tests for ServiceConfig serialization behavior."""

from typing import cast

from pydantic import BaseModel

from wks.api.service.ServiceConfig import ServiceConfig


def test_service_config_model_dump_serializes_data() -> None:
    # ServiceConfig's validate_and_populate_data validator converts dict to BaseModel
    # We use cast to tell mypy that the validator will handle the conversion
    data_dict = {
        "label": "com.test.wks",
        "keep_alive": True,
        "run_at_load": False,
    }
    cfg = ServiceConfig(
        type="darwin",
        data=cast(BaseModel, data_dict),  # Validator converts dict to BaseModel
    )
    dumped = cfg.model_dump(mode="python")
    assert dumped["type"] == "darwin"
    assert isinstance(dumped["data"], dict)
    assert dumped["data"]["label"] == "com.test.wks"
