"""Transform commands (binary to text conversion)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from pymongo import MongoClient

from ...config import WKSConfig
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
    try:
        cfg = WKSConfig.load()
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return 2

    try:
        # Get file path
        file_path = expand_path(args.file_path)

        if not file_path.exists():
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            return 2

        # Get engine name
        engine_name = args.engine

        # Get transform config
        transform_cfg = cfg.transform
        cache_location = expand_path(transform_cfg.cache.location)
        max_size_bytes = transform_cfg.cache.max_size_bytes

        # Engine config - assume docling is enabled/available
        # For now, we just use default options or empty dict if not found in new structure
        options = {}

        # Get output path if specified
        output_path = None
        if args.output:
            output_path = Path(args.output)

        # Connect to database
        uri = cfg.mongo.uri
        db_name = cfg.transform.database
        # coll_name = cfg.transform.database.split(".")[1] # Not needed
        client = connect_to_mongo(uri)
        db = client[db_name]

        # Initialize controller
        default_engine = transform_cfg.default_engine
        controller = TransformController(db, cache_location, max_size_bytes, default_engine)

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
