"""Mv API function.

Move a file within monitored paths and update the database.
Matches CLI: wksc mv <source> <dest>, MCP: wksm_mv
"""

import re
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

from ..config.StageResult import StageResult
from ..config.URI import URI
from . import MvMvOutput

# Regex pattern for valid destination filenames
# Matches: YYYY-Title, YYYY_MM-Title, or YYYY_MM_DD-Title
# Where Title is underscore-separated words (e.g., My_Short_Title)
FILENAME_PATTERN = re.compile(
    r"^(\d{4})(?:_(\d{2})(?:_(\d{2}))?)?-([A-Z][A-Za-z0-9]*(?:_[A-Z][A-Za-z0-9]*)*)(\.[a-zA-Z0-9]+)?$"
)


def _is_valid_filename(filename: str) -> tuple[bool, str]:
    """Validate destination filename follows YYYY[-MM[-DD]]-Title format.

    Valid formats:
    - YYYY-Title_Here.ext
    - YYYY_MM-Title_Here.ext
    - YYYY_MM_DD-Title_Here.ext

    Returns:
        Tuple of (is_valid, error_message)
    """
    if FILENAME_PATTERN.match(filename):
        return True, ""

    return False, (
        f"Invalid filename '{filename}'. "
        "Must follow date-title format: YYYY-Title, YYYY_MM-Title, or YYYY_MM_DD-Title "
        "(e.g., 2026-My_Document.pdf, 2026_02-Project_Notes.txt)"
    )


def _is_git_tracked(path: Path) -> tuple[bool, str | None]:
    """Check if a file is tracked by git.

    Returns:
        Tuple of (is_tracked, git_root_path)
        git_root_path is the path to the git repo root if tracked, None otherwise
    """
    try:
        # Find the git root directory
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path.parent,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            # Not in a git repo
            return False, None

        git_root = result.stdout.strip()

        # Check if file is tracked
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(path)],
            cwd=git_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return True, git_root
        return False, None

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # git not available or other error - assume not tracked
        return False, None


def cmd(source: URI | str, dest: URI | str) -> StageResult:
    """Move a file within monitored paths.

    Args:
        source: URI of file to move (must exist and be monitored, or in always_allow_sources)
        dest: URI of destination (parent must be monitored, filename must follow date-title format)

    Rules:
        1. No overwriting - destination must not exist
        2. Source from always_allow_sources (e.g., ~/Downloads) bypasses monitor check
        3. Files tracked by version control cannot be moved
        4. Destination filename must follow YYYY-Title, YYYY_MM-Title, or YYYY_MM_DD-Title format

    Returns:
        StageResult with move results
    """
    # Handle string inputs from MCP (use from_any to handle bare paths)
    source_uri = URI.from_any(source) if isinstance(source, str) else source
    dest_uri = URI.from_any(dest) if isinstance(dest, str) else dest

    def _build_result(
        result_obj: StageResult,
        success: bool,
        message: str,
        source_str: str,
        dest_str: str,
        database_updated: bool,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        result_obj.output = MvMvOutput(
            errors=errors or [],
            warnings=warnings or [],
            source=source_str,
            destination=dest_str,
            database_updated=database_updated,
            success=success,
        ).model_dump(mode="python")
        result_obj.result = message
        result_obj.success = success

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ..config.WKSConfig import WKSConfig
        from ..database.Database import Database
        from ..monitor.cmd_sync import cmd_sync
        from ..monitor.explain_path import explain_path

        errors: list[str] = []
        warnings: list[str] = []

        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()
        monitor_cfg = config.monitor
        mv_cfg = config.mv

        yield (0.15, "Resolving paths...")
        try:
            source_path = source_uri.path
            dest_path = dest_uri.path
        except ValueError as e:
            _build_result(
                result_obj,
                success=False,
                message=f"Invalid URI: {e}",
                source_str=str(source_uri),
                dest_str=str(dest_uri),
                database_updated=False,
                errors=[str(e)],
            )
            return

        source_str = str(source_path)
        dest_str = str(dest_path)

        yield (0.2, "Validating source exists...")
        # Check source exists
        if not source_path.exists():
            _build_result(
                result_obj,
                success=False,
                message=f"Source does not exist: {source_str}",
                source_str=source_str,
                dest_str=dest_str,
                database_updated=False,
                errors=[f"Source does not exist: {source_str}"],
            )
            return

        yield (0.25, "Checking version control...")
        # Check if source is tracked by git
        is_tracked, git_root = _is_git_tracked(source_path)
        if is_tracked:
            _build_result(
                result_obj,
                success=False,
                message=f"Cannot move git-tracked file: {source_str}",
                source_str=source_str,
                dest_str=dest_str,
                database_updated=False,
                errors=[
                    f"File is tracked by git in repo {git_root}. "
                    "Remove from version control first (git rm --cached) before moving."
                ],
            )
            return

        yield (0.3, "Validating source permissions...")
        # Check source is monitored OR in always_allow_sources
        source_always_allowed = mv_cfg.is_always_allowed_source(source_path)
        if not source_always_allowed:
            source_allowed, source_trace = explain_path(monitor_cfg, source_path)
            if not source_allowed:
                reason = source_trace[-1] if source_trace else "Not in monitored paths"
                _build_result(
                    result_obj,
                    success=False,
                    message=f"Source not monitored: {reason}",
                    source_str=source_str,
                    dest_str=dest_str,
                    database_updated=False,
                    errors=[f"Source path not monitored: {source_str}. Reason: {reason}"],
                )
                return

        yield (0.35, "Validating destination filename...")
        # Check destination filename format (only for renamed files)
        dest_filename = dest_path.name
        if source_path.name != dest_filename:
            is_valid, error_msg = _is_valid_filename(dest_filename)
            if not is_valid:
                _build_result(
                    result_obj,
                    success=False,
                    message=error_msg,
                    source_str=source_str,
                    dest_str=dest_str,
                    database_updated=False,
                    errors=[error_msg],
                )
                return

        yield (0.4, "Validating destination...")
        # Check dest parent is monitored
        dest_parent = dest_path.parent
        dest_allowed, dest_trace = explain_path(monitor_cfg, dest_parent)
        if not dest_allowed:
            reason = dest_trace[-1] if dest_trace else "Not in monitored paths"
            _build_result(
                result_obj,
                success=False,
                message=f"Destination parent not monitored: {reason}",
                source_str=source_str,
                dest_str=dest_str,
                database_updated=False,
                errors=[f"Destination parent not monitored: {dest_parent}. Reason: {reason}"],
            )
            return

        yield (0.45, "Checking destination availability...")
        # Check if dest exists - no overwriting allowed
        if dest_path.exists():
            _build_result(
                result_obj,
                success=False,
                message=f"Destination exists (overwriting not allowed): {dest_str}",
                source_str=source_str,
                dest_str=dest_str,
                database_updated=False,
                errors=[f"Destination exists: {dest_str}. Overwriting is not allowed."],
            )
            return

        yield (0.5, "Moving file...")
        try:
            # Ensure parent directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source_path), str(dest_path))
        except Exception as e:
            _build_result(
                result_obj,
                success=False,
                message=f"Move failed: {e}",
                source_str=source_str,
                dest_str=dest_str,
                database_updated=False,
                errors=[f"Move failed: {e}"],
            )
            return

        yield (0.7, "Updating database...")
        database_updated = False
        try:
            # Delete old record from nodes database
            database_name = "nodes"
            with Database(config.database, database_name) as database:
                old_uri_str = str(URI.from_path(source_path))
                database.delete_many({"local_uri": old_uri_str})

            # Sync new path
            sync_result = cmd_sync(URI.from_path(dest_path))
            list(sync_result.progress_callback(sync_result))

            if sync_result.success:
                database_updated = True
            else:
                sync_errors = sync_result.output["errors"]
                warnings.extend([f"Sync warning: {e}" for e in sync_errors])
        except Exception as e:
            warnings.append(f"Database update failed: {e}")

        yield (0.85, "Updating vault links...")
        try:
            from ..vault.Vault import Vault

            with Vault() as vault:
                link_result = vault.update_link_for_move(source_path, dest_path)
                if link_result is not None:
                    old_vault_rel, new_vault_rel = link_result
                    vault.rewrite_wiki_links(old_vault_rel, new_vault_rel)
                    vault.update_edges_for_move(
                        source_path,
                        dest_path,
                        old_vault_rel,
                        new_vault_rel,
                    )
        except Exception as e:
            warnings.append(f"Vault link update failed: {e}")

        yield (1.0, "Complete")
        _build_result(
            result_obj,
            success=True,
            message=f"Moved {source_path.name} to {dest_str}",
            source_str=source_str,
            dest_str=dest_str,
            database_updated=database_updated,
            errors=errors,
            warnings=warnings,
        )

    return StageResult(
        announce=f"Moving {source} to {dest}...",
        progress_callback=do_work,
    )
