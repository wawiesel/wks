"""Child process entry point for daemon (invoked via subprocess)."""

import sys


def main() -> None:
    """Parse args and run the daemon child loop."""
    if len(sys.argv) != 8:
        sys.exit(1)

    home_dir = sys.argv[1]
    log_path = sys.argv[2]
    paths_json = sys.argv[3]
    restrict_val = sys.argv[4]
    sync_interval = float(sys.argv[5])
    status_path = sys.argv[6]
    lock_path = sys.argv[7]

    import json

    paths = json.loads(paths_json)

    from .Daemon import _child_main

    _child_main(
        home_dir=home_dir,
        log_path=log_path,
        paths=paths,
        restrict_val=restrict_val,
        sync_interval=sync_interval,
        status_path=status_path,
        lock_path=lock_path,
    )


if __name__ == "__main__":
    main()
