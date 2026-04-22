"""Unit tests for wks.api.log.summarize_status_log_messages."""

from wks.api.log.summarize_status_log_messages import (
    STATUS_LOG_MESSAGE_LIMIT,
    summarize_status_log_messages,
)


def test_summarize_status_log_messages_keeps_small_lists():
    warnings = ["warn-1", "warn-2"]
    errors = ["error-1"]

    summarized_warnings, summarized_errors = summarize_status_log_messages(warnings, errors)

    assert summarized_warnings == warnings
    assert summarized_errors == errors


def test_summarize_status_log_messages_truncates_to_recent_entries():
    warnings = [f"warn-{idx}" for idx in range(STATUS_LOG_MESSAGE_LIMIT + 3)]
    errors = [f"error-{idx}" for idx in range(STATUS_LOG_MESSAGE_LIMIT + 2)]

    summarized_warnings, summarized_errors = summarize_status_log_messages(warnings, errors)

    assert len(summarized_warnings) == STATUS_LOG_MESSAGE_LIMIT + 1
    assert len(summarized_errors) == STATUS_LOG_MESSAGE_LIMIT + 1
    assert (
        summarized_warnings[0] == "Status output truncated: showing 20 most recent warnings out of 23 total. "
        "Use 'wksc log status' and the logfile for full history."
    )
    assert (
        summarized_errors[0] == "Status output truncated: showing 20 most recent errors out of 22 total. "
        "Use 'wksc log status' and the logfile for full history."
    )
    assert summarized_warnings[1:] == warnings[-STATUS_LOG_MESSAGE_LIMIT:]
    assert summarized_errors[1:] == errors[-STATUS_LOG_MESSAGE_LIMIT:]
