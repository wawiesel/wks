from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import ConfigDict, Field

from ._models import ServiceResponse

StatusProvider = Callable[[], Any]


class StatusResponse(ServiceResponse):
    model_config = ConfigDict(extra="forbid")

    sections: dict[str, dict[str, Any]] = Field(default_factory=dict)


def collect_status(*, providers: dict[str, StatusProvider] | None = None) -> StatusResponse:
    resolved_providers = providers or _default_providers()
    sections = {name: _run_status_provider(provider) for name, provider in resolved_providers.items()}
    return StatusResponse(success=True, message="System status", sections=sections)


def _run_status_provider(provider: StatusProvider) -> dict[str, Any]:
    try:
        stage = provider()
        list(stage.progress_callback(stage))
        return stage.output
    except Exception as exc:
        return {"error": str(exc)}


def _default_providers() -> dict[str, StatusProvider]:
    import wks.api.link.cmd_status as link_mod
    import wks.api.log.cmd_status as log_mod
    import wks.api.monitor.cmd_status as monitor_mod
    import wks.api.service.cmd_status as service_mod
    import wks.api.vault.cmd_status as vault_mod

    return {
        "service": service_mod.cmd_status,
        "log": log_mod.cmd_status,
        "monitor": monitor_mod.cmd_status,
        "link": link_mod.cmd_status,
        "vault": vault_mod.cmd_status,
    }
