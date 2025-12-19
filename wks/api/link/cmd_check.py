"""Link check API command."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from wks.utils.uri_utils import path_to_uri, uri_to_path

from ..config.WKSConfig import WKSConfig
from ..monitor.explain_path import explain_path
from ..StageResult import StageResult
from ..vault._obsidian._LinkResolver import _LinkResolver
from ..vault.Vault import Vault
from . import LinkCheckOutput

# Accessing private module as we reuse the logic
from ._parsers import get_parser
from .cloud_resolver import resolve_cloud_url


def cmd_check(path: str, parser: str | None = None) -> StageResult:
    """Check if file is monitored and extract links."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Loading configuration...")
        config: Any = WKSConfig.load()
        monitor_cfg = config.monitor
        vault_cfg = config.vault

        yield (0.2, "Resolving path...")
        file_path = Path(path).expanduser().resolve()

        if not file_path.exists():
            result_obj.output = LinkCheckOutput(
                path=str(file_path),
                is_monitored=False,
                links=[],
                errors=["File does not exist"],
            ).model_dump(mode="python")
            result_obj.result = f"File not found: {path}"
            result_obj.success = False
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

            # Resolve links
            links_out = []
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
            resolver = None
            vault_root = None
            try:
                with Vault(vault_cfg) as vault:
                    resolver = _LinkResolver(vault.vault_path, vault.links_dir)
                    vault_root = vault.vault_path
            except Exception:
                pass  # Vault might not be configured or file is outside vault

            # Determine from_uri: use vault:/// if within vault, otherwise file://
            if vault_root and file_path.is_relative_to(vault_root):
                relative_path = file_path.relative_to(vault_root)
                from_uri = f"vault:///{relative_path}"
            else:
                from_uri = path_to_uri(file_path)

            for ref in link_refs:
                to_uri = ref.raw_target

                # Attempt resolution for WikiLinks or relative paths
                if ref.link_type == "wikilink" and resolver:
                    metadata = resolver.resolve(ref.raw_target)
                    to_uri = metadata.target_uri
                elif "://" not in ref.raw_target:
                    # Assume relative to file or absolute path
                    # If it looks like a path
                    pass  # TODO: Implement robust relative path resolution outside vault

                # Calculate cloud_url
                cloud_url = None
                target_path_obj = None
                try:
                    if to_uri.startswith("vault:///"):
                        if vault_root:
                            # Strip "vault:///" and join with vault_root
                            rel_part = to_uri[11:]
                            target_path_obj = vault_root / rel_part
                    elif to_uri.startswith("file://"):
                        target_path_obj = uri_to_path(to_uri)

                    if target_path_obj:
                        cloud_url = resolve_cloud_url(target_path_obj, config.cloud)
                except Exception:
                    # Failures in cloud resolution/path checks shouldn't fail the link check
                    pass

                links_out.append(
                    {
                        "from_uri": from_uri,
                        "to_uri": to_uri,
                        "line_number": ref.line_number,
                        "column_number": ref.column_number,
                        "parser": parser_name,
                        "name": ref.alias,
                        "cloud_url": cloud_url,
                    }
                )

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

    return StageResult(announce=f"Checking links in {path}...", progress_callback=do_work)
