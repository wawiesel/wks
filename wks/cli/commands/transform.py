"""Transform commands (binary to text conversion)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from pymongo import MongoClient

from ...config import load_config
from ...db_helpers import get_transform_db_config, connect_to_mongo
from ...transform import TransformController
from ...utils import expand_path


def transform_cmd(args: argparse.Namespace) -> int:
    """Transform file using specified engine.

    Args:
        args: Command arguments with file_path, engine, output, and options

    Returns:
        Exit code (0 for success, non-zero for error)

    Note:
        All messages go to stderr, only cache key goes to stdout.
        This allows piping the checksum while seeing progress.
    """
    cfg = load_config()

    try:
        # Get file path
        file_path = expand_path(args.file_path)

        if not file_path.exists():
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            return 2

        # Get engine name
        engine_name = args.engine

        # Get transform config
        transform_cfg = cfg.get("transform", {})
        cache_cfg = transform_cfg.get("cache", {})
        cache_location = expand_path(cache_cfg.get("location", ".wks/transform/cache"))
        max_size_bytes = cache_cfg.get("max_size_bytes", 1073741824)  # 1GB default

        # Get engine config
        engine_cfg = transform_cfg.get("engines", {}).get(engine_name, {})

        # Check if engine is enabled
        if not engine_cfg.get("enabled", False):
            print(f"Error: Engine '{engine_name}' is not enabled", file=sys.stderr)
            return 2

        # Build options from config and CLI args
        options = dict(engine_cfg)
        options.pop("enabled", None)

        # Get output path if specified
        output_path = None
        if args.output:
            output_path = Path(args.output)

        # Connect to database
        uri, db_name, coll_name = get_transform_db_config(cfg)
        client = connect_to_mongo(uri)
        db = client[db_name]

        # Initialize controller
        controller = TransformController(db, cache_location, max_size_bytes)

        # Perform transform (status message to stderr)
        print(f"Transforming {file_path.name} using {engine_name}...", file=sys.stderr)

        cache_key = controller.transform(file_path, engine_name, options, output_path)

        # Output results: cache key to stdout, messages to stderr
        if output_path:
            print(f"Transformed to {output_path}", file=sys.stderr)

        # Always output cache key to stdout
        print(cache_key)

        return 0

    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"Error: Transform failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


def setup_transform_parser(subparsers) -> None:
    """Register transform command.

    Args:
        subparsers: Argparse subparsers to add command to
    """
    parser = subparsers.add_parser(
        "transform",
        help="Transform file using specified engine"
    )

    parser.add_argument("engine", help="Transform engine name (e.g., 'docling')")
    parser.add_argument("file_path", help="Path to file to transform")
    parser.add_argument(
        "-o", "--output",
        help="Output file path (if not specified, only cache key is output)"
    )

    parser.set_defaults(func=transform_cmd)
