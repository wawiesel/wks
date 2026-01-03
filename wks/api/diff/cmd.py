"""Diff command."""

from typing import Any

from ...api.StageResult import StageResult


def cmd(
    target1: str,
    target2: str,
    engine: str | None = None,
) -> StageResult:
    """Compute diff between two targets.

    Args:
        target1: First target (path or checksum)
        target2: Second target (path or checksum)
        engine: Optional engine override

    Returns:
        StageResult with diff in 'content' field
    """

    def do_work(result_obj: StageResult) -> Any:
        from ..config.WKSConfig import WKSConfig
        from ..transform._get_controller import _get_controller
        from .controller import DiffController

        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()

        # Determine engine
        engine_to_use = engine
        if not engine_to_use:
            engine_to_use = config.diff.router.fallback

        # Access transform controller for context
        with _get_controller() as tr_controller:
            diff_controller = DiffController(config.diff, transform_controller=tr_controller)

            yield (0.3, f"Computing diff using {engine_to_use}...")
            try:
                diff_output = diff_controller.diff(target1, target2, engine_to_use)

                output = {"content": diff_output, "engine": engine_to_use, "target1": target1, "target2": target2}

                result_obj.output = output
                result_obj.result = f"Diff computed using {engine_to_use}"
                result_obj.success = True
                yield (1.0, "Complete")

            except Exception as e:
                result_obj.success = False
                result_obj.result = str(e)
                yield (1.0, "Failed")

    return StageResult(announce=f"Diffing {target1} vs {target2}...", progress_callback=do_work)
