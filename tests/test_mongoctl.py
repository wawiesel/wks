"""Tests for MongoDB controller helpers."""

import pytest

from wks import mongoctl


def test_is_local_uri_accepts_trailing_slash():
    """Default localhost URIs with trailing slash should count as local."""
    assert mongoctl.is_local_uri("mongodb://localhost:27017/")


def test_is_local_uri_requires_single_loopback_host():
    """Multiple hosts disable local auto-management even if all are loopback."""
    uri = "mongodb://user:pw@127.0.0.1:27017,[::1]:27018/test?replicaSet=rs0"
    assert not mongoctl.is_local_uri(uri)


def test_is_local_uri_rejects_remote_hosts():
    """Remote URIs must not be considered local."""
    assert not mongoctl.is_local_uri("mongodb+srv://cluster0.example.mongodb.net")


def test_local_node_returns_host_and_port():
    """Local node helper should expose host and port for auto-start logic."""
    assert mongoctl.local_node("mongodb://localhost:27017/") == ("localhost", 27017)
    assert mongoctl.local_node("mongodb://127.0.0.1:27018/") == ("127.0.0.1", 27018)
    assert mongoctl.local_node("mongodb://localhost:27017,127.0.0.1:27018/") is None


def test_ensure_mongo_running_autostarts_local_default(monkeypatch):
    """Local localhost URIs should be auto-started regardless of port."""
    import wks.mongoctl as mongoctl

    pings = []

    def fake_ping(uri, timeout_ms=500):
        pings.append((uri, timeout_ms))
        return len(pings) > 1

    monkeypatch.setattr(mongoctl, "mongo_ping", fake_ping)
    starts = []
    monkeypatch.setattr(mongoctl.shutil, "which", lambda exe: "/usr/bin/mongod" if exe == "mongod" else None)

    def fake_popen(cmd, *args, **kwargs):
        starts.append(cmd)

        class Proc:
            pid = 4242

        return Proc()

    monkeypatch.setattr(mongoctl.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(mongoctl.time, "sleep", lambda _: None)
    mongoctl.ensure_mongo_running("mongodb://localhost:27017/")
    assert starts, "mongod should be started when initial ping fails"
    port_arg_index = starts[0].index("--port") + 1
    assert starts[0][port_arg_index] == "27017"


def test_ensure_mongo_running_rejects_remote(monkeypatch):
    """Remote URIs still require the user to provide MongoDB."""
    import wks.mongoctl as mongoctl

    monkeypatch.setattr(mongoctl, "mongo_ping", lambda uri, timeout_ms=500: False)
    monkeypatch.setattr(mongoctl.shutil, "which", lambda exe: "/usr/bin/mongod" if exe == "mongod" else None)
    with pytest.raises(SystemExit):
        mongoctl.ensure_mongo_running("mongodb://db.example.com:27017/")
