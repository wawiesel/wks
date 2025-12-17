"""Shared fixtures for integration tests."""

from pathlib import Path

import pytest


class FakeCollection:
    """Fake MongoDB collection for testing."""

    def __init__(self):
        self.docs = {}
        self.deleted = []

    def count_documents(self, filt, limit=None):
        path = filt.get("path") if isinstance(filt, dict) else None
        if path:
            if isinstance(path, dict) and "$in" in path:
                return sum(1 for candidate in path["$in"] if candidate in self.docs)
            if isinstance(path, str):
                return 1 if path in self.docs else 0
        return len(self.docs)

    def find_one(self, filt, projection=None):
        path = filt.get("path") if isinstance(filt, dict) else None
        if not isinstance(path, str):
            return None
        doc = self.docs.get(path)
        if not doc:
            return None
        if projection:
            return {key: doc.get(key) for key in projection if key in doc}
        return doc

    def update_one(self, filt, update, upsert=False):
        path = filt.get("path") if isinstance(filt, dict) else None
        if not isinstance(path, str):
            return
        doc = update.get("$set", {})
        self.docs[path] = dict(doc)

    def delete_one(self, filt):
        path = filt.get("path") if isinstance(filt, dict) else None
        if isinstance(path, str):
            self.docs.pop(path, None)
            self.deleted.append(path)

    def find(self, filt, projection=None):
        return iter([])

    def delete_many(self, filt):
        pass


class FakeVault:
    """Fake vault for testing."""

    def __init__(self, *args, **kwargs):
        self.vault_path = kwargs.get("vault_path", Path("/tmp/test_vault"))
        self.links_dir = kwargs.get("links_dir")

    def ensure_structure(self):
        pass

    def log_file_operation(self, *args, **kwargs):
        pass

    def update_link_on_move(self, *args, **kwargs):
        pass

    def update_vault_links_on_move(self, *args, **kwargs):
        pass

    def mark_reference_deleted(self, *args, **kwargs):
        pass

    def create_project_note(self, *args, **kwargs):
        pass


class FakeIndexer:
    """Fake vault indexer for testing."""

    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    def from_config(cls, vault, cfg):
        return cls()

    def sync(self, incremental=False):
        pass

    def update_links_on_file_move(self, old_uri, new_uri):
        return 0

    def has_references_to(self, path):
        return False


class FakeObserver:
    """Fake filesystem observer for testing."""

    def stop(self):
        pass

    def join(self):
        pass


@pytest.fixture
def mock_mongodb():
    """Mock MongoDB connection for integration tests."""
    return FakeCollection()


@pytest.fixture
def temp_watch_directory(tmp_path):
    """Create a temporary directory with test files."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    (watch_dir / "test.txt").write_text("test content")
    return watch_dir
