from wks.api.config.normalize_path import normalize_path
from wks.api.monitor.RemoteConfig import RemoteConfig
from wks.api.URI import URI


def resolve_remote_uri(uri: URI, remote_config: RemoteConfig) -> URI | None:
    """Resolve a local path to a remote URI if a mapping exists.

    Args:
        uri: Local file URI to resolve.
        remote_config: Configuration containing mappings.

    Returns:
        Remote URI object or None if no mapping matches.
    """
    # Validate arguments (fail fast to prevent hangs)
    if not isinstance(uri, URI):
        raise TypeError(f"uri must be URI, got {type(uri).__name__}")
    if not isinstance(remote_config, RemoteConfig):
        raise TypeError(f"remote_config must be RemoteConfig, got {type(remote_config).__name__}")

    # Only file:// URIs can be resolved
    if not uri.is_file:
        return None

    resolved_path = uri.path

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
                remote_uri_str = f"{base}/{rel_str}"
                return URI(remote_uri_str)
        except ValueError:
            continue

    return None
