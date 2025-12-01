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
        # Get targets (files or checksums)
        target1 = args.file1
        target2 = args.file2

        # Get engine name
        engine_name = args.engine

        # Initialize TransformController for checksum resolution
        # We need to set up DB connection and cache config
        transform_cfg = cfg.transform
        cache_location = expand_path(transform_cfg.cache_location)
        max_size_bytes = transform_cfg.cache_max_size_bytes

        uri = cfg.mongo.uri
        db_name = cfg.transform.database.split(".")[0]
        # coll_name = cfg.transform.database.split(".")[1] # Not needed for controller init
        
        from ...db_helpers import connect_to_mongo
        client = connect_to_mongo(uri)
        db = client[db_name]
        
        from ...transform import TransformController
        transform_controller = TransformController(db, cache_location, max_size_bytes)

        # Initialize DiffController
        controller = DiffController(transform_controller)

        # Perform diff
        options = {}
        result = controller.diff(target1, target2, engine_name, options)

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
