from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.monitor._sync_uri import sync_uri
from wks.api.monitor.explain_path import explain_path

from ._models import FailureKind, ServiceResponse

FILENAME_PATTERN = re.compile(
    r"^(\d{4})(?:_(\d{2})(?:_(\d{2}))?)?-([A-Z][A-Za-z0-9]*(?:_[A-Z][A-Za-z0-9]*)*)(\.[a-zA-Z0-9]+)?$"
)


class MoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    dest: str


class MoveResponse(ServiceResponse):
    model_config = ConfigDict(extra="forbid")

    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source: str
    destination: str
    database_updated: bool


def move_document(request: MoveRequest, *, config: WKSConfig | None = None) -> MoveResponse:
    loaded_config = config or WKSConfig.load()
    try:
        source_uri = URI.from_any(request.source)
        dest_uri = URI.from_any(request.dest)
        source_path = source_uri.path
        dest_path = dest_uri.path
    except ValueError as exc:
        return _error_response(
            message=f"Invalid URI: {exc}",
            failure_kind="validation",
            request=request,
            errors=[str(exc)],
        )

    source_str = str(source_path)
    dest_str = str(dest_path)
    source_error = _validate_source(loaded_config, source_path, source_str, dest_str)
    if source_error is not None:
        return source_error
    destination_error = _validate_destination(loaded_config, source_path, dest_path, source_str, dest_str)
    if destination_error is not None:
        return destination_error

    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(dest_path))
    except Exception as exc:
        return _error_response(
            message=f"Move failed: {exc}",
            failure_kind="runtime",
            request=request,
            errors=[f"Move failed: {exc}"],
        )

    database_updated, warnings = _update_move_side_effects(loaded_config, source_path, dest_path)
    return MoveResponse(
        success=True,
        message=f"Moved {source_path.name} to {dest_str}",
        errors=[],
        warnings=warnings,
        source=source_str,
        destination=dest_str,
        database_updated=database_updated,
    )


def _validate_source(
    config: WKSConfig,
    source_path: Path,
    source_str: str,
    dest_str: str,
) -> MoveResponse | None:
    if not source_path.exists():
        return _error_response(
            message=f"Source does not exist: {source_str}",
            failure_kind="not_found",
            request=MoveRequest(source=source_str, dest=dest_str),
            errors=[f"Source does not exist: {source_str}"],
        )
    is_tracked, git_root = _is_git_tracked(source_path)
    if is_tracked:
        return _error_response(
            message=f"Cannot move git-tracked file: {source_str}",
            failure_kind="conflict",
            request=MoveRequest(source=source_str, dest=dest_str),
            errors=[
                f"File is tracked by git in repo {git_root}. "
                "Remove from version control first (git rm --cached) before moving."
            ],
        )

    if config.mv.is_always_allowed_source(source_path):
        return None
    source_allowed, source_trace = explain_path(config.monitor, source_path)
    if source_allowed:
        return None
    reason = source_trace[-1] if source_trace else "Not in monitored paths"
    return _error_response(
        message=f"Source not monitored: {reason}",
        failure_kind="validation",
        request=MoveRequest(source=source_str, dest=dest_str),
        errors=[f"Source path not monitored: {source_str}. Reason: {reason}"],
    )


def _validate_destination(
    config: WKSConfig,
    source_path: Path,
    dest_path: Path,
    source_str: str,
    dest_str: str,
) -> MoveResponse | None:
    if source_path.name != dest_path.name:
        is_valid, error_msg = _is_valid_filename(dest_path.name)
        if not is_valid:
            return _error_response(
                message=error_msg,
                failure_kind="validation",
                request=MoveRequest(source=source_str, dest=dest_str),
                errors=[error_msg],
            )

    dest_allowed, dest_trace = explain_path(config.monitor, dest_path.parent)
    if not dest_allowed:
        reason = dest_trace[-1] if dest_trace else "Not in monitored paths"
        return _error_response(
            message=f"Destination parent not monitored: {reason}",
            failure_kind="validation",
            request=MoveRequest(source=source_str, dest=dest_str),
            errors=[f"Destination parent not monitored: {dest_path.parent}. Reason: {reason}"],
        )
    if dest_path.exists():
        return _error_response(
            message=f"Destination exists (overwriting not allowed): {dest_str}",
            failure_kind="conflict",
            request=MoveRequest(source=source_str, dest=dest_str),
            errors=[f"Destination exists: {dest_str}. Overwriting is not allowed."],
        )
    return None


def _update_move_side_effects(config: WKSConfig, source_path: Path, dest_path: Path) -> tuple[bool, list[str]]:
    warnings: list[str] = []
    database_updated = False
    try:
        with Database(config.database, "nodes") as database:
            old_uri_str = str(URI.from_path(source_path))
            database.delete_many({"local_uri": old_uri_str})

        sync_output = sync_uri(config, URI.from_path(dest_path), write_status=False)
        if sync_output.success:
            database_updated = True
        else:
            warnings.extend([f"Sync warning: {error}" for error in sync_output.errors])
    except Exception as exc:
        warnings.append(f"Database update failed: {exc}")

    try:
        from wks.api.vault.Vault import Vault

        with Vault(config.vault) as vault:
            link_result = vault.update_link_for_move(source_path, dest_path)
            if link_result is not None:
                old_vault_rel, new_vault_rel = link_result
                vault.rewrite_wiki_links(old_vault_rel, new_vault_rel)
                vault.update_edges_for_move(source_path, dest_path, old_vault_rel, new_vault_rel)
    except Exception as exc:
        warnings.append(f"Vault link update failed: {exc}")
    return database_updated, warnings


def _is_valid_filename(filename: str) -> tuple[bool, str]:
    if FILENAME_PATTERN.match(filename):
        return True, ""
    return False, (
        f"Invalid filename '{filename}'. "
        "Must follow date-title format: YYYY-Title, YYYY_MM-Title, or YYYY_MM_DD-Title "
        "(e.g., 2026-My_Document.pdf, 2026_02-Project_Notes.txt)"
    )


def _is_git_tracked(path: Path) -> tuple[bool, str | None]:
    try:
        git_root_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path.parent,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if git_root_result.returncode != 0:
            return False, None
        git_root = git_root_result.stdout.strip()
        tracked_result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(path)],
            cwd=git_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return tracked_result.returncode == 0, git_root if tracked_result.returncode == 0 else None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False, None


def _error_response(
    *,
    message: str,
    failure_kind: FailureKind,
    request: MoveRequest,
    errors: list[str],
) -> MoveResponse:
    return MoveResponse(
        success=False,
        message=message,
        failure_kind=failure_kind,
        errors=errors,
        warnings=[],
        source=request.source,
        destination=request.dest,
        database_updated=False,
    )
