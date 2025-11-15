"""Tests for MongoDB controller helpers."""

from wks import mongoctl


def test_is_local_uri_accepts_trailing_slash():
    """Default localhost URIs with trailing slash should count as local."""
    assert mongoctl._is_local_uri("mongodb://localhost:27017/")


def test_is_local_uri_requires_single_loopback_host():
    """Multiple hosts disable local auto-management even if all are loopback."""
    uri = "mongodb://user:pw@127.0.0.1:27017,[::1]:27018/test?replicaSet=rs0"
    assert not mongoctl._is_local_uri(uri)


def test_is_local_uri_rejects_remote_hosts():
    """Remote URIs must not be considered local."""
    assert not mongoctl._is_local_uri("mongodb+srv://cluster0.example.mongodb.net")


def test_local_node_returns_host_and_port():
    """Local node helper should expose host and port for auto-start logic."""
    assert mongoctl._local_node("mongodb://localhost:27017/") == ("localhost", 27017)
    assert mongoctl._local_node("mongodb://127.0.0.1:27018/") == ("127.0.0.1", 27018)
    assert mongoctl._local_node("mongodb://localhost:27017,127.0.0.1:27018/") is None
