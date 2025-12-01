"""Cat command - display or save transformed content."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from ...config import WKSConfig
from ...db_helpers import get_transform_db_config, connect_to_mongo
from ...transform import TransformController
from ...utils import expand_path


def cat_cmd(args: argparse.Namespace) -> int:
    """Display or save transformed content.

    Args:
        args: Command arguments with input (file path or checksum), output

    Returns:
        Exit code (0 for success, non-zero for error)

    Note:
        - With file input: transforms file, stores in cache, displays/saves result
        - With checksum input: retrieves from cache, displays/saves result
        - Without -o: displays content to stdout
        - With -o: creates hardlink to cache file for efficiency
    """
    try:
        cfg = WKSConfig.load()
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return 2

    try:
        input_arg = args.input
        output_path = Path(args.output) if args.output else None

        # Get transform config
        transform_cfg = cfg.transform
        cache_location = expand_path(transform_cfg.cache.location)
        max_size_bytes = transform_cfg.cache.max_size_bytes

        # Connect to database
        uri = cfg.mongo.uri
        db_name = cfg.transform.database
        # coll_name = cfg.transform.database.split(".")[1]
        client = connect_to_mongo(uri)
        db = client[db_name]

        default_engine = transform_cfg.default_engine

        controller = TransformController(db, cache_location, max_size_bytes, default_engine)

        # Use the controller to get content
        content = controller.get_content(input_arg, output_path)
        
        # If output path was specified, controller handled writing/linking.
        # We just print a message to stderr.
        if output_path:
             print(f"Saved to {output_path}", file=sys.stderr)
        else:
             # Otherwise print content to stdout
             print(content)

        return 0

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


def setup_cat_parser(subparsers) -> None:
    """Register cat command.

    Args:
        subparsers: Argparse subparsers to add command to
    """
    parser = subparsers.add_parser(
        "cat",
        help="Display or save transformed content (from file or cache)"
    )

    parser.add_argument(
        "input",
        help="File path to transform or cache checksum (64 hex chars)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path (hardlinked to cache for efficiency)"
    )

    parser.set_defaults(func=cat_cmd)
