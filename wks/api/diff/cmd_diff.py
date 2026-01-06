"""Diff command."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict
from typing import Any, cast

from wks.api.config.StageResult import StageResult

from .BinaryDiffOutput import BinaryDiffOutput
from .CodeDiffOutput import CodeDiffOutput
from .controller import DiffController
from .DiffMetadata import DiffMetadata
from .DiffResult import DiffResult
from .TextDiffOutput import TextDiffOutput


def cmd_diff(config: dict[str, Any], target_a: str, target_b: str) -> StageResult:
    """Compute a diff between two targets using an explicit config."""

    def build_failure(message: str, errors: list[str], engine_used: str) -> DiffResult:
        metadata = DiffMetadata(
            engine_used=engine_used,
            is_identical=False,
            file_type_a=None,
            file_type_b=None,
            checksum_a=None,
            checksum_b=None,
            encoding_a=None,
            encoding_b=None,
        )
        return DiffResult(
            status="failure",
            metadata=metadata,
            diff_output=None,
            message=message,
            error_details={"errors": errors},
        )

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Validating inputs")

        errors: list[str] = []
        engine_used = "unknown"

        if not isinstance(config, dict):
            errors.append(f"config must be a dict (found: {type(config).__name__})")

        if not target_a:
            errors.append("target_a is required and must be non-empty")
        if not target_b:
            errors.append("target_b is required and must be non-empty")

        engine_config: dict[str, Any] | None = None
        if isinstance(config, dict):
            engine_config = config.get("engine_config")
            if engine_config is None:
                errors.append("config.engine_config is required")
            elif not isinstance(engine_config, dict):
                errors.append(f"config.engine_config must be a dict (found: {type(engine_config).__name__})")

        engine: str | None = None
        if isinstance(engine_config, dict):
            engine = engine_config.get("engine")
            if not engine:
                errors.append("config.engine_config.engine is required")
            elif engine not in {"bsdiff4", "myers", "ast"}:
                errors.append(f"config.engine_config.engine must be one of bsdiff4,myers,ast (found: {engine!r})")
            else:
                engine_used = engine

        timeout_seconds: Any = None
        max_size_mb: Any = None
        if isinstance(config, dict):
            timeout_seconds = config.get("timeout_seconds", 60)
            max_size_mb = config.get("max_size_mb", 100)
        if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
            errors.append("config.timeout_seconds must be a positive int")
        if not isinstance(max_size_mb, int) or max_size_mb <= 0:
            errors.append("config.max_size_mb must be a positive int")

        if errors:
            yield (1.0, "Failed")
            failure = build_failure("Diff failed due to invalid inputs.", errors, engine_used)
            result_obj.result = failure.message or "Diff failed."
            result_obj.output = asdict(failure)
            result_obj.success = False
            return

        assert isinstance(engine_config, dict)
        assert engine is not None

        options: dict[str, Any] = {}
        if engine == "myers":
            context_lines = engine_config.get("context_lines", 3)
            ignore_whitespace = engine_config.get("ignore_whitespace", False)
            if not isinstance(context_lines, int) or context_lines < 0:
                errors.append("config.engine_config.context_lines must be a non-negative int")
            if not isinstance(ignore_whitespace, bool):
                errors.append("config.engine_config.ignore_whitespace must be a bool")
            options = {"context_lines": context_lines, "ignore_whitespace": ignore_whitespace}
        elif engine == "ast":
            language = engine_config.get("language")
            ignore_comments = engine_config.get("ignore_comments", True)
            if not language or not isinstance(language, str):
                errors.append("config.engine_config.language is required for ast engine")
            if not isinstance(ignore_comments, bool):
                errors.append("config.engine_config.ignore_comments must be a bool")
            options = {"language": language, "ignore_comments": ignore_comments}

        if errors:
            yield (1.0, "Failed")
            failure = build_failure("Diff failed due to invalid engine options.", errors, engine_used)
            result_obj.result = failure.message or "Diff failed."
            result_obj.output = asdict(failure)
            result_obj.success = False
            return

        controller = DiffController()

        yield (0.3, "Resolving targets")
        try:
            file_a = controller._resolve_target(target_a)
            file_b = controller._resolve_target(target_b)
        except Exception as exc:
            failure = build_failure(f"Diff failed: {exc}", [str(exc)], engine_used)
            yield (1.0, "Failed")
            result_obj.result = failure.message or "Diff failed."
            result_obj.output = asdict(failure)
            result_obj.success = False
            return

        if not file_a.exists():
            errors.append(f"target_a not found: {file_a}")
        if not file_b.exists():
            errors.append(f"target_b not found: {file_b}")

        if errors:
            failure = build_failure("Diff failed due to missing targets.", errors, engine_used)
            yield (1.0, "Failed")
            result_obj.result = failure.message or "Diff failed."
            result_obj.output = asdict(failure)
            result_obj.success = False
            return

        max_bytes = int(max_size_mb) * 1024 * 1024
        size_a = file_a.stat().st_size
        size_b = file_b.stat().st_size
        if size_a > max_bytes:
            errors.append(f"target_a exceeds max_size_mb ({size_a} bytes > {max_bytes} bytes)")
        if size_b > max_bytes:
            errors.append(f"target_b exceeds max_size_mb ({size_b} bytes > {max_bytes} bytes)")
        if errors:
            failure = build_failure("Diff failed due to size limits.", errors, engine_used)
            yield (1.0, "Failed")
            result_obj.result = failure.message or "Diff failed."
            result_obj.output = asdict(failure)
            result_obj.success = False
            return

        yield (0.6, "Computing diff")
        try:
            diff_text = controller.diff(target_a, target_b, engine_used, options)
        except Exception as exc:
            failure = build_failure(f"Diff failed: {exc}", [str(exc)], engine_used)
            yield (1.0, "Failed")
            result_obj.result = failure.message or "Diff failed."
            result_obj.output = asdict(failure)
            result_obj.success = False
            return

        is_identical = file_a.read_bytes() == file_b.read_bytes()
        metadata = DiffMetadata(
            engine_used=engine_used,
            is_identical=is_identical,
            file_type_a=file_a.suffix or None,
            file_type_b=file_b.suffix or None,
            checksum_a=None,
            checksum_b=None,
            encoding_a=None,
            encoding_b=None,
        )

        diff_output: TextDiffOutput | BinaryDiffOutput | CodeDiffOutput | None = None
        message = None
        if engine_used == "myers":
            diff_output = TextDiffOutput(unified_diff=diff_text, patch_format="unified")
        elif engine_used == "ast":
            if "no structural changes" in diff_text.lower():
                structured = []
            else:
                structured = [{"type": "ast_diff", "detail": diff_text}]
            diff_output = CodeDiffOutput(structured_changes=structured)
            message = diff_text
        else:
            diff_output = BinaryDiffOutput(patch_path=diff_text, patch_size_bytes=0)
            message = "Binary patch generated."

        result = DiffResult(
            status="success",
            metadata=metadata,
            diff_output=diff_output,
            message=message,
            error_details=None,
        )

        yield (1.0, "Complete")
        result_obj.result = "Diff completed."
        result_obj.output = cast(dict[str, Any], asdict(result))
        result_obj.success = True

    return StageResult(
        announce=f"Diffing {target_a} vs {target_b}...",
        progress_callback=do_work,
    )
