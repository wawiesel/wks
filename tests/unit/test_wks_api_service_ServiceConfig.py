"""Unit tests for ServiceConfig serialization behavior."""

import pytest

from wks.api.service.ServiceConfig import ServiceConfig

def test_service_config_model_dump_serializes_data() -> None:
    cfg = ServiceConfig(
        type="darwin",
        sync_interval_secs=60.0,
        data={
            "label": "com.test.wks",
            "keep_alive": True,
            "run_at_load": False,
        },
    )
    dumped = cfg.model_dump(mode="python")
    assert dumped["type"] == "darwin"
    assert dumped["sync_interval_secs"] == 60.0
    assert isinstance(dumped["data"], dict)
    assert dumped["data"]["label"] == "com.test.wks"
