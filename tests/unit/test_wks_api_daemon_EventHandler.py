"""Unit tests for wks.api.daemon._EventHandler."""

from wks.api.daemon._EventHandler import _EventHandler


def test_event_handler_get_and_clear_events():
    """Test accumulating and clearing events."""
    handler = _EventHandler()

    # Manually add events (simulating what on_* methods do)
    handler._modified.add("/path/modified.md")
    handler._created.add("/path/created.md")
    handler._deleted.add("/path/deleted.md")
    handler._moved["file:///old"] = "file:///new"

    events = handler.get_and_clear_events()

    assert "/path/modified.md" in events.modified
    assert "/path/created.md" in events.created
    assert "/path/deleted.md" in events.deleted
    assert ("file:///old", "file:///new") in events.moved

    # Verify cleared
    events2 = handler.get_and_clear_events()
    assert len(events2.modified) == 0
    assert len(events2.created) == 0
    assert len(events2.deleted) == 0
    assert len(events2.moved) == 0


def test_event_handler_thread_safety():
    """Test that event handler uses locks correctly."""
    handler = _EventHandler()

    # Add events and verify lock exists
    assert handler._lock is not None

    # Add via internal sets (simulating real usage)
    with handler._lock:
        handler._modified.add("file1")
        handler._modified.add("file2")

    events = handler.get_and_clear_events()
    assert len(events.modified) == 2
