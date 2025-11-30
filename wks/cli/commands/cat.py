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

        # Determine if input is a checksum (64 hex chars) or file path
        is_checksum = bool(re.match(r'^[a-f0-9]{64}$', input_arg))

        # Get transform config
        transform_cfg = cfg.transform
        cache_location = expand_path(transform_cfg.cache_location)
        max_size_bytes = transform_cfg.cache_max_size_bytes

        # Connect to database
        uri = cfg.mongo.uri
        db_name = cfg.transform.database.split(".")[0]
        coll_name = cfg.transform.database.split(".")[1]
        client = connect_to_mongo(uri)
        db = client[db_name]

        controller = TransformController(db, cache_location, max_size_bytes)

        if is_checksum:
            # Input is a checksum - retrieve from cache
            cache_key = input_arg
            cache_file = cache_location / f"{cache_key}.md"

            if not cache_file.exists():
                print(f"Error: Cache entry not found: {cache_key}", file=sys.stderr)
                return 2

            # Output to file or stdout
            if output_path:
                # Create hardlink for efficiency
                try:
                    os.link(cache_file, output_path)
                    print(f"Hardlinked to {output_path}", file=sys.stderr)
                except FileExistsError:
                    print(f"Error: Output file already exists: {output_path}", file=sys.stderr)
                    return 2
                except Exception as exc:
                    print(f"Error creating hardlink: {exc}", file=sys.stderr)
                    return 2
            else:
                # Display to stdout
                print(cache_file.read_text(encoding="utf-8"))

        else:
            # Input is a file path - transform it
            file_path = expand_path(input_arg)

            if not file_path.exists():
                print(f"Error: File not found: {file_path}", file=sys.stderr)
                return 2

            # Use docling engine (default)
            engine_name = "docling"
            # In new config structure, we assume docling is always available/enabled if not explicitly disabled
            # For now, we just use default options or empty dict if not found in new structure
            options = {}

            # Transform to cache
            print(f"Transforming {file_path.name}...", file=sys.stderr)
            cache_key = controller.transform(file_path, engine_name, options, output_path=None)

            # Get cache file location
            cache_file = cache_location / f"{cache_key}.md"

            if not cache_file.exists():
                print(f"Error: Transform failed to create cache file", file=sys.stderr)
                return 2

            # Output to file or stdout
            if output_path:
                # Create hardlink for efficiency
                try:
                    os.link(cache_file, output_path)
                    print(f"Hardlinked to {output_path}", file=sys.stderr)
                except FileExistsError:
                    print(f"Error: Output file already exists: {output_path}", file=sys.stderr)
                    return 2
                except Exception as exc:
                    print(f"Error creating hardlink: {exc}", file=sys.stderr)
                    return 2
            else:
                # Display to stdout
                print(cache_file.read_text(encoding="utf-8"))

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
