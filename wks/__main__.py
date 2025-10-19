"""
Entry point for running wks.daemon as a module.
"""

from pathlib import Path
from .daemon import WKSDaemon

if __name__ == "__main__":
    vault_path = Path.home() / "obsidian"
    monitor_paths = [
        Path.home(),  # Monitor home directory
    ]

    daemon = WKSDaemon(vault_path, monitor_paths)

    print("Starting WKS daemon...")
    print("Press Ctrl+C to stop")

    try:
        daemon.run()
    except KeyboardInterrupt:
        print("\nStopping...")
