"""Config commands for wkso CLI."""

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from .config import load_user_config, DEFAULT_TIMESTAMP_FORMAT


def print_config(args: argparse.Namespace) -> int:
    """Print effective configuration."""
    cfg = load_user_config()
    print(json.dumps(cfg, indent=2, sort_keys=True))
    return 0


def setup_config_parser(subparsers) -> None:
    """Add config subcommands to parser."""
    cfg = subparsers.add_parser("config", help="Config commands")
    cfg_sub = cfg.add_subparsers(dest="cfg_cmd")

    cfg_print = cfg_sub.add_parser("print", help="Print effective config")
    cfg_print.set_defaults(func=print_config)
