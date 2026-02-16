"""Top-level status command - aggregates status from all subsystems."""

from collections.abc import Iterator
from typing import Any

from .config.StageResult import StageResult


def _run_sub_status(cmd_fn: Any) -> dict[str, Any]:
    """Run a sub-status command and return its output, or an error dict."""
    try:
        stage = cmd_fn()
        for _ in stage.progress_callback(stage):
            pass
        return stage.output
    except Exception as e:
        return {"error": str(e)}


def cmd_status() -> StageResult:
    """Get aggregated status from all subsystems."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        import wks.api.link.cmd_status as link_mod
        import wks.api.log.cmd_status as log_mod
        import wks.api.monitor.cmd_status as mon_mod
        import wks.api.service.cmd_status as svc_mod
        import wks.api.vault.cmd_status as vault_mod

        sections: dict[str, Any] = {}

        yield (0.1, "Checking service status...")
        sections["service"] = _run_sub_status(svc_mod.cmd_status)

        yield (0.3, "Checking log status...")
        sections["log"] = _run_sub_status(log_mod.cmd_status)

        yield (0.5, "Checking monitor status...")
        sections["monitor"] = _run_sub_status(mon_mod.cmd_status)

        yield (0.7, "Checking link status...")
        sections["link"] = _run_sub_status(link_mod.cmd_status)

        yield (0.9, "Checking vault status...")
        sections["vault"] = _run_sub_status(vault_mod.cmd_status)

        yield (1.0, "Complete")
        result_obj.output = sections
        result_obj.result = "System status"
        result_obj.success = True

    return StageResult(
        announce="Checking system status...",
        progress_callback=do_work,
    )
