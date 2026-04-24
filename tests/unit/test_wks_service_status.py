"""Unit tests for the shared status aggregation service."""

from collections.abc import Iterator

from wks.api.config.StageResult import StageResult
from wks.services.status import collect_status


def _provider(output: dict):
    def _run() -> StageResult:
        def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
            result_obj.output = output
            result_obj.result = "ok"
            result_obj.success = True
            yield (1.0, "done")

        return StageResult(announce="status", progress_callback=do_work)

    return _run


def test_collect_status_aggregates_sections():
    """The status service should aggregate provider outputs under one response."""
    response = collect_status(
        providers={
            "service": _provider({"running": True}),
            "log": _provider({"errors": 0}),
        }
    )

    assert response.success is True
    assert response.sections["service"]["running"] is True
    assert response.sections["log"]["errors"] == 0


def test_collect_status_captures_provider_errors():
    """The status service should preserve provider failures per section."""

    def failing_provider():
        raise RuntimeError("boom")

    response = collect_status(providers={"service": failing_provider})

    assert response.success is True
    assert response.sections["service"]["error"] == "boom"
