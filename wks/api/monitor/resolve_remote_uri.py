from wks.api.config.normalize_path import normalize_path
from wks.api.config.URI import URI
from wks.api.monitor.RemoteConfig import RemoteConfig


def resolve_remote_uri(uri: URI, remote_config: RemoteConfig) -> URI | None:
    if not isinstance(uri, URI):
        raise TypeError(f"uri must be URI, got {type(uri).__name__}")
    if not isinstance(remote_config, RemoteConfig):
        raise TypeError(f"remote_config must be RemoteConfig, got {type(remote_config).__name__}")

    if not uri.is_file:
        return None

    resolved_path = uri.path

    for mapping in remote_config.mappings:
        try:
            root = normalize_path(mapping.local_path)

            if resolved_path.is_relative_to(root):
                rel_path = resolved_path.relative_to(root)
                rel_str = str(rel_path).replace("\\", "/")

                base = mapping.remote_uri.rstrip("/")
                remote_uri_str = f"{base}/{rel_str}"
                return URI(remote_uri_str)
        except ValueError:
            continue

    return None
