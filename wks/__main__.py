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
try:
    from .config import apply_similarity_mongo_defaults, mongo_settings
    from .similarity import SimilarityDB
    from .cli import _ensure_mongo_running
except Exception:
    SimilarityDB = None
    _ensure_mongo_running = None

def _expand(p: str) -> Path:
    return Path(p).expanduser()

if __name__ == "__main__":
    # Load config from ~/.wks/config.json
    config_path = Path.home() / WKS_HOME_EXT / "config.json"
    config = {}
    try:
        if config_path.exists():
            config = json.load(open(config_path, "r"))
    except Exception as e:
        print(f"Warning: failed to load config {config_path}: {e}")

    if "vault_path" not in config:
        print(f"Fatal: 'vault_path' is required in {WKS_HOME_DISPLAY}/config.json")
        raise SystemExit(2)
    vault_path = _expand(config.get("vault_path"))
    mongo_cfg = mongo_settings(config)
    if _ensure_mongo_running is not None:
        try:
            _ensure_mongo_running(mongo_cfg['uri'], record_start=True)
        except SystemExit:
            raise
        except Exception:
            pass

    monitor_cfg = config.get("monitor", {})
    # Require explicit monitor.*
    missing = []
    for key in ["include_paths", "exclude_paths", "ignore_dirnames", "ignore_globs", "state_file"]:
        if key not in monitor_cfg:
            missing.append(f"monitor.{key}")
    if missing:
        print("Fatal: missing required config keys: " + ", ".join(missing))
        raise SystemExit(2)

    include_paths = [_expand(p) for p in monitor_cfg.get("include_paths")]
    exclude_paths = [_expand(p) for p in monitor_cfg.get("exclude_paths")]
    ignore_dirnames = set(monitor_cfg.get("ignore_dirnames"))
    ignore_patterns = set()  # deprecated
    ignore_globs = list(monitor_cfg.get("ignore_globs"))
    state_file = _expand(monitor_cfg.get("state_file"))

    # Require obsidian.base_dir
    obsidian_cfg = config.get("obsidian", {})
    base_dir = obsidian_cfg.get("base_dir")
    if not base_dir:
        print(f"Fatal: 'obsidian.base_dir' is required in {WKS_HOME_DISPLAY}/config.json (e.g., 'WKS')")
        raise SystemExit(2)

    # Require obsidian.base_dir and explicit logging caps/widths
    obsidian_cfg = config.get("obsidian", {})
    base_dir = obsidian_cfg.get("base_dir")
    if not base_dir:
        print("Fatal: 'obsidian.base_dir' is required in ~/.wks/config.json (e.g., 'WKS')")
        raise SystemExit(2)
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
        fs_rate_short_window_secs=fs_short_window,
        fs_rate_long_window_secs=fs_long_window,
        fs_rate_short_weight=fs_short_weight,
        fs_rate_long_weight=fs_long_weight,
    )

    # Similarity (explicit)
    mongo_cfg = mongo_settings(config)
    sim_cfg_raw = config.get("similarity")
    if sim_cfg_raw is None or "enabled" not in sim_cfg_raw:
        print(f"Fatal: 'similarity.enabled' is required (true/false) in {WKS_HOME_DISPLAY}/config.json")
        raise SystemExit(2)
    if sim_cfg_raw.get("enabled"):
        if SimilarityDB is None:
            print("Fatal: similarity enabled but SimilarityDB not available")
            raise SystemExit(2)
        sim_cfg = apply_similarity_mongo_defaults(sim_cfg_raw, mongo_cfg)
        required = ["mongo_uri", "database", "collection", "model", "include_extensions", "min_chars", "max_chars", "chunk_chars", "chunk_overlap"]
        missing = [k for k in required if k not in sim_cfg]
        if missing:
            print("Fatal: missing required similarity keys: " + ", ".join([f"similarity.{k}" for k in missing]))
            raise SystemExit(2)
        model = sim_cfg["model"]
        mongo_uri = sim_cfg["mongo_uri"]
        database = sim_cfg["database"]
        collection = sim_cfg["collection"]
        include_exts = set([e.lower() for e in sim_cfg["include_extensions"]])
        min_chars = int(sim_cfg["min_chars"])
        max_chars = int(sim_cfg["max_chars"])
        chunk_chars = int(sim_cfg["chunk_chars"])
        chunk_overlap = int(sim_cfg["chunk_overlap"])
        # Extraction config (explicit)
        extract_cfg = config.get("extract")
        if extract_cfg is None or 'engine' not in extract_cfg or 'ocr' not in extract_cfg or 'timeout_secs' not in extract_cfg:
            print("Fatal: 'extract.engine', 'extract.ocr', and 'extract.timeout_secs' are required in config")
            raise SystemExit(2)
        def _build_simdb():
            return SimilarityDB(
                database_name=database,
                collection_name=collection,
                mongo_uri=mongo_uri,
                model_name=model,
                model_path=sim_cfg.get("model_path"),
                offline=bool(sim_cfg.get("offline", False)),
                min_chars=min_chars,
                max_chars=max_chars,
                chunk_chars=chunk_chars,
                chunk_overlap=chunk_overlap,
                extract_engine=extract_cfg['engine'],
                extract_ocr=bool(extract_cfg['ocr']),
                extract_timeout_secs=int(extract_cfg['timeout_secs']),
                extract_options=dict(extract_cfg.get('options') or {}),
                write_extension=extract_cfg.get('write_extension'),
            )
        try:
            simdb = _build_simdb()
        except Exception as e:
            # Best-effort: if using localhost and mongod exists, try to start it
            try:
                if str(mongo_uri).startswith("mongodb://localhost:") and shutil.which("mongod"):
                    dbroot = Path.home() / WKS_HOME_EXT / "mongodb"
                    dbpath = dbroot / "db"
                    logfile = dbroot / "mongod.log"
                    dbpath.mkdir(parents=True, exist_ok=True)
                    subprocess.check_call([
                        "mongod", "--dbpath", str(dbpath), "--logpath", str(logfile),
                        "--fork", "--bind_ip", "127.0.0.1", "--port", str(mongo_uri.split(":")[-1].split("/")[0])
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(0.3)
                    simdb = _build_simdb()
                else:
                    raise
            except Exception as e2:
                print(f"Fatal: failed to initialize similarity DB: {e2}")
                raise SystemExit(2)
        daemon.similarity = simdb
        daemon.similarity_extensions = include_exts
        daemon.similarity_min_chars = min_chars
        print("Similarity indexing enabled.")

    # base_dir is set via constructor; no defaults applied

    print("Starting WKS daemon...")
    print("Press Ctrl+C to stop")

    try:
        daemon.run()
    except KeyboardInterrupt:
        print("\nStopping...")
