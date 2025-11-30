"""Diff commands (file comparison)."""

from __future__ import annotations

import argparse
from pathlib import Path

from ...config import WKSConfig
from ...diff import DiffController
from ...utils import expand_path


def diff_cmd(args: argparse.Namespace) -> int:
    """Compare two files using specified diff engine.

    Args:
        args: Command arguments with engine, file1, file2, and options

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        cfg = WKSConfig.load()
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return 2
    display = getattr(args, "display_obj", None)

    try:
        # Get file paths
        file1 = expand_path(args.file1)
        file2 = expand_path(args.file2)

        if not file1.exists():
            if display:
                display.error(f"File not found: {file1}")
            else:
                print(f"Error: File not found: {file1}")
            return 2

        if not file2.exists():
            if display:
                display.error(f"File not found: {file2}")
            else:
                print(f"Error: File not found: {file2}")
            return 2

        # Get engine name
        engine_name = args.engine

        # Get diff config (not yet in WKSConfig dataclass, so we might need to add it or skip validation for now)
        # For now, we'll proceed without strict config validation for diff engines as they are stateless
        options = {}

        # Initialize controller
        controller = DiffController()

        # Perform diff
        result = controller.diff(file1, file2, engine_name, options)

        # Output result
        print(result)

        return 0

    except ValueError as exc:
        if display:
            display.error(str(exc))
        else:
            print(f"Error: {exc}")
        return 2
    except RuntimeError as exc:
        if display:
            display.error(f"Diff failed: {exc}")
        else:
            print(f"Error: Diff failed: {exc}")
        return 2
    except Exception as exc:
        if display:
            display.error(f"Unexpected error: {exc}")
        else:
            print(f"Error: {exc}")
        return 2


def setup_diff_parser(subparsers) -> None:
    """Register diff command.

    Args:
        subparsers: Argparse subparsers to add command to
    """
    parser = subparsers.add_parser(
        "diff",
        help="Compare two files using specified diff engine"
    )

    parser.add_argument("engine", help="Diff engine name (e.g., 'bsdiff3', 'myers')")
    parser.add_argument("file1", help="First file path")
    parser.add_argument("file2", help="Second file path")

    parser.set_defaults(func=diff_cmd)
