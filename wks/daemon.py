"""
WKS daemon for monitoring file system and updating Obsidian.
"""

import time
from pathlib import Path
from typing import Optional
from .monitor import start_monitoring
from .obsidian import ObsidianVault


class WKSDaemon:
    """Daemon that monitors filesystem and updates Obsidian vault."""

    def __init__(
        self,
        vault_path: Path,
        monitor_paths: list[Path],
        state_file: Optional[Path] = None
    ):
        """
        Initialize WKS daemon.

        Args:
            vault_path: Path to Obsidian vault
            monitor_paths: List of paths to monitor
            state_file: Path to monitoring state file
        """
        self.vault = ObsidianVault(vault_path)
        self.monitor_paths = monitor_paths
        self.state_file = state_file or Path.home() / ".wks" / "monitor_state.json"
        self.observer = None

    def on_file_change(self, event_type: str, path_info):
        """
        Callback when a file changes.

        Args:
            event_type: Type of event (created, modified, moved, deleted)
            path_info: Path string for most events, or (src, dest) tuple for moves
        """
        # Handle move events specially
        if event_type == "moved":
            src_path, dest_path = path_info
            self.vault.log_file_operation("moved", Path(src_path), Path(dest_path))
            return

        # Regular events
        path = Path(path_info)

        # Log to Obsidian
        if event_type in ["created", "modified", "deleted"]:
            self.vault.log_file_operation(event_type, path)

        # Handle specific cases for non-move events
        if event_type == "created" and path_info and Path(path_info).is_dir():
            # New directory - check if it's a project
            p = Path(path_info)
            if p.parent == Path.home() and p.name.startswith("20"):
                # Looks like a project folder (YYYY-Name pattern)
                try:
                    self.vault.create_project_note(p, status="New")
                    self.vault.log_file_operation(
                        "created",
                        p,
                        details="Auto-created project note in Obsidian"
                    )
                except Exception as e:
                    print(f"Error creating project note: {e}")

    def start(self):
        """Start monitoring."""
        self.vault.ensure_structure()

        # Ignore common large directories
        ignore_dirs = {
            'Library',
            'Applications',
            '.Trash',
            '.cache',
            'Cache',
            'Caches',
            'node_modules',
            'venv',
            '.venv',
            '__pycache__',
            'build',
            'dist',
        }

        self.observer = start_monitoring(
            directories=self.monitor_paths,
            state_file=self.state_file,
            on_change=self.on_file_change,
            ignore_dirs=ignore_dirs
        )

        print(f"WKS daemon started, monitoring: {[str(p) for p in self.monitor_paths]}")

    def stop(self):
        """Stop monitoring."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            print("WKS daemon stopped")

    def run(self):
        """Run the daemon (blocking)."""
        self.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()


if __name__ == "__main__":
    import sys

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
        sys.exit(0)
