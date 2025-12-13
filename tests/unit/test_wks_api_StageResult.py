"""Unit tests for wks.api.StageResult module."""

from collections.abc import Iterator

from wks.api.StageResult import StageResult


def test_stage_result_initialization():
    """Test that StageResult initializes correctly."""

    def progress_gen(result: StageResult) -> Iterator[tuple[float, str]]:
        yield (1.0, "Complete")
        result.result = "Done"
        result.output = {"test": True}
        result.success = True

    result = StageResult(
        announce="Testing",
        progress_callback=progress_gen,
    )
    assert result.announce == "Testing"
    assert result.result == ""
    assert result.output == {}
    assert result.success is False
