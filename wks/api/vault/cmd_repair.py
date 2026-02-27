"""Vault repair API function.

Find broken _links/ symlinks and attempt to repair them by searching
the monitor database for a matching checksum at a new path.

Matches CLI: wksc vault repair, MCP: wksm_vault_repair
"""

from collections.abc import Iterator
from pathlib import Path

from ..config.StageResult import StageResult
from . import VaultRepairOutput


def cmd_repair() -> StageResult:
    """Find and repair broken _links/ symlinks.

    For each broken symlink, looks up the original file's checksum in the
    monitor (nodes) database, then searches for a file with the same checksum
    at a different path. If found, updates the symlink, rewrites wiki links
    in vault markdown files, and updates the edges database.

    Returns:
        StageResult with repair results.
    """

    def _build_result(
        result_obj: StageResult,
        success: bool,
        message: str,
        fixed: list[dict],
        unresolved: list[dict],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        result_obj.output = VaultRepairOutput(
            errors=errors,
            warnings=warnings,
            fixed=fixed,
            unresolved=unresolved,
            fixed_count=len(fixed),
            unresolved_count=len(unresolved),
            success=success,
        ).model_dump(mode="python")
        result_obj.result = message
        result_obj.success = success

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ..config.URI import URI
        from ..config.WKSConfig import WKSConfig
        from ..database.Database import Database
        from .Vault import Vault

        errors: list[str] = []
        warnings: list[str] = []
        fixed: list[dict] = []
        unresolved: list[dict] = []

        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()

        yield (0.2, "Finding broken symlinks...")
        with Vault(config.vault) as vault:
            broken = vault.find_broken_links()

            if not broken:
                _build_result(
                    result_obj,
                    success=True,
                    message="No broken symlinks found",
                    fixed=fixed,
                    unresolved=unresolved,
                    errors=errors,
                    warnings=warnings,
                )
                return

            yield (0.3, f"Checking {len(broken)} broken symlinks...")

            for i, symlink_path in enumerate(broken):
                progress = 0.3 + 0.6 * (i / len(broken))
                yield (progress, f"Repairing {i + 1}/{len(broken)}...")

                # Extract the old absolute target from the symlink path convention.
                # Symlink path: {vault}/_links/{machine}/{abs_path_stripped}
                # The target the symlink used to point to: /{abs_path_stripped}
                try:
                    rel_to_links = symlink_path.relative_to(vault.links_dir)
                except ValueError:
                    errors.append(f"Symlink not under _links/: {symlink_path}")
                    continue

                # First component is machine name, rest is the absolute path
                parts = rel_to_links.parts
                if len(parts) < 2:
                    errors.append(f"Unexpected symlink path structure: {symlink_path}")
                    continue

                old_abs_path = Path("/") / Path(*parts[1:])
                old_uri_str = str(URI.from_path(old_abs_path))

                # Look up checksum in nodes database
                checksum = None
                try:
                    with Database(config.database, "nodes") as db:
                        doc = db.find_one(
                            {"local_uri": old_uri_str},
                            {"checksum": 1},
                        )
                        if doc:
                            checksum = doc.get("checksum")
                except Exception as exc:
                    warnings.append(f"DB lookup failed for {old_uri_str}: {exc}")

                if not checksum:
                    unresolved.append(
                        {
                            "symlink": str(symlink_path.relative_to(vault.vault_path)),
                            "old_path": str(old_abs_path),
                            "reason": "no checksum in monitor DB",
                        }
                    )
                    continue

                # Search for a file with the same checksum at a different path
                new_path = None
                try:
                    with Database(config.database, "nodes") as db:
                        cursor = db.find(
                            {"checksum": checksum, "local_uri": {"$ne": old_uri_str}},
                            {"local_uri": 1},
                        )
                        for match in cursor:
                            candidate_uri = URI(match["local_uri"])
                            candidate_path = candidate_uri.path
                            if candidate_path.exists():
                                new_path = candidate_path
                                break
                except Exception as exc:
                    warnings.append(f"DB search failed for checksum {checksum[:12]}...: {exc}")

                if not new_path:
                    unresolved.append(
                        {
                            "symlink": str(symlink_path.relative_to(vault.vault_path)),
                            "old_path": str(old_abs_path),
                            "reason": "no matching file found in monitor DB",
                        }
                    )
                    continue

                # Repair: update symlink, rewrite wiki links, update edges
                result = vault.update_link_for_move(old_abs_path, new_path)
                if not result:
                    unresolved.append(
                        {
                            "symlink": str(symlink_path.relative_to(vault.vault_path)),
                            "old_path": str(old_abs_path),
                            "reason": "symlink update failed",
                        }
                    )
                    continue

                old_vault_rel, new_vault_rel = result
                files_rewritten = vault.rewrite_wiki_links(old_vault_rel, new_vault_rel)
                edges_updated = vault.update_edges_for_move(
                    old_abs_path,
                    new_path,
                    old_vault_rel,
                    new_vault_rel,
                )

                fixed.append(
                    {
                        "old_path": str(old_abs_path),
                        "new_path": str(new_path),
                        "old_link": old_vault_rel,
                        "new_link": new_vault_rel,
                        "files_rewritten": files_rewritten,
                        "edges_updated": edges_updated,
                    }
                )

        yield (1.0, "Complete")
        message_parts = []
        if fixed:
            message_parts.append(f"{len(fixed)} repaired")
        if unresolved:
            message_parts.append(f"{len(unresolved)} unresolved")
        message = ", ".join(message_parts) if message_parts else "No broken symlinks"

        _build_result(
            result_obj,
            success=True,
            message=message,
            fixed=fixed,
            unresolved=unresolved,
            errors=errors,
            warnings=warnings,
        )

    return StageResult(
        announce="Repairing broken vault symlinks...",
        progress_callback=do_work,
    )
