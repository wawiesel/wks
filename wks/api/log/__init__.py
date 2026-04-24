"""Log module - centralized logging."""

from wks.api.config.output_models import output_model

LogPruneOutput = output_model(
    "LogPruneOutput",
    "pruned_debug",
    "pruned_info",
    "pruned_warnings",
    "pruned_errors",
    "message",
)
LogStatusOutput = output_model(
    "LogStatusOutput", "log_path", "size_bytes", "entry_counts", "oldest_entry", "newest_entry"
)

__all__ = [
    "LogPruneOutput",
    "LogStatusOutput",
]
