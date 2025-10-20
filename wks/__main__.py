"""
Entry point for running wks.daemon as a module.

Loads ~/.wks/config.json to configure include/exclude paths.
"""

import json
import shutil
import subprocess
import time
from pathlib import Path
from .daemon import WKSDaemon
try:
    from .similarity import SimilarityDB
except Exception:
    SimilarityDB = None

def _expand(p: str) -> Path:
    return Path(p).expanduser()

if __name__ == "__main__":
    # Load config from ~/.wks/config.json
    config_path = Path.home() / ".wks" / "config.json"
    config = {}
    try:
        if config_path.exists():
            config = json.load(open(config_path, "r"))
    except Exception as e:
        print(f"Warning: failed to load config {config_path}: {e}")

    vault_path = _expand(config.get("vault_path", "~/obsidian"))

    monitor_cfg = config.get("monitor", {})
    include_paths = [
        _expand(p) for p in monitor_cfg.get("include_paths", [str(Path.home())])
    ]
    exclude_paths = [
        _expand(p) for p in monitor_cfg.get("exclude_paths", ["~/Library", "~/obsidian", "~/.wks"])
    ]
    ignore_dirnames = set(monitor_cfg.get("ignore_dirnames", [
        'Applications', '.Trash', '.cache', 'Cache', 'Caches',
        'node_modules', 'venv', '.venv', '__pycache__', 'build', 'dist'
    ]))
    ignore_patterns = set(monitor_cfg.get("ignore_patterns", [
        '.git', '__pycache__', '.DS_Store', 'venv', '.venv', 'node_modules'
    ]))
    ignore_globs = list(monitor_cfg.get("ignore_globs", []))
    state_file = _expand(monitor_cfg.get("state_file", str(Path.home() / ".wks" / "monitor_state.json")))

    daemon = WKSDaemon(
        vault_path=vault_path,
        monitor_paths=include_paths,
        state_file=state_file,
        ignore_dirnames=ignore_dirnames,
        exclude_paths=exclude_paths,
        ignore_patterns=ignore_patterns,
        ignore_globs=ignore_globs,
    )

    # Similarity (optional)
    sim_cfg = config.get("similarity", {})
    if sim_cfg.get("enabled", True) and SimilarityDB is not None:
        try:
            model = sim_cfg.get("model", 'all-MiniLM-L6-v2')
            mongo_uri = sim_cfg.get("mongo_uri", 'mongodb://localhost:27027/')
            database = sim_cfg.get("database", 'wks_similarity')
            collection = sim_cfg.get("collection", 'file_embeddings')
            # If include_extensions omitted or empty, index any file with readable text
            include_exts = set([e.lower() for e in sim_cfg.get("include_extensions", [])])
            min_chars = int(sim_cfg.get("min_chars", 10))
            def _init_simdb():
                max_chars = int(sim_cfg.get("max_chars", 200000))
                chunk_chars = int(sim_cfg.get("chunk_chars", 1500))
                chunk_overlap = int(sim_cfg.get("chunk_overlap", 200))
                return SimilarityDB(
                    database_name=database,
                    collection_name=collection,
                    mongo_uri=mongo_uri,
                    model_name=model,
                    max_chars=max_chars,
                    chunk_chars=chunk_chars,
                    chunk_overlap=chunk_overlap,
                )
            try:
                simdb = _init_simdb()
            except Exception as e:
                # Attempt to auto-start local mongod if URI matches our local default
                if mongo_uri.startswith("mongodb://localhost:27027") and shutil.which("mongod"):
                    dbroot = Path.home() / ".wks" / "mongodb"
                    dbpath = dbroot / "db"
                    logfile = dbroot / "mongod.log"
                    dbpath.mkdir(parents=True, exist_ok=True)
                    try:
                        subprocess.check_call([
                            "mongod", "--dbpath", str(dbpath), "--logpath", str(logfile),
                            "--fork", "--bind_ip", "127.0.0.1", "--port", "27027"
                        ])
                        time.sleep(0.5)
                        simdb = _init_simdb()
                        print("Auto-started local mongod for similarity indexing.")
                    except Exception as e2:
                        raise RuntimeError(f"Auto-start mongod failed: {e2}")
                else:
                    raise
            daemon.similarity = simdb
            daemon.similarity_extensions = include_exts
            daemon.similarity_min_chars = min_chars
            print("Similarity indexing enabled.")
        except Exception as e:
            print(f"Warning: failed to initialize similarity DB: {e}")

    # Configure Obsidian: base subdirectory and logging
    obsidian_cfg = config.get("obsidian", {})
    base_dir = obsidian_cfg.get("base_dir")
    if base_dir:
        try:
            daemon.vault.set_base_dir(base_dir)
        except Exception as e:
            print(f"Warning: failed to set Obsidian base_dir '{base_dir}': {e}")
    logs_cfg = obsidian_cfg.get("logs", {})
    weekly_logs = logs_cfg.get("weekly", False)
    logs_dirname = logs_cfg.get("dir", "Logs")
    max_entries = logs_cfg.get("max_entries", 500)
    source_max = logs_cfg.get("source_max", 40)
    dest_max = logs_cfg.get("destination_max", 40)
    active_cfg = obsidian_cfg.get("active", {})
    active_max_rows = active_cfg.get("max_rows", 50)
    try:
        daemon.vault.configure_logging(
            weekly_logs=weekly_logs,
            logs_dirname=logs_dirname,
            max_entries=max_entries,
            active_max_rows=active_max_rows,
            source_max_chars=source_max,
            destination_max_chars=dest_max,
        )
    except Exception as e:
        print(f"Warning: failed to configure Obsidian logging: {e}")

    print("Starting WKS daemon...")
    print("Press Ctrl+C to stop")

    try:
        daemon.run()
    except KeyboardInterrupt:
        print("\nStopping...")
