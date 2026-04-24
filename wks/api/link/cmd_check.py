from collections.abc import Iterator
from typing import Any

from ..config._ensure_arg_uri import _ensure_arg_uri
from ..config.StageResult import StageResult
from ..config.URI import URI
from ..config.WKSConfig import WKSConfig
from ..monitor.explain_path import explain_path
from ..monitor.resolve_remote_uri import resolve_remote_uri
from ..vault.Vault import Vault
from . import LinkCheckOutput
from ._parsers import get_parser
from ._process_link import _process_link


def cmd_check(uri: URI, parser: str | None = None) -> StageResult:
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
        try:
            parser_instance = get_parser(parser, file_path)
            parser_name = getattr(parser_instance, "name", parser or "auto")

            try:
                text = file_path.read_text(encoding="utf-8")
            except Exception as exc:
                raise ValueError(f"Cannot read file: {exc}") from exc

            link_refs = parser_instance.parse(text)

            links_out: list[dict[str, Any]] = []

            vault_root = None
            to_uri = None
            try:
                with Vault(vault_cfg) as vault:
                    vault_root = vault.vault_path

                    if vault_root and file_path.is_relative_to(vault_root):
                        relative_path = file_path.relative_to(vault_root)
                        from_uri_str = f"vault:///{relative_path}"
                    else:
                        from_uri_str = str(URI.from_path(file_path))

                    from_uri_obj = URI.from_path(file_path)
                    from_remote_uri_obj = resolve_remote_uri(from_uri_obj, monitor_cfg.remote)
                    from_remote_uri = from_remote_uri_obj  # Pass URI object to _process_link

                    for ref in link_refs:
                        to_uri = ref.raw_target
                        if ref.link_type == "wikilink":
                            metadata = vault.resolve_link(ref.raw_target)
                            to_uri = metadata.target_uri
                        elif "://" not in ref.raw_target:
                            resolved_path = file_path.parent / ref.raw_target
                            to_uri = str(URI.from_path(resolved_path))

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
