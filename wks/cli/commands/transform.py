"""Transform commands (binary to text conversion)."""

from __future__ import annotations

import argparse
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
    """
    cfg = load_config()
    display = getattr(args, "display_obj", None)

    try:
        # Get file path
        file_path = expand_path(args.file_path)

        if not file_path.exists():
            if display:
                display.error(f"File not found: {file_path}")
            else:
                print(f"Error: File not found: {file_path}")
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
            if display:
                display.error(f"Engine '{engine_name}' is not enabled")
            else:
                print(f"Error: Engine '{engine_name}' is not enabled")
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

        # Perform transform
        if display:
            display.info(f"Transforming {file_path.name} using {engine_name}...")

        cache_key = controller.transform(file_path, engine_name, options, output_path)

        # Output results
        if output_path:
            if display:
                display.success(f"Transformed to {output_path}")
                display.info(f"Cache key: {cache_key}")
            else:
                print(f"Transformed to {output_path}")
                print(f"Cache key: {cache_key}")
        else:
            # Just output cache key
            print(cache_key)

        return 0

    except ValueError as exc:
        if display:
            display.error(str(exc))
        else:
            print(f"Error: {exc}")
        return 2
    except RuntimeError as exc:
        if display:
            display.error(f"Transform failed: {exc}")
        else:
            print(f"Error: Transform failed: {exc}")
        return 2
    except Exception as exc:
        if display:
            display.error(f"Unexpected error: {exc}")
        else:
            print(f"Error: {exc}")
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
