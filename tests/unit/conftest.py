"""Shared test fixtures for unit tests."""


class DummyConfig:
    """Mock WKSConfig for testing."""

    def __init__(self, monitor):
        self.monitor = monitor
        self.save_calls = 0

    def save(self):
        self.save_calls += 1

