"""SSE proxy for the WKS MCP stdio server.

Wraps ``python3 -m wks.mcp.main`` behind an SSE/HTTP endpoint so that
containers (or any HTTP client) can reach the MCP server without needing
direct stdio access.

MCP SSE transport protocol:
    GET  /sse                       → SSE stream (first event = endpoint URL)
    POST /messages?sessionId=<id>   → send JSON-RPC request, returns 202

Usage:
    wksc mcp proxy start [--port 8765]
    wksc mcp proxy stop
    wksc mcp proxy status
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import uuid
from contextlib import suppress
from pathlib import Path

from aiohttp import web

log = logging.getLogger("wks.mcp.sse_proxy")

PYTHON = os.environ.get("WKS_MCP_PYTHON", sys.executable)
DEFAULT_HOST = "0.0.0.0"  # containers need to reach the proxy
DEFAULT_PORT = 8765


def _pid_file() -> Path:
    """PID file location (cross-platform, inside WKS_HOME)."""
    home = Path(os.environ.get("WKS_HOME", Path.home() / ".wks"))
    return home / "mcp-proxy.pid"


def _log_file() -> Path:
    """Log file location."""
    home = Path(os.environ.get("WKS_HOME", Path.home() / ".wks"))
    log_dir = home / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "mcp-proxy.log"


def _read_pid() -> int | None:
    """Read PID from file, return None if missing or stale."""
    pf = _pid_file()
    if not pf.exists():
        return None
    try:
        pid = int(pf.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (ValueError, OSError):
        return None


def _write_pid() -> None:
    _pid_file().parent.mkdir(parents=True, exist_ok=True)
    _pid_file().write_text(str(os.getpid()))


def _remove_pid() -> None:
    with suppress(OSError):
        _pid_file().unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# SSE connection - one MCP subprocess per session
# ---------------------------------------------------------------------------


async def handle_sse(request: web.Request) -> web.StreamResponse:
    """Establish an SSE stream and spawn a backing MCP subprocess."""
    session_id = str(uuid.uuid4())

    response = web.StreamResponse()
    response.headers["Content-Type"] = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    response.headers["Access-Control-Allow-Origin"] = "*"
    await response.prepare(request)

    process = await asyncio.create_subprocess_exec(
        PYTHON,
        "-m",
        "wks.mcp.main",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=os.environ,
        limit=16 * 1024 * 1024,  # 16 MB — default 64 KB is too small for large responses
    )
    log.info("session %s: spawned MCP pid %s", session_id, process.pid)

    request.app["sessions"][session_id] = {
        "process": process,
        "response": response,
    }

    # Tell the client where to POST messages.
    await response.write(f"event: endpoint\ndata: /messages?sessionId={session_id}\n\n".encode())

    # Task that reads subprocess stdout and forwards to the SSE stream.
    # Wrapped so the heartbeat can cancel it when the client disconnects.
    read_task: asyncio.Task | None = None

    async def _read_stdout():
        assert process.stdout is not None
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            text = line.decode().strip()
            if not text:
                continue
            # Handle LSP Content-Length framing (the server auto-detects).
            if text.lower().startswith("content-length"):
                length = int(text.split(":", 1)[1].strip())
                # Consume header lines until blank separator.
                while True:
                    sep = await process.stdout.readline()
                    if not sep or not sep.strip():
                        break
                data = await process.stdout.readexactly(length)
                text = data.decode()
            if text:
                await response.write(f"event: message\ndata: {text}\n\n".encode())

    # Send periodic SSE comments to detect dead clients.
    # When the write fails, cancel the read loop so cleanup runs.
    async def _heartbeat():
        try:
            while True:
                await asyncio.sleep(15)
                await response.write(b": keepalive\n\n")
        except (ConnectionResetError, asyncio.CancelledError):
            if read_task and not read_task.done():
                read_task.cancel()

    heartbeat_task = asyncio.create_task(_heartbeat())

    try:
        read_task = asyncio.create_task(_read_stdout())
        await read_task
    except (ConnectionResetError, asyncio.CancelledError, asyncio.LimitOverrunError, ValueError):
        log.info("session %s: client disconnected or stream error", session_id)
    finally:
        heartbeat_task.cancel()
        process.terminate()
        await process.wait()
        request.app["sessions"].pop(session_id, None)
        log.info("session %s: cleaned up", session_id)

    return response


# ---------------------------------------------------------------------------
# Message relay - POST JSON-RPC to subprocess stdin
# ---------------------------------------------------------------------------


async def handle_message(request: web.Request) -> web.Response:
    """Forward a JSON-RPC message to the subprocess."""
    session_id = request.query.get("sessionId")
    if not session_id or session_id not in request.app["sessions"]:
        return web.Response(status=404, text="Session not found")

    session = request.app["sessions"][session_id]
    process = session["process"]

    body = await request.text()
    assert process.stdin is not None
    process.stdin.write((body + "\n").encode())
    await process.stdin.drain()

    return web.Response(status=202, text="Accepted")


# ---------------------------------------------------------------------------
# Vault check - simple REST endpoint for containers to call
# ---------------------------------------------------------------------------


async def handle_vault_check(request: web.Request) -> web.Response:
    """POST /vault/check — run wks vault check, return JSON result."""
    try:
        data = await request.json() if request.can_read_body and request.content_type == "application/json" else {}
        path = data.get("path")
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid JSON body"}, status=400)

    from wks.api.config.URI import URI
    from wks.api.vault.cmd_check import cmd_check as vault_cmd_check

    uri = URI(path) if path else None

    def run_check():
        result = vault_cmd_check(uri=uri)
        for _ in result.progress_callback(result):
            pass
        return result

    try:
        result = await asyncio.wait_for(asyncio.to_thread(run_check), timeout=30.0)
        out = result.output or {}
        return web.json_response(
            {
                "ok": out.get("is_valid", result.success),
                "broken_count": out.get("broken_count", 0),
                "issues": out.get("issues", []),
                "errors": out.get("errors", []),
            }
        )
    except asyncio.TimeoutError:
        return web.json_response({"ok": False, "error": "timed out"}, status=504)
    except Exception as e:
        log.exception("vault check error")
        return web.json_response({"ok": False, "error": str(e)}, status=500)


# ---------------------------------------------------------------------------
# Health / CORS
# ---------------------------------------------------------------------------


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response(
        {
            "status": "ok",
            "sessions": len(request.app["sessions"]),
        }
    )


@web.middleware
async def cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        resp = web.Response(status=204)
    else:
        resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


# ---------------------------------------------------------------------------
# Cleanup on shutdown
# ---------------------------------------------------------------------------


async def on_shutdown(app: web.Application) -> None:
    for sid, session in list(app["sessions"].items()):
        log.info("shutdown: terminating session %s", sid)
        session["process"].terminate()
        await session["process"].wait()
    app["sessions"].clear()


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """Run the SSE proxy in the foreground (blocking)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    _write_pid()
    try:
        app = web.Application(middlewares=[cors_middleware])
        app["sessions"] = {}
        app.on_shutdown.append(on_shutdown)
        app.router.add_get("/sse", handle_sse)
        app.router.add_post("/messages", handle_message)
        app.router.add_get("/health", handle_health)
        app.router.add_post("/vault/check", handle_vault_check)

        log.info("Starting MCP SSE proxy on %s:%s", host, port)
        web.run_app(app, host=host, port=port, print=lambda msg: log.info(msg))
    finally:
        _remove_pid()


def start_background(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> dict[str, object]:
    """Start the proxy as a background process. Returns status dict."""
    existing = _read_pid()
    if existing:
        return {"running": True, "pid": existing, "started": False, "message": f"Already running (pid {existing})"}

    import subprocess

    log_path = _log_file()
    log_fh = log_path.open("a")

    env = os.environ.copy()
    env["PYTHONPATH"] = env.get("PYTHONPATH", str(Path(__file__).resolve().parents[2]))

    proc = subprocess.Popen(
        [sys.executable, "-m", "wks.mcp.sse_proxy", "--host", host, "--port", str(port)],
        stdout=log_fh,
        stderr=log_fh,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        env=env,
    )
    return {"running": True, "pid": proc.pid, "started": True, "message": f"Started (pid {proc.pid}), log: {log_path}"}


def stop_background() -> dict[str, object]:
    """Stop a running background proxy. Returns status dict."""
    pid = _read_pid()
    if not pid:
        return {"running": False, "stopped": False, "message": "Not running"}

    with suppress(OSError):
        os.kill(pid, signal.SIGTERM)
    _remove_pid()
    return {"running": False, "stopped": True, "message": f"Stopped (pid {pid})"}


def get_status() -> dict[str, object]:
    """Check proxy status. Returns status dict."""
    pid = _read_pid()
    if pid:
        return {"running": True, "pid": pid}
    return {"running": False, "pid": None}


# ---------------------------------------------------------------------------
# __main__ entry point (used by background Popen and launchd plist)
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="WKS MCP SSE proxy")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
