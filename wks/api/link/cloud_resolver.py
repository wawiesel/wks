from pathlib import Path

from wks.api.config.CloudConfig import CloudConfig


def resolve_cloud_url(path: Path | str, cloud_config: CloudConfig) -> str | None:
    """Resolve a local path to a cloud URL if a mapping exists.

    Args:
        path: Local path (Path object or string).
        cloud_config: Configuration containing mappings.

    Returns:
        Cloud URL string or None if no mapping matches.
    """
    try:
        resolved_path = Path(path).expanduser().resolve()
    except Exception:
        # If path resolution fails (e.g. non-existent path that cannot be resolved), return None
        return None

    for mapping in cloud_config.mappings:
        try:
            # Expand user in config path
            root = Path(mapping.local_path).expanduser().resolve()

            if resolved_path.is_relative_to(root):
                rel_path = resolved_path.relative_to(root)
                # Normalize to URL separators (forward slash)
                rel_str = str(rel_path).replace("\\", "/")

                base = mapping.remote_url.rstrip("/")
                # Join base and relative path
                # simple string concatenation is used as requested for MVP
                return f"{base}/{rel_str}"
        except ValueError:
            # is_relative_to might raise or other path issues
            continue

    return None
