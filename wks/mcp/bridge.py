"""Background MCP broker that multiplexes clients onto the MCP server."""

from __future__ import annotations

import contextlib
import socket
import threading
from pathlib import Path

from .server import MCPServer


class MCPBroker:
    """Unix-domain socket broker that serves the MCP server to many clients."""

    def __init__(self, socket_path: Path):
        self.socket_path = socket_path
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if self.socket_path.exists():
                self.socket_path.unlink()
        except FileNotFoundError:
            pass

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.socket_path))
        server.listen()
        self._server = server
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._serve, name="wks-mcp-broker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._server:
            with contextlib.suppress(OSError):
                self._server.close()
            self._server = None
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        try:
            if self.socket_path.exists():
                self.socket_path.unlink()
        except Exception:
            pass

    def _serve(self) -> None:
        assert self._server is not None
        while not self._stop_event.is_set():
            try:
                conn, _ = self._server.accept()
            except OSError:
                break
            threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()

    def _handle_client(self, conn: socket.socket) -> None:
        with conn:
            rfile = conn.makefile("r")
            wfile = conn.makefile("w")
            server = MCPServer(input_stream=rfile, output_stream=wfile)
            try:
                server.run()
            finally:
                with contextlib.suppress(Exception):
                    wfile.flush()
                rfile.close()
                wfile.close()


__all__ = ["MCPBroker"]
