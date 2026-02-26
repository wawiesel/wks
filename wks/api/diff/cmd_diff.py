"""Diff command."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
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
            elif engine not in {"auto", "bsdiff3", "myers", "sexp", "semantic"}:
                errors.append(
                    f"config.engine_config.engine must be one of auto,bsdiff3,myers,sexp,semantic (found: {engine!r})"
                )
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
        elif engine == "semantic":
            required_keys = [
                "modified_threshold",
                "unchanged_threshold",
                "text_model",
                "image_model",
                "pixel_threshold",
                "max_examples",
            ]
            missing_keys = [key for key in required_keys if key not in engine_config]
            if missing_keys:
                errors.append(
                    "config.engine_config missing required semantic options: " + ",".join(sorted(missing_keys))
                )
            else:
                modified_threshold = engine_config["modified_threshold"]
                unchanged_threshold = engine_config["unchanged_threshold"]
                text_model = engine_config["text_model"]
                image_model = engine_config["image_model"]
                pixel_threshold = engine_config["pixel_threshold"]
                max_examples = engine_config["max_examples"]
                if not isinstance(modified_threshold, (int, float)) or not (0.0 <= float(modified_threshold) <= 1.0):
                    errors.append("config.engine_config.modified_threshold must be in [0,1]")
                if not isinstance(unchanged_threshold, (int, float)) or not (0.0 <= float(unchanged_threshold) <= 1.0):
                    errors.append("config.engine_config.unchanged_threshold must be in [0,1]")
                if (
                    isinstance(modified_threshold, (int, float))
                    and isinstance(unchanged_threshold, (int, float))
                    and float(modified_threshold) > float(unchanged_threshold)
                ):
                    errors.append("config.engine_config.modified_threshold must be <= unchanged_threshold")
                if not isinstance(text_model, str) or not text_model.strip():
                    errors.append("config.engine_config.text_model must be a non-empty string")
                if not isinstance(image_model, str) or not image_model.strip():
                    errors.append("config.engine_config.image_model must be a non-empty string")
                if not isinstance(pixel_threshold, int) or pixel_threshold < 0:
                    errors.append("config.engine_config.pixel_threshold must be a non-negative int")
                if not isinstance(max_examples, int) or max_examples <= 0:
                    errors.append("config.engine_config.max_examples must be a positive int")
                options = {
                    "modified_threshold": float(modified_threshold),
                    "unchanged_threshold": float(unchanged_threshold),
                    "text_model": text_model,
                    "image_model": image_model,
                    "pixel_threshold": pixel_threshold,
                    "max_examples": max_examples,
                }
        # Note: "auto" mode will be handled after resolving targets

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

        # Handle auto mode - select engine based on file types
        if engine_used == "auto":
            from ._auto_engine import select_auto_diff_engine

            auto_engine = select_auto_diff_engine(file_a, file_b)
            engine_used = auto_engine

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
        diff_extension = None  # Extension for registering in transform cache

        if engine_used == "myers":
            diff_output = TextDiffOutput(unified_diff=diff_text, patch_format="unified")
            diff_extension = "txt"
            message = "Text diff generated."
        elif engine_used == "sexp":
            if "no structural changes" in diff_text.lower():
                structured = []
            else:
                structured = [{"type": "sexp_diff", "detail": diff_text}]
            diff_output = CodeDiffOutput(structured_changes=structured)
            diff_extension = "sexp"
            message = diff_text
        elif engine_used == "bsdiff3":
            # For bsdiff3, extract patch size from the diff_text if available
            patch_size = 0
            if "Patch size:" in diff_text:
                try:
                    # Extract patch size from the summary text
                    for line in diff_text.split("\n"):
                        if "Patch size:" in line:
                            parts = line.split(":")
                            if len(parts) > 1:
                                size_str = parts[1].strip().split()[0]  # Get number before "bytes"
                                patch_size = int(size_str)
                                break
                except (ValueError, IndexError):
                    pass
            diff_output = BinaryDiffOutput(patch_path=diff_text, patch_size_bytes=patch_size)
            diff_extension = "bin"
            message = "Binary patch generated."
        elif engine_used == "semantic":
            import json

            semantic_payload = json.loads(diff_text)
            diff_output = CodeDiffOutput(structured_changes=[semantic_payload])
            diff_extension = "json"
            message = "Semantic diff generated."
        else:
            # Fallback
            diff_output = BinaryDiffOutput(patch_path=diff_text, patch_size_bytes=0)
            diff_extension = "bin"
            message = "Diff generated."

        # Register diff result in transform cache
        diff_checksum = None
        if diff_extension:
            yield (0.9, "Registering diff in transform cache")
            try:
                import hashlib

                from wks.api.config.now_iso import now_iso
                from wks.api.config.URI import URI
                from wks.api.config.WKSConfig import WKSConfig
                from wks.api.database.Database import Database
                from wks.api.transform._CacheManager import _CacheManager
                from wks.api.transform._TransformRecord import _TransformRecord

                # Compute checksum of diff content
                diff_content = diff_text.encode("utf-8") if isinstance(diff_text, str) else diff_text
                sha256 = hashlib.sha256(diff_content)
                diff_checksum = sha256.hexdigest()

                # Get transform cache directory
                wks_config = WKSConfig.load()
                cache_dir = Path(wks_config.transform.cache.base_dir)
                cache_file = cache_dir / f"{diff_checksum}.{diff_extension}"

                # Write diff to cache
                cache_dir.mkdir(parents=True, exist_ok=True)
                if isinstance(diff_text, str):
                    cache_file.write_text(diff_text, encoding="utf-8")
                else:
                    cache_file.write_bytes(diff_text)

                # Register in database
                with Database(wks_config.database, "transform") as db:
                    record = _TransformRecord(
                        file_uri=URI.from_path(file_a),  # Use file_a as the "source"
                        cache_uri=URI.from_path(cache_file),
                        checksum=diff_checksum,
                        size_bytes=cache_file.stat().st_size,
                        last_accessed=now_iso(),
                        created_at=now_iso(),
                        engine=f"diff_{engine_used}",
                        options_hash="",  # No options hash for diff results
                        referenced_uris=[],
                    )
                    db.insert_one(record.to_dict())

                    # Update cache size
                    cache_manager = _CacheManager(cache_dir, wks_config.transform.cache.max_size_bytes, db)
                    cache_manager.add_file(cache_file.stat().st_size)

            except Exception as exc:
                # Log but don't fail the diff operation
                yield (0.95, f"Warning: Failed to register diff in cache: {exc}")

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
