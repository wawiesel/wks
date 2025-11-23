"""Diff commands (file comparison)."""

from __future__ import annotations

import argparse
from pathlib import Path

from ...config import load_config
from ...diff import DiffController
from ...utils import expand_path


def diff_cmd(args: argparse.Namespace) -> int:
    """Compare two files using specified diff engine.

    Args:
        args: Command arguments with engine, file1, file2, and options

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    cfg = load_config()
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

        # Get diff config
        diff_cfg = cfg.get("diff", {})
        engine_cfg = diff_cfg.get("engines", {}).get(engine_name, {})

        # Check if engine is enabled
        if not engine_cfg.get("enabled", False):
            if display:
                display.error(f"Engine '{engine_name}' is not enabled")
            else:
                print(f"Error: Engine '{engine_name}' is not enabled")
            return 2

        # Build options from config
        options = dict(engine_cfg)
        options.pop("enabled", None)

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
