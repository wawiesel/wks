"""Client helpers for connecting to the background MCP broker."""

from __future__ import annotations

import socket
import sys
import threading
from pathlib import Path
from typing import Optional, TextIO


def proxy_stdio_to_socket(
    socket_path: Path,
    *,
    stdin: Optional[TextIO] = None,
    stdout: Optional[TextIO] = None,
) -> bool:
    """Proxy the current stdio streams to the MCP broker socket."""
    in_stream = stdin or sys.stdin
    out_stream = stdout or sys.stdout

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(str(socket_path))
    except OSError:
        return False

    stop = threading.Event()
    sock_reader = sock.makefile("r")
    sock_writer = sock.makefile("w")

    def upstream():
        try:
            for line in in_stream:
                sock_writer.write(line)
                sock_writer.flush()
        finally:
            try:
                sock_writer.flush()
            except Exception:
                pass
            try:
                sock.shutdown(socket.SHUT_WR)
            except Exception:
                pass

    def downstream():
        try:
            for line in sock_reader:
                out_stream.write(line)
                out_stream.flush()
        finally:
            stop.set()

    threads = [
        threading.Thread(target=upstream, name="mcp-proxy-up", daemon=True),
        threading.Thread(target=downstream, name="mcp-proxy-down", daemon=True),
    ]
    for t in threads:
        t.start()
    try:
        while any(t.is_alive() for t in threads):
            for t in threads:
                t.join(timeout=0.1)
    finally:
        stop.set()
        sock_reader.close()
        sock_writer.close()
        sock.close()
    return True


__all__ = ["proxy_stdio_to_socket"]
