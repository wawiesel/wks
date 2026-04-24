"""REST server entry point."""

from __future__ import annotations

import argparse
import sys

import uvicorn

from .server import create_app


def main(argv: list[str] | None = None) -> int:
    """Run the WKS REST server."""
    parser = argparse.ArgumentParser(description="Run the WKS REST server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8787, type=int)
    args = parser.parse_args(argv)

    print(f"Starting WKS REST server on {args.host}:{args.port}", file=sys.stderr)
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
