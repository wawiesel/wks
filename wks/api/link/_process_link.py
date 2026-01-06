"""Build a single link record for link check output."""

from wks.api.config.URI import URI
from wks.api.monitor.resolve_remote_uri import resolve_remote_uri


def _process_link(ref, from_uri, to_uri, vault_root, monitor_cfg, parser_name, from_remote_uri, links_out):
    """Append a normalized link record to links_out."""
    # Calculate remote_uri for target
    remote_uri = None
    target_path_obj = None
    try:
        if to_uri.startswith("vault:///"):
            if vault_root:
                # Strip "vault:///" and join with vault_root
                rel_part = to_uri[11:]
                target_path_obj = vault_root / rel_part
        elif to_uri.startswith("file://"):
            target_path_obj = URI(to_uri).path

        if target_path_obj:
            target_uri = URI.from_path(target_path_obj)
            remote_uri_obj = resolve_remote_uri(target_uri, monitor_cfg.remote)
            remote_uri = str(remote_uri_obj) if remote_uri_obj else None
    except Exception:
        # Failures in remote resolution checks shouldn't fail the link check
        pass

    # Convert from_remote_uri to string if it's a URI object
    from wks.api.config.uri_to_string import uri_to_string

    from_remote_uri_str = uri_to_string(from_remote_uri)

    links_out.append(
        {
            "from_local_uri": from_uri,
            "from_remote_uri": from_remote_uri_str,
            "to_local_uri": to_uri,
            "to_remote_uri": remote_uri,
            "line_number": ref.line_number,
            "column_number": ref.column_number,
            "parser": parser_name,
            "name": ref.alias,
        }
    )
