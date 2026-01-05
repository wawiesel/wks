"""Link check API command."""

from collections.abc import Iterator
from typing import Any

from .._ensure_arg_uri import _ensure_arg_uri
from ..config.WKSConfig import WKSConfig
from ..monitor.explain_path import explain_path
from ..monitor.resolve_remote_uri import resolve_remote_uri
from ..StageResult import StageResult

# Accessing private module as we reuse the logic
from ..URI import URI
from ..vault.Vault import Vault
from . import LinkCheckOutput
from ._parsers import get_parser


def _process_link(ref, from_uri, to_uri, vault_root, monitor_cfg, parser_name, from_remote_uri, links_out):
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
    from wks.utils.uri_to_string import uri_to_string

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


# Accessing private module as we reuse the logic


def cmd_check(uri: URI, parser: str | None = None) -> StageResult:
    """Check if file is monitored and extract links."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Loading configuration...")
        config: Any = WKSConfig.load()
        monitor_cfg = config.monitor
        vault_cfg = config.vault

        yield (0.2, "Resolving path...")
        file_path = _ensure_arg_uri(uri, result_obj, LinkCheckOutput, is_monitored=False, links=[])
        if not file_path:
            return

        yield (0.3, "Checking monitor rules...")
        allowed, _ = explain_path(monitor_cfg, file_path)

        yield (0.5, "Scanning for links...")
        # Validate parser selection
        try:
            # Get appropriate parser
            parser_instance = get_parser(parser, file_path)
            parser_name = parser or "auto"

            # Read file content
            try:
                text = file_path.read_text(encoding="utf-8")
            except Exception as exc:
                raise ValueError(f"Cannot read file: {exc}") from exc

            # Parse links
            link_refs = parser_instance.parse(text)

            # Yield link results
            links_out: list[dict[str, Any]] = []
            # We need a resolver for WikiLinks (fuzzy matching)
            # Basic URLs (http/file) we can resolve directly
            # Ideally resolver should be decoupled from Vault too, but for now we reuse it if it's a vault path

            # Helper to resolve URI
            # Note: This is simplified. Proper resolution needs context (Vault/Root).
            # We'll use a temporary strategy:
            # 1. If absolute URL -> use as is
            # 2. If valid file path -> make URI
            # 3. If "fuzzy" (WikiLink) -> try vault resolver

            # Temporary resolver access
            # We keep vault open to use its resolve_link method
            vault_root = None
            to_uri = None
            try:
                with Vault(vault_cfg) as vault:
                    # Determine from_uri inside vault context if possible
                    # But path calculation only needs paths so we can do it before or inside

                    vault_root = vault.vault_path

                    # Determine from_uri: use vault:/// if within vault, otherwise file://
                    if vault_root and file_path.is_relative_to(vault_root):
                        relative_path = file_path.relative_to(vault_root)
                        from_uri_str = f"vault:///{relative_path}"
                    else:
                        from_uri_str = str(URI.from_path(file_path))

                    # Calculate from_remote_uri once
                    from_uri_obj = URI.from_path(file_path)
                    from_remote_uri_obj = resolve_remote_uri(from_uri_obj, monitor_cfg.remote)
                    from_remote_uri = from_remote_uri_obj  # Pass URI object to _process_link

                    for ref in link_refs:
                        to_uri = ref.raw_target
                        # Attempt resolution for WikiLinks
                        if ref.link_type == "wikilink":
                            metadata = vault.resolve_link(ref.raw_target)
                            to_uri = metadata.target_uri
                        elif "://" not in ref.raw_target:
                            # Relative path resolution not yet implemented
                            # But we should still cover this line
                            pass

                        _process_link(
                            ref,
                            from_uri_str,
                            to_uri,
                            vault_root,
                            monitor_cfg,
                            parser_name,
                            from_remote_uri,
                            links_out,
                        )

            except Exception:
                # Vault failed or not configured - fall back to basic processing
                from_uri_str = str(URI.from_path(file_path))
                from_uri_obj = URI.from_path(file_path)
                from_remote_uri_obj = resolve_remote_uri(from_uri_obj, monitor_cfg.remote)
                from_remote_uri = from_remote_uri_obj  # Pass URI object to _process_link
                for ref in link_refs:
                    _process_link(
                        ref,
                        from_uri_str,
                        ref.raw_target,
                        None,
                        monitor_cfg,
                        parser_name,
                        from_remote_uri,
                        links_out,
                    )

                # Status message and success
                pass

            errors = []
            if not allowed:
                errors.append("File is not in monitor allowed list")

            result_obj.output = LinkCheckOutput(
                path=str(file_path),
                is_monitored=allowed,
                links=links_out,
                errors=errors,
            ).model_dump(mode="python")

            status_msg = "Monitored" if allowed else "Not Monitored"
            result_obj.result = f"{status_msg}: Found {len(links_out)} links in {file_path.name}"
            result_obj.success = True

        except Exception as e:
            result_obj.output = LinkCheckOutput(
                path=str(file_path),
                is_monitored=allowed,
                links=[],
                errors=[str(e)],
            ).model_dump(mode="python")
            result_obj.result = f"Error scanning file: {e}"
            result_obj.success = False

    return StageResult(announce=f"Checking links in {uri}...", progress_callback=do_work)
