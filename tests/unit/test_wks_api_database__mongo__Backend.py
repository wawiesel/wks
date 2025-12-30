import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from wks.api.database._mongo._Backend import _Backend
from wks.api.database.DatabaseConfig import DatabaseConfig


def test_mongo_backend_init_error():
    """Test error when data is not _Data (line 26)."""
    # Create with wrong data type bypassing validation
    cfg = DatabaseConfig.model_construct(type="mongo", prefix="test", data=None)
    with pytest.raises(ValueError, match="MongoDB config data is required"):
        _Backend(cfg, "db", "coll")


def test_mongo_backend_ensure_local_early_connect(monkeypatch):
    """Test skip startup if already connected (line 91)."""
    cfg = DatabaseConfig.model_validate(
        {
            "type": "mongo",
            "prefix": "test",
            "data": {"uri": "mongodb://localhost:27017", "local": True},
        }
    )
    backend = _Backend(cfg, "db", "coll")
    monkeypatch.setattr(_Backend, "_can_connect", lambda self, uri: True)
    backend._ensure_local_mongod("mongodb://localhost")
    assert backend._started_local is False


def test_mongo_backend_fallback_binary(monkeypatch, tmp_path):
    """Test fallback binary detection (lines 102-106)."""
    monkeypatch.setattr(shutil, "which", lambda x: None)

    # We need to mock Path.exists carefully
    def mock_exists(self):
        return str(self) == "/usr/local/bin/mongod"

    monkeypatch.setattr(Path, "exists", mock_exists)

    cfg = DatabaseConfig.model_validate(
        {
            "type": "mongo",
            "prefix": "test",
            "data": {"uri": "mongodb://localhost:27017", "local": True},
        }
    )
    backend = _Backend(cfg, "db", "coll")
    # Just need it to get past the search
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: MagicMock())
    monkeypatch.setattr(_Backend, "_can_connect", lambda *args: True)
    backend._ensure_local_mongod("mongodb://localhost")


def test_mongo_backend_default_port():
    """Test default port 27017 (line 200)."""
    host, port = _Backend._parse_host_port("mongodb://localhost")
    assert host == "localhost"
    assert port == 27017


def test_mongo_backend_exit_error(monkeypatch):
    """Test exception in __exit__ (lines 56-57)."""
    cfg = DatabaseConfig.model_validate(
        {
            "type": "mongo",
            "prefix": "test",
            "data": {"uri": "mongodb://localhost:27017", "local": True},
        }
    )
    backend = _Backend(cfg, "db", "coll")

    # Mock process that raises on terminate
    mock_proc = MagicMock()
    mock_proc.terminate.side_effect = Exception("fail")

    backend._started_local = True
    backend._mongod_proc = mock_proc
    # Should not raise
    backend.__exit__(None, None, None)


def test_mongo_backend_exit_wait_timeout(monkeypatch):
    """Test timeout in wait (lines 56-57)."""
    cfg = DatabaseConfig.model_validate(
        {
            "type": "mongo",
            "prefix": "test",
            "data": {"uri": "mongodb://localhost:27017", "local": True},
        }
    )
    backend = _Backend(cfg, "db", "coll")

    # Mock process that timeouts on wait
    mock_proc = MagicMock()
    mock_proc.wait.side_effect = subprocess.TimeoutExpired(["mongod"], 5)

    backend._started_local = True
    backend._mongod_proc = mock_proc
    # Should not raise
    backend.__exit__(None, None, None)


def test_mongo_backend_basic_ops(monkeypatch, tmp_path):
    """Test basic operations with local=False (uses mongomock)."""
    import mongomock

    monkeypatch.setattr("wks.api.database._mongo._Backend.MongoClient", mongomock.MongoClient)

    cfg = DatabaseConfig.model_validate(
        {
            "type": "mongo",
            "prefix": "test",
            "data": {"uri": "mongodb://localhost:27017", "local": False},
        }
    )
    with _Backend(cfg, "test_db", "test_coll") as backend:
        # insert
        backend.insert_many([{"a": 1}])
        assert backend.count_documents() == 1

        # find_one
        assert backend.find_one({"a": 1})["a"] == 1

        # update_one
        backend.update_one({"a": 1}, {"$set": {"a": 2}})
        assert backend.find_one({"a": 2})["a"] == 2

        # update_many
        count = backend.update_many({"a": 2}, {"$set": {"b": 3}})
        assert count == 1

        # find
        res = list(backend.find())
        assert len(res) == 1
        assert res[0]["b"] == 3

        # list_collection_names
        cols = backend.list_collection_names()
        assert "test_coll" in cols

        # delete_many
        del_count = backend.delete_many({})
        assert del_count == 1
        assert backend.count_documents() == 0


def test_mongo_backend_list_collections_error():
    """Test error when client not initialized (line 84)."""
    cfg = DatabaseConfig.model_validate(
        {
            "type": "mongo",
            "prefix": "test",
            "data": {"uri": "mongodb://localhost:27017", "local": False},
        }
    )
    backend = _Backend(cfg, "db", "coll")
    with pytest.raises(RuntimeError, match="Mongo client not initialized"):
        backend.list_collection_names()


def test_mongo_backend_local_startup_success(monkeypatch, tmp_path):
    """Test successful local mongod startup (line 88+)."""
    wks_home = tmp_path / ".wks"
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    import mongomock

    # We need to mock MongoClient but also _can_connect
    monkeypatch.setattr("wks.api.database._mongo._Backend.MongoClient", mongomock.MongoClient)

    # Mock _can_connect to return False first, then True
    connect_results = [False, True]

    def mock_can_connect(self, uri):
        return connect_results.pop(0) if connect_results else True

    monkeypatch.setattr(_Backend, "_can_connect", mock_can_connect)

    # Mock subprocess.Popen
    class MockProc:
        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, timeout=None):
            pass

    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kwargs: MockProc())
    monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/mongod")

    cfg = DatabaseConfig.model_validate(
        {
            "type": "mongo",
            "prefix": "test",
            "data": {"uri": "mongodb://localhost:27017", "local": True},
        }
    )
    with _Backend(cfg, "db", "coll") as backend:
        assert backend._started_local is True


def test_mongo_backend_local_startup_error_address_in_use(monkeypatch, tmp_path):
    """Test local startup error - address in use (line 140, 166)."""
    wks_home = tmp_path / ".wks"
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    monkeypatch.setattr(_Backend, "_can_connect", lambda self, uri: False)

    class MockProc:
        returncode = 48

        def poll(self):
            return 48

    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kwargs: MockProc())
    monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/mongod")

    cfg = DatabaseConfig.model_validate(
        {
            "type": "mongo",
            "prefix": "test",
            "data": {"uri": "mongodb://localhost:27017", "local": True},
        }
    )
    with pytest.raises(RuntimeError, match="already in use"), _Backend(cfg, "db", "coll"):
        pass


def test_mongo_backend_local_startup_error_no_binary(monkeypatch, tmp_path):
    """Test local startup error - no binary found (line 109)."""
    monkeypatch.setattr(shutil, "which", lambda x: None)
    # Mock Path.exists to return False for fallback paths
    monkeypatch.setattr(Path, "exists", lambda self: False)
    monkeypatch.setattr(_Backend, "_can_connect", lambda self, uri: False)

    cfg = DatabaseConfig.model_validate(
        {
            "type": "mongo",
            "prefix": "test",
            "data": {"uri": "mongodb://localhost:27017", "local": True},
        }
    )
    with pytest.raises(RuntimeError, match="mongod binary not found"), _Backend(cfg, "db", "coll"):
        pass


def test_mongo_backend_local_startup_error_data_dir(monkeypatch, tmp_path):
    """Test local startup error - data directory issue (line 146, 172)."""
    wks_home = tmp_path / ".wks"
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    monkeypatch.setattr(_Backend, "_can_connect", lambda self, uri: False)

    # We need to make the temp log file accessible for reading in the test
    log_file = tmp_path / "mongo_err.log"
    log_file.write_text("locked")

    class MockProc:
        returncode = 100

        def poll(self):
            return 100

    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kwargs: MockProc())
    monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/mongod")

    # Mock tempfile to return our known log file
    class MockTempFile:
        def __init__(self, *args, **kwargs):
            self.name = str(log_file)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", MockTempFile)

    cfg = DatabaseConfig.model_validate(
        {
            "type": "mongo",
            "prefix": "test",
            "data": {"uri": "mongodb://localhost:27017", "local": True},
        }
    )
    with pytest.raises(RuntimeError, match="data directory issue"), _Backend(cfg, "db", "coll"):
        pass


def test_mongo_backend_popen_filenotfound(monkeypatch, tmp_path):
    """Test FileNotFoundError during Popen (lines 130-131)."""
    monkeypatch.setattr(shutil, "which", lambda x: "/no/bin")
    monkeypatch.setattr(_Backend, "_can_connect", lambda *args: False)

    def mock_popen(*args, **kwargs):
        raise FileNotFoundError("no bin")

    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    cfg = DatabaseConfig.model_validate(
        {
            "type": "mongo",
            "prefix": "test",
            "data": {"uri": "mongodb://localhost:27017", "local": True},
        }
    )
    with pytest.raises(RuntimeError, match="mongod binary not found"), _Backend(cfg, "db", "coll"):
        pass


def test_mongo_backend_parse_uri_error(monkeypatch):
    """Test error when URI missing host (line 197)."""
    # Mock parse_uri in the Backend module where it's imported
    monkeypatch.setattr("wks.api.database._mongo._Backend.parse_uri", lambda u: {"nodelist": []})
    # Ensure it hits _parse_host_port by making _can_connect False
    monkeypatch.setattr(_Backend, "_can_connect", lambda self, uri: False)

    cfg = DatabaseConfig.model_validate(
        {
            "type": "mongo",
            "prefix": "test",
            "data": {"uri": "mongodb://localhost", "local": True},
        }
    )
    backend = _Backend(cfg, "db", "coll")
    with pytest.raises(RuntimeError, match="must include host:port"):
        backend.__enter__()


def test_mongo_backend_can_connect_exception(monkeypatch):
    """Test _can_connect exception handling (line 190)."""
    cfg = DatabaseConfig.model_validate(
        {
            "type": "mongo",
            "prefix": "test",
            "data": {"uri": "mongodb://localhost", "local": False},
        }
    )
    backend = _Backend(cfg, "db", "coll")

    def mock_client(*args, **kwargs):
        raise Exception("conn fail")

    monkeypatch.setattr("wks.api.database._mongo._Backend.MongoClient", mock_client)

    assert backend._can_connect("mongodb://localhost") is False


def test_mongo_backend_local_startup_timeout(monkeypatch, tmp_path):
    """Test timeout starting local mongod (line 182)."""
    wks_home = tmp_path / ".wks"
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    monkeypatch.setattr(_Backend, "_can_connect", lambda self, uri: False)
    monkeypatch.setattr(time, "sleep", lambda x: None)

    class MockProc:
        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, timeout=None):
            pass

    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kwargs: MockProc())
    monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/mongod")

    cfg = DatabaseConfig.model_validate(
        {
            "type": "mongo",
            "prefix": "test",
            "data": {"uri": "mongodb://localhost:27017", "local": True},
        }
    )

    # Reduce max_attempts to speed up test
    import wks.api.database._mongo._Backend as backend_mod

    monkeypatch.setattr(backend_mod, "subprocess", subprocess)  # ensure module uses mocked subprocess

    with pytest.raises(RuntimeError, match="Failed to start local mongod"), _Backend(cfg, "db", "coll"):
        pass


def test_mongo_backend_local_startup_generic_exit(monkeypatch, tmp_path):
    """Test generic exit code during startup (line 152, 179)."""
    wks_home = tmp_path / ".wks"
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    monkeypatch.setattr(_Backend, "_can_connect", lambda self, uri: False)

    class MockProc:
        returncode = 1

        def poll(self):
            return 1

    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kwargs: MockProc())
    monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/mongod")

    cfg = DatabaseConfig.model_validate(
        {
            "type": "mongo",
            "prefix": "test",
            "data": {"uri": "mongodb://localhost:27017", "local": True},
        }
    )
    with pytest.raises(RuntimeError, match="process exited with code 1"), _Backend(cfg, "db", "coll"):
        pass
