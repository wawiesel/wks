import os
from pathlib import Path

from ..monitor.RemoteConfig import RemoteMapping


def detect_remote_mappings(home_dir: Path | None = None) -> list[RemoteMapping]:
    """Detect remote folders (OneDrive/SharePoint) in the user's home directory.

    Args:
        home_dir: Optional path to home directory. Defaults to Path.home().

    Returns:
        List of discovered RemoteMapping objects.
    """
    if home_dir is None:
        home_dir = Path.home()

    mappings: list[RemoteMapping] = []

    try:
        # Scan immediate subdirectories of home
        with os.scandir(home_dir) as entries:
            for entry in entries:
                if not entry.is_dir():
                    continue

                name = entry.name

                # Check for OneDrive
                if name.startswith("OneDrive"):
                    remote_uri = "https://example-my.sharepoint.com/personal/user_example_com/Documents"
                    if " - " in name:
                        tenant = name.split(" - ")[1].replace(" ", "").lower()
                        remote_uri = f"https://{tenant}-my.sharepoint.com/personal/user_{tenant}_com/Documents"

                    mappings.append(
                        RemoteMapping(
                            local_path=str(Path(entry.path).resolve()), remote_uri=remote_uri, type="onedrive"
                        )
                    )

                # Check for SharePoint
                elif name.startswith("SharePoint") or "SharePoint" in name:
                    mappings.append(
                        RemoteMapping(
                            local_path=str(Path(entry.path).resolve()),
                            remote_uri="https://example.sharepoint.com/sites/SiteName/Shared%20Documents",
                            type="sharepoint",
                        )
                    )

    except Exception:
        pass

    return mappings
