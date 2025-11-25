"""Cat command - display or save transformed content."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from ...config import load_config
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
    cfg = load_config()

    try:
        input_arg = args.input
        output_path = Path(args.output) if args.output else None

        # Determine if input is a checksum (64 hex chars) or file path
        is_checksum = bool(re.match(r'^[a-f0-9]{64}$', input_arg))

        # Get transform config
        transform_cfg = cfg.get("transform", {})
        cache_cfg = transform_cfg.get("cache", {})
        cache_location = expand_path(cache_cfg.get("location", "~/.wks/transform/cache"))
        max_size_bytes = cache_cfg.get("max_size_bytes", 1073741824)

        # Connect to database
        uri, db_name, coll_name = get_transform_db_config(cfg)
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
            engine_cfg = transform_cfg.get("engines", {}).get(engine_name, {})

            if not engine_cfg.get("enabled", False):
                print(f"Error: Engine '{engine_name}' is not enabled", file=sys.stderr)
                return 2

            # Build options from config
            options = dict(engine_cfg)
            options.pop("enabled", None)

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
