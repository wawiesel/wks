"""
Entry point for running wks.daemon as a module.

Loads ~/.wks/config.json to configure include/exclude paths.
"""

import json
import shutil
import subprocess
import time
from pathlib import Path

from .constants import WKS_HOME_EXT, WKS_HOME_DISPLAY
from .daemon import WKSDaemon
from .mongoctl import ensure_mongo_running
from .dbmeta import resolve_db_compatibility, IncompatibleDatabase
from .config import load_config
from .config_validator import validate_and_raise, ConfigValidationError
from .utils import get_package_version, expand_path
try:
    from .config import mongo_settings
    from .similarity import build_similarity_from_config
except Exception:
    build_similarity_from_config = None  # type: ignore

if __name__ == "__main__":
    # Load and validate config
    config = load_config()
    try:
        validate_and_raise(config)
    except ConfigValidationError as e:
        print(str(e))
        raise SystemExit(2)

    vault_path = expand_path(config.get("vault_path"))
    mongo_cfg = mongo_settings(config)
    space_compat_tag, time_compat_tag = resolve_db_compatibility(config)
    ensure_mongo_running(mongo_cfg['uri'], record_start=True)

    monitor_cfg = config.get("monitor", {})
    include_paths = [expand_path(p) for p in monitor_cfg.get("include_paths")]
    exclude_paths = [expand_path(p) for p in monitor_cfg.get("exclude_paths")]
    ignore_dirnames = set(monitor_cfg.get("ignore_dirnames"))
    ignore_patterns = set()  # deprecated
    ignore_globs = list(monitor_cfg.get("ignore_globs"))
    state_file = expand_path(monitor_cfg.get("state_file"))

    obsidian_cfg = config.get("obsidian", {})
    base_dir = obsidian_cfg.get("base_dir")
    # Explicit obsidian logging settings
    for k in ["log_max_entries", "active_files_max_rows", "source_max_chars", "destination_max_chars", "docs_keep"]:
        if k not in obsidian_cfg:
            print(f"Fatal: missing required config key: obsidian.{k}")
            raise SystemExit(2)
    log_max_entries = int(obsidian_cfg["log_max_entries"])
    active_rows = int(obsidian_cfg["active_files_max_rows"])
    src_max = int(obsidian_cfg["source_max_chars"])
    dst_max = int(obsidian_cfg["destination_max_chars"])
    docs_keep = int(obsidian_cfg["docs_keep"])

    metrics_cfg = config.get("metrics") or {}
    fs_short_window = float(metrics_cfg.get("fs_rate_short_window_secs", 10))
    fs_long_window = float(metrics_cfg.get("fs_rate_long_window_secs", 600))
    fs_short_weight = float(metrics_cfg.get("fs_rate_short_weight", 0.8))
    fs_long_weight = float(metrics_cfg.get("fs_rate_long_weight", 0.2))

    daemon = WKSDaemon(
        vault_path=vault_path,
        base_dir=base_dir,
        obsidian_log_max_entries=log_max_entries,
        obsidian_active_files_max_rows=active_rows,
        obsidian_source_max_chars=src_max,
        obsidian_destination_max_chars=dst_max,
        obsidian_docs_keep=docs_keep,
        monitor_paths=include_paths,
        state_file=state_file,
        ignore_dirnames=ignore_dirnames,
        exclude_paths=exclude_paths,
        ignore_patterns=ignore_patterns,
        ignore_globs=ignore_globs,
        mongo_uri=mongo_cfg.get("uri"),
        fs_rate_short_window_secs=fs_short_window,
        fs_rate_long_window_secs=fs_long_window,
        fs_rate_short_weight=fs_short_weight,
        fs_rate_long_weight=fs_long_weight,
    )

    # Similarity (explicit)
    sim_cfg_raw = config.get("similarity")
    if sim_cfg_raw is None or "enabled" not in sim_cfg_raw:
        print(f"Fatal: 'similarity.enabled' is required (true/false) in {WKS_HOME_DISPLAY}/config.json")
        raise SystemExit(2)
    if sim_cfg_raw.get("enabled"):
        if build_similarity_from_config is None:
            print("Fatal: similarity enabled but SimilarityDB not available")
            raise SystemExit(2)
        try:
            simdb, sim_cfg = build_similarity_from_config(
                config,
                require_enabled=True,
                compatibility_tag=space_compat_tag,
                product_version=get_package_version(),
            )
        except IncompatibleDatabase as exc:
            print(exc)
            raise SystemExit(2)
        except Exception as e:
            print(f"Fatal: failed to initialize similarity DB: {e}")
            raise SystemExit(2)
        if not simdb or not sim_cfg:
            print("Fatal: similarity initialization failed")
            raise SystemExit(2)
        daemon.similarity = simdb
        daemon.similarity_extensions = set([e.lower() for e in sim_cfg["include_extensions"]])
        daemon.similarity_min_chars = int(sim_cfg["min_chars"])
        print("Similarity indexing enabled.")

    # base_dir is set via constructor; no defaults applied

    print("Starting WKS daemon...")
    print("Press Ctrl+C to stop")

    try:
        daemon.run()
    except KeyboardInterrupt:
        print("\nStopping...")
