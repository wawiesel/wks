"""Log status command - show log file status after auto-pruning by retention."""

from collections.abc import Iterator
from contextlib import suppress
from datetime import datetime, timedelta, timezone

from ..config.WKSConfig import WKSConfig
from ..StageResult import StageResult
from . import LogStatusOutput
from .LOG_PATTERN import LOG_PATTERN


def cmd_status() -> StageResult:
    """Show log file status after auto-pruning expired entries by retention."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()
        log_cfg = config.log
        log_path = WKSConfig.get_logfile_path()

        yield (0.2, "Auto-pruning expired entries...")

        # Calculate cutoff times for each level
        now = datetime.now(timezone.utc)
        cutoffs = {
            "DEBUG": now - timedelta(days=log_cfg.debug_retention_days),
            "INFO": now - timedelta(days=log_cfg.info_retention_days),
            "WARN": now - timedelta(days=log_cfg.warning_retention_days),
            "ERROR": now - timedelta(days=log_cfg.error_retention_days),
        }

        counts = {"debug": 0, "info": 0, "warn": 0, "error": 0}
        kept_lines: list[str] = []
        oldest_entry: str | None = None
        newest_entry: str | None = None

        if not log_path.exists():
            result_obj.result = "Log file status"
            result_obj.output = LogStatusOutput(
                errors=[],
                warnings=[],
                log_path=str(log_path),
                size_bytes=0,
                entry_counts=counts,
                oldest_entry=None,
                newest_entry=None,
            ).model_dump(mode="python")
            result_obj.success = True
            yield (1.0, "Complete")
            return

        try:
            lines = log_path.read_text(errors="ignore").splitlines()
        except Exception as e:
            result_obj.result = f"Failed to read log: {e}"
            result_obj.output = LogStatusOutput(
                errors=[str(e)],
                warnings=[],
                log_path=str(log_path),
                size_bytes=0,
                entry_counts=counts,
                oldest_entry=None,
                newest_entry=None,
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
                timestamp_str = match.group(1)
                level = match.group(3).upper()

                try:
                    entry_time = datetime.fromisoformat(timestamp_str)
                except ValueError:
                    entry_time = now  # Treat unparseable as current

                # Check if entry is expired
                cutoff = cutoffs.get(level, now)
                if entry_time < cutoff:
                    # Entry expired, don't keep it
                    continue

                # Keep the entry and count it
                kept_lines.append(stripped)
                level_key = level.lower()
                if level_key in counts:
                    counts[level_key] += 1

                # Track oldest/newest
                ts = entry_time.isoformat()
                if oldest_entry is None or ts < oldest_entry:
                    oldest_entry = ts
                if newest_entry is None or ts > newest_entry:
                    newest_entry = ts
            else:
                # Legacy format - keep it but count by level keyword
                kept_lines.append(stripped)
                upper = stripped.upper()
                if "DEBUG" in upper:
                    counts["debug"] += 1
                elif "INFO" in upper:
                    counts["info"] += 1
                elif "WARN" in upper:
                    counts["warn"] += 1
                elif "ERROR" in upper:
                    counts["error"] += 1

        yield (0.8, "Writing cleaned log...")

        # Write back only non-expired entries
        with suppress(Exception):
            log_path.write_text("\n".join(kept_lines) + "\n" if kept_lines else "", encoding="utf-8")

        size_bytes = log_path.stat().st_size if log_path.exists() else 0

        result_obj.result = "Log file status"
        result_obj.output = LogStatusOutput(
            errors=[],
            warnings=[],
            log_path=str(log_path),
            size_bytes=size_bytes,
            entry_counts=counts,
            oldest_entry=oldest_entry,
            newest_entry=newest_entry,
        ).model_dump(mode="python")
        result_obj.success = True
        yield (1.0, "Complete")

    return StageResult(
        announce="Checking log status...",
        progress_callback=do_work,
    )
