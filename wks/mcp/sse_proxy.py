"""SSE proxy for the WKS MCP stdio server.

Wraps ``python3 -m wks.mcp.main`` behind an SSE/HTTP endpoint so that
containers (or any HTTP client) can reach the MCP server without needing
direct stdio access.

MCP SSE transport protocol:
    GET  /sse                       → SSE stream (first event = endpoint URL)
    POST /messages?sessionId=<id>   → send JSON-RPC request, returns 202

Usage:
    python -m wks.mcp.sse_proxy [--host localhost] [--port 8765]
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid

from aiohttp import web

log = logging.getLogger("wks.mcp.sse_proxy")

PYTHON = os.environ.get("WKS_MCP_PYTHON", sys.executable)


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
    )
    log.info("session %s: spawned MCP pid %s", session_id, process.pid)

    request.app["sessions"][session_id] = {
        "process": process,
        "response": response,
    }

    # Tell the client where to POST messages.
    await response.write(f"event: endpoint\ndata: /messages?sessionId={session_id}\n\n".encode())

    # Forward subprocess stdout → SSE events.
    try:
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
    except (ConnectionResetError, asyncio.CancelledError):
        log.info("session %s: client disconnected", session_id)
    finally:
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
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="WKS MCP SSE proxy")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = web.Application(middlewares=[cors_middleware])
    app["sessions"] = {}
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/sse", handle_sse)
    app.router.add_post("/messages", handle_message)
    app.router.add_get("/health", handle_health)

    log.info("Starting MCP SSE proxy on %s:%s", args.host, args.port)
    web.run_app(app, host=args.host, port=args.port, print=lambda msg: log.info(msg))


if __name__ == "__main__":
    main()
