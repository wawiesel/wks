"""Log prune command - remove log entries by level."""


from collections.abc import Iterator

from ..config.WKSConfig import WKSConfig
from ..StageResult import StageResult
from . import LogPruneOutput

from ._utils import LOG_PATTERN


def cmd_prune(
    prune_info: bool = True,
    prune_warnings: bool = False,
    prune_errors: bool = False,
    prune_debug: bool = True,
) -> StageResult:
    """Remove log entries by level.

    Args:
        prune_info: Remove INFO entries (default: True)
        prune_warnings: Remove WARN entries (default: False)
        prune_errors: Remove ERROR entries (default: False)
        prune_debug: Remove DEBUG entries (default: False)
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Loading configuration...")
        log_path = WKSConfig.get_logfile_path()

        pruned_debug = 0
        pruned_info = 0
        pruned_warnings = 0
        pruned_errors = 0
        kept_lines: list[str] = []

        yield (0.3, "Reading log file...")

        if not log_path.exists():
            result_obj.result = "No log file found"
            result_obj.output = LogPruneOutput(
                errors=[],
                warnings=[],
                pruned_debug=0,
                pruned_info=0,
                pruned_warnings=0,
                pruned_errors=0,
                message="No log file found",
            ).model_dump(mode="python")
            result_obj.success = True
            yield (1.0, "Complete")
            return

        try:
            lines = log_path.read_text(errors="ignore").splitlines()
        except Exception as e:
            result_obj.result = f"Failed to read log: {e}"
            result_obj.output = LogPruneOutput(
                errors=[str(e)],
                warnings=[],
                pruned_debug=0,
                pruned_info=0,
                pruned_warnings=0,
                pruned_errors=0,
                message=f"Failed to read log: {e}",
            ).model_dump(mode="python")
            result_obj.success = False
            yield (1.0, "Complete")
            return

        yield (0.5, f"Processing {len(lines)} entries...")

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            match = LOG_PATTERN.match(stripped)
            if match:
                level = match.group(3).upper()

                should_prune = False
                if level == "DEBUG" and prune_debug:
                    should_prune = True
                    pruned_debug += 1
                elif level == "INFO" and prune_info:
                    should_prune = True
                    pruned_info += 1
                elif level == "WARN" and prune_warnings:
                    should_prune = True
                    pruned_warnings += 1
                elif level == "ERROR" and prune_errors:
                    should_prune = True
                    pruned_errors += 1

                if not should_prune:
                    kept_lines.append(stripped)
            else:
                # Keep lines that don't match new format (legacy)
                upper = stripped.upper()
                should_prune = False
                if "DEBUG" in upper and prune_debug:
                    should_prune = True
                    pruned_debug += 1
                elif "INFO" in upper and prune_info:
                    should_prune = True
                    pruned_info += 1
                elif "WARN" in upper and prune_warnings:
                    should_prune = True
                    pruned_warnings += 1
                elif "ERROR" in upper and prune_errors:
                    should_prune = True
                    pruned_errors += 1

                if not should_prune:
                    kept_lines.append(stripped)

        yield (0.7, "Writing cleaned log...")

        try:
            log_path.write_text("\n".join(kept_lines) + "\n" if kept_lines else "", encoding="utf-8")
        except Exception as e:
            result_obj.result = f"Failed to write log: {e}"
            result_obj.output = LogPruneOutput(
                errors=[str(e)],
                warnings=[],
                pruned_debug=0,
                pruned_info=0,
                pruned_warnings=0,
                pruned_errors=0,
                message=f"Failed to write log: {e}",
            ).model_dump(mode="python")
            result_obj.success = False
            yield (1.0, "Complete")
            return

        total = pruned_debug + pruned_info + pruned_warnings + pruned_errors
        message = f"Pruned {total} log entries"

        result_obj.result = message
        result_obj.output = LogPruneOutput(
            errors=[],
            warnings=[],
            pruned_debug=pruned_debug,
            pruned_info=pruned_info,
            pruned_warnings=pruned_warnings,
            pruned_errors=pruned_errors,
            message=message,
        ).model_dump(mode="python")
        result_obj.success = True
        yield (1.0, "Complete")

    return StageResult(
        announce="Pruning log entries...",
        progress_callback=do_work,
    )
