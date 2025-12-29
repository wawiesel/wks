from pathlib import Path

from wks.api.monitor.RemoteConfig import RemoteConfig
from wks.utils.normalize_path import normalize_path


def resolve_remote_uri(path: Path | str, remote_config: RemoteConfig) -> str | None:
    """Resolve a local path to a remote URI if a mapping exists.

    Args:
        path: Local path (Path object or string).
        remote_config: Configuration containing mappings.

    Returns:
        Remote URI string or None if no mapping matches.
    """
    try:
        resolved_path = normalize_path(path)
    except Exception:
        # If path resolution fails, return None
        return None

    for mapping in remote_config.mappings:
        try:
            # Expand user in config path
            root = normalize_path(mapping.local_path)

            if resolved_path.is_relative_to(root):
                rel_path = resolved_path.relative_to(root)
                # Normalize to URL separators (forward slash)
                rel_str = str(rel_path).replace("\\", "/")

                base = mapping.remote_uri.rstrip("/")
                # Join base and relative path
                return f"{base}/{rel_str}"
        except ValueError:
            continue

    return None
