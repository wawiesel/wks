"""Run daemon (foreground blocking)."""

from pathlib import Path

from .Daemon import Daemon


def cmd_run(restrict_dir: Path | None = None) -> None:
    """Run the daemon watcher in the foreground.

    Args:
        restrict_dir: Optional directory to restrict monitoring to.
    """
    daemon = Daemon()
    try:
        daemon.run_foreground(restrict_dir=restrict_dir)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        exit(1)
    except KeyboardInterrupt:
        # Allow clean exit on Ctrl+C
        pass
