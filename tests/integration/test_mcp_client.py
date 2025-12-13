import io
import json
import socket
import threading
from pathlib import Path

from wks.mcp.client import proxy_stdio_to_socket


def test_proxy_stdio_to_socket_round_trip(monkeypatch):
    """proxy_stdio_to_socket streams stdin to a socketpair and echoes to stdout."""
    client_sock, server_sock = socket.socketpair()

    class FakeSocket:
        def __init__(self):
            self._sock = client_sock

        def connect(self, _path):
            return None

        def makefile(self, mode):
            return self._sock.makefile(mode)

        def shutdown(self, how):
            self._sock.shutdown(how)

        def close(self):
            self._sock.close()

    monkeypatch.setattr(socket, "socket", lambda *a, **k: FakeSocket())

    def echo():
        reader = server_sock.makefile("r")
        writer = server_sock.makefile("w")
        for line in reader:
            writer.write(line)
            writer.flush()
        reader.close()
        writer.close()
        server_sock.close()

    threading.Thread(target=echo, daemon=True).start()

    stdin = io.StringIO(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}) + "\n")
    stdout = io.StringIO()

    assert proxy_stdio_to_socket(Path("/tmp/dummy.sock"), stdin=stdin, stdout=stdout) is True
    assert '"method": "ping"' in stdout.getvalue()


def test_proxy_stdio_to_socket_handles_connection_error(monkeypatch):
    """proxy_stdio_to_socket returns False when socket connect fails."""

    class FailingSocket:
        def connect(self, _path):
            raise OSError("boom")

    monkeypatch.setattr(socket, "socket", lambda *a, **k: FailingSocket())

    stdin = io.StringIO()
    stdout = io.StringIO()

    assert proxy_stdio_to_socket(Path("/tmp/missing.sock"), stdin=stdin, stdout=stdout) is False


def test_proxy_stdio_to_socket_joins_threads(monkeypatch):
    """Ensure join loop executes even when work is minimal."""

    class DummyThread:
        def __init__(self, target=None, name=None, daemon=None):
            self._alive = True

        def start(self):
            return None

        def is_alive(self):
            return self._alive

        def join(self, timeout=None):
            self._alive = False

    class DummySocket:
        def connect(self, _path):
            return None

        def makefile(self, mode):
            return io.StringIO()

        def shutdown(self, how):
            return None

        def close(self):
            return None

    monkeypatch.setattr(socket, "socket", lambda *a, **k: DummySocket())
    monkeypatch.setattr(threading, "Thread", DummyThread)

    assert proxy_stdio_to_socket(Path("/tmp/dummy.sock"), stdin=io.StringIO("data\n"), stdout=io.StringIO()) is True
