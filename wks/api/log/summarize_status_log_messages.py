"""Summarize warning/error lists for status-style outputs."""

STATUS_LOG_MESSAGE_LIMIT = 20


def _summarize_status_messages(messages: list[str], *, label: str, limit: int) -> list[str]:
    if limit <= 0:
        raise ValueError(f"Status log message limit must be positive, got {limit}")
    if len(messages) <= limit:
        return messages
    total = len(messages)
    recent = messages[-limit:]
    summary = (
        f"Status output truncated: showing {limit} most recent {label} out of {total} total. "
        "Use 'wksc log status' and the logfile for full history."
    )
    return [summary, *recent]


def summarize_status_log_messages(
    warnings: list[str],
    errors: list[str],
    *,
    limit: int = STATUS_LOG_MESSAGE_LIMIT,
) -> tuple[list[str], list[str]]:
    """Return bounded warning/error lists for status commands and daemon.json."""
    return (
        _summarize_status_messages(warnings, label="warnings", limit=limit),
        _summarize_status_messages(errors, label="errors", limit=limit),
    )
