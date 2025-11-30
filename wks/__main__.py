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
from .config import WKSConfig, ConfigError
from .utils import get_package_version, expand_path
from .monitor import MonitorConfig
from .monitor_rules import MonitorRules

if __name__ == "__main__":
    # Load and validate config
    try:
        config = WKSConfig.load()
    except ConfigError as e:
        print(str(e))
        raise SystemExit(2)

    # Vault config
    vault_path = config.vault.base_dir
    base_dir = config.vault.wks_dir
    
    # Ensure Mongo is running
    ensure_mongo_running(config.mongo.uri, record_start=True)

    # Monitor config
    monitor_cfg_obj = config.monitor
    monitor_rules = MonitorRules.from_config(monitor_cfg_obj)
    include_paths = [expand_path(p) for p in monitor_cfg_obj.include_paths]

    # Metrics config
    metrics = config.metrics

    daemon = WKSDaemon(
        config=config,
        vault_path=vault_path,
        base_dir=base_dir,
        monitor_paths=include_paths,
        monitor_rules=monitor_rules,
        fs_rate_short_window_secs=metrics.fs_rate_short_window_secs,
        fs_rate_long_window_secs=metrics.fs_rate_long_window_secs,
        fs_rate_short_weight=metrics.fs_rate_short_weight,
        fs_rate_long_weight=metrics.fs_rate_long_weight,
    )

    print("Starting WKS daemon...")
    print("Press Ctrl+C to stop")

    try:
        daemon.run()
    except KeyboardInterrupt:
        print("\nStopping...")
