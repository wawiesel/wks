"""Index and extract commands (Semantic Engines layer - higher than Monitor)."""

import argparse
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymongo

from ..dataclasses import DatabaseSummary, FileSummary, FileTimings, IndexResult
from ..helpers import (
    as_file_uri_local,
    build_extractor,
    file_checksum,
    iter_files,
    make_progress,
    maybe_write_json,
)
from ...config import load_config, mongo_settings
from ...constants import WKS_HOME_DISPLAY, MAX_DISPLAY_WIDTH
from ...dbmeta import IncompatibleDatabase, resolve_db_compatibility
from ...status import record_db_activity
from ...utils import get_package_version
from ... import mongoctl


# Similarity loading helpers
def handle_similarity_import_error(e: Exception, require_enabled: bool) -> Tuple[None, None]:
    """Handle import errors for similarity dependencies."""
    error_msg = str(e).lower()
    if "sentence" in error_msg or "transformers" in error_msg:
        from ...error_messages import missing_dependency_error
        missing_dependency_error("sentence-transformers", e)
    elif "docling" in error_msg:
        from ...error_messages import missing_dependency_error
        missing_dependency_error("docling", e)
    else:
        print(f"\nSimilarity features not available: {e}")
        print("Install with: pip install -e '.[all]'\n")
    if require_enabled:
        raise SystemExit(2)
    return None, None


def try_build_similarity(cfg: Dict[str, Any], require_enabled: bool) -> Tuple[Any, Any]:
    """Try to build similarity DB from config."""
    try:
        from ...similarity import build_similarity_from_config  # type: ignore
    except ImportError as e:
        return handle_similarity_import_error(e, require_enabled)
    except Exception as e:
        print(f"Similarity not available: {e}")
        if require_enabled:
            raise SystemExit(2)
        return None, None

    space_tag, _ = resolve_db_compatibility(cfg)
    pkg_version = get_package_version()
    try:
        db, sim_cfg = build_similarity_from_config(
            cfg,
            require_enabled=require_enabled,
            compatibility_tag=space_tag,
            product_version=pkg_version,
        )
        return db, sim_cfg
    except IncompatibleDatabase as exc:
        print(exc)
        if require_enabled:
            raise SystemExit(2)
        return None, None
    except Exception as e:
        return try_auto_start_mongod_and_build(cfg, require_enabled, space_tag, pkg_version, e)


def try_auto_start_mongod_and_build(
    cfg: Dict[str, Any],
    require_enabled: bool,
    space_tag: str,
    pkg_version: str,
    original_error: Exception
) -> Tuple[Any, Any]:
    """Try to auto-start mongod and then build similarity."""
    import shutil
    import subprocess
    from ...constants import WKS_HOME_EXT

    mongo_uri = mongo_settings(cfg)["uri"]
    node = mongoctl.local_node(mongo_uri)
    if not (node and shutil.which("mongod")):
        print(f"Failed to initialize similarity DB: {original_error}")
        if require_enabled:
            raise SystemExit(2)
        return None, None

    dbroot = Path.home() / WKS_HOME_EXT / "mongodb"
    dbpath = dbroot / "db"
    logfile = dbroot / "mongod.log"
    dbpath.mkdir(parents=True, exist_ok=True)
    host, port = node
    bind_ip = "127.0.0.1" if host in ("localhost", "127.0.0.1") else host
    try:
        subprocess.check_call([
            "mongod", "--dbpath", str(dbpath), "--logpath", str(logfile),
            "--fork", "--bind_ip", bind_ip, "--port", str(port)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        from ...similarity import build_similarity_from_config  # type: ignore
        db, sim_cfg = build_similarity_from_config(
            cfg,
            require_enabled=require_enabled,
            compatibility_tag=space_tag,
            product_version=pkg_version,
        )
        return db, sim_cfg
    except IncompatibleDatabase as exc2:
        print(exc2)
        if require_enabled:
            raise SystemExit(2)
        return None, None
    except Exception as e2:
        print(f"Failed to auto-start local mongod: {e2}")
        if require_enabled:
            raise SystemExit(2)
        return None, None


def build_similarity_from_config(require_enabled: bool = True):
    """Build similarity database from config."""
    cfg = load_config()
    return try_build_similarity(cfg, require_enabled)


def load_similarity_required() -> Tuple[Any, Dict[str, Any]]:
    """Load similarity DB, raising SystemExit if unavailable."""
    db, sim_cfg = build_similarity_from_config(require_enabled=True)
    if db is None or sim_cfg is None:
        raise SystemExit(2)
    return db, sim_cfg


def mongo_client_params(
    server_timeout: int = 500,
    connect_timeout: int = 500,
    cfg: Optional[Dict[str, Any]] = None,
    *,
    ensure_running: bool = True,
) -> Tuple[pymongo.MongoClient, Dict[str, str]]:
    """Return (client, normalized mongo settings)."""
    if cfg is None:
        cfg = load_config()
    mongo_cfg = mongo_settings(cfg)
    client = mongoctl.create_client(
        mongo_cfg['uri'],
        server_timeout=server_timeout,
        connect_timeout=connect_timeout,
        ensure_running=ensure_running,
    )
    return client, mongo_cfg


def load_vault() -> Any:
    """Load Obsidian vault from config."""
    from ...obsidian import ObsidianVault  # lazy import
    cfg = load_config()
    vault_path = cfg.get('vault_path')
    if not vault_path:
        print(f"Fatal: 'vault_path' is required in {WKS_HOME_DISPLAY}/config.json")
        raise SystemExit(2)
    obs = cfg.get('obsidian', {})
    base_dir = obs.get('base_dir')
    if not base_dir:
        print(f"Fatal: 'obsidian.base_dir' is required in {WKS_HOME_DISPLAY}/config.json (e.g., 'WKS')")
        raise SystemExit(2)
    # Require explicit logging caps/widths
    for k in ["log_max_entries", "active_files_max_rows", "source_max_chars", "destination_max_chars"]:
        if k not in obs:
            print(f"Fatal: missing required config key: obsidian.{k}")
            raise SystemExit(2)
    vault = ObsidianVault(
        Path(vault_path).expanduser(),
        base_dir=base_dir,
        log_max_entries=int(obs["log_max_entries"]),
        active_files_max_rows=int(obs["active_files_max_rows"]),
        source_max_chars=int(obs["source_max_chars"]),
        destination_max_chars=int(obs["destination_max_chars"]),
    )
    return vault


# Extract command
def extract_cmd(args: argparse.Namespace) -> int:
    """Extract document text using the configured pipeline."""
    cfg = load_config()
    include_exts = [e.lower() for e in (cfg.get('similarity', {}).get('include_extensions') or [])]
    files = iter_files(args.paths, include_exts, cfg)
    if not files:
        print("No files to extract (check paths/extensions)")
        return 0
    extractor = build_extractor(cfg)
    extracted = 0
    skipped = 0
    errors = 0
    outputs: List[Tuple[Path, Path]] = []
    with make_progress(total=len(files), display=args.display) as prog:
        for f in files:
            prog.update(f.name, advance=0)
            try:
                result = extractor.extract(f, persist=True)
                if result.content_path:
                    extracted += 1
                    outputs.append((f, Path(result.content_path)))
                else:
                    skipped += 1
            except Exception:
                errors += 1
            finally:
                prog.update(f.name, advance=1)
    for src, artefact in outputs:
        print(f"{src} -> {artefact}")
    print(f"Extracted {extracted} file(s), skipped {skipped}, errors {errors}")
    return 0


# Index command helpers
def handle_untrack_mode(files: List[Path], args: argparse.Namespace) -> int:
    """Handle untrack mode - remove files from similarity DB."""
    removed = 0
    missing = 0
    errors = 0
    outcomes: List[Dict[str, Any]] = []
    with make_progress(total=len(files), display=args.display) as prog:
        prog.update("Connecting to DB…", advance=0)
        db, _ = load_similarity_required()
        for f in files:
            prog.update(f"{f.name} • untrack", advance=0)
            try:
                if db.remove_file(f):
                    removed += 1
                    outcomes.append({"path": str(f), "status": "removed"})
                else:
                    missing += 1
                    outcomes.append({"path": str(f), "status": "not_tracked"})
            except Exception as exc:
                errors += 1
                outcomes.append({"path": str(f), "status": f"error: {exc}"})
            finally:
                prog.update(f.name, advance=1)
        prog.update("Untracking complete", advance=0)
    payload = {
        "mode": "untrack",
        "requested": [str(p) for p in files],
        "removed": removed,
        "missing": missing,
        "errors": errors,
        "files": outcomes,
    }
    maybe_write_json(args, payload)
    print(f"Untracked {removed} file(s), missing {missing}, errors {errors}")
    return 0


def get_database_summary_for_cached(cfg: Dict[str, Any]) -> Optional[DatabaseSummary]:
    """Get database summary when all files are cached."""
    try:
        client, mongo_cfg = mongo_client_params(
            server_timeout=300,
            connect_timeout=300,
            cfg=cfg,
            ensure_running=False,
        )
        coll = client[mongo_cfg['space_database']][mongo_cfg['space_collection']]
        total_files = coll.count_documents({})
        client.close()
        return DatabaseSummary(
            database=mongo_cfg['space_database'],
            collection=mongo_cfg['space_collection'],
            total_files=total_files,
        )
    except Exception:
        return None


def handle_all_cached_case(
    files: List[Path],
    pre_skipped: List[Path],
    hash_times: Dict[Path, Optional[float]],
    cfg: Dict[str, Any],
    display_mode: str,
    args: argparse.Namespace
) -> int:
    """Handle case where all files are already cached."""
    skipped = len(pre_skipped)
    cached_summaries = [
        create_file_summary(
            path=f,
            status="cached",
            hash_time=hash_times.get(f),
        )
        for f in pre_skipped
    ]

    db_summary_obj = get_database_summary_for_cached(cfg)

    result = IndexResult(
        mode="index",
        requested=[str(p) for p in files],
        added=0,
        skipped=skipped,
        errors=0,
        files=cached_summaries,
        database=db_summary_obj,
    )
    maybe_write_json(args, result.to_dict())

    print("Nothing to index; all files already current.")
    print(f"Indexed 0 file(s), skipped {skipped}, errors 0")
    if db_summary_obj:
        print(
            f"DB: {db_summary_obj.database}.{db_summary_obj.collection} total_files={db_summary_obj.total_files}"
        )
    if cached_summaries:
        render_timing_summary_updated(cached_summaries, display_mode)
    return 0


def extract_file_content(extractor: Any, f: Path, prog: Any) -> Tuple[Any, float]:
    """Extract file content. Returns (extraction, extract_time)."""
    prog.update(f"{f.name} • extract", advance=0)
    extract_start = time.perf_counter()
    extraction = extractor.extract(f, persist=True)
    extract_time = time.perf_counter() - extract_start
    return extraction, extract_time


def embed_file_to_db(
    db: Any,
    f: Path,
    extraction: Any,
    checksums: Dict[Path, Optional[str]],
    file_sizes: Dict[Path, Optional[int]],
    prog: Any
) -> Tuple[bool, Dict[str, float]]:
    """Embed file to database. Returns (updated, rec_timings)."""
    prog.update(f"{f.name} • embed", advance=0)
    kwargs: Dict[str, Any] = {}
    checksum_value = checksums.get(f)
    if checksum_value is not None:
        kwargs['file_checksum'] = checksum_value
    size_value = file_sizes.get(f)
    if size_value is not None:
        kwargs['file_bytes'] = size_value

    updated = db.add_file(f, extraction=extraction, **kwargs)
    rec = db.get_last_add_result() or {}
    rec_timings = rec.get('timings') or {}
    return updated, rec_timings


def process_files_for_indexing(
    files_to_process: List[Path],
    pre_skipped: List[Path],
    hash_times: Dict[Path, Optional[float]],
    checksums: Dict[Path, Optional[str]],
    file_sizes: Dict[Path, Optional[int]],
    cfg: Dict[str, Any],
    docs_keep: int,
    display_mode: str
) -> Tuple[List[FileSummary], int, int, int, Any]:
    """Process files through indexing pipeline.

    Returns:
        Tuple of (summaries, added, skipped, errors, db)
    """
    added = 0
    skipped = len(pre_skipped)
    errors = 0
    summaries: List[FileSummary] = []

    with make_progress(total=len(files_to_process), display=display_mode) as prog:
        prog.update(f"Pre-checking {len(files_to_process) + len(pre_skipped)} file(s)…", advance=0)
        prog.update("Connecting to DB…", advance=0)
        db, _ = load_similarity_required()
        extractor = build_extractor(cfg)
        vault = load_vault()

        for f in files_to_process:
            summary, updated, error_occurred = process_single_file(
                f, hash_times, checksums, file_sizes, extractor, db, vault, docs_keep, prog
            )
            summaries.append(summary)
            if error_occurred:
                errors += 1
            elif updated:
                added += 1
            else:
                skipped += 1

        prog.update("DB update complete", advance=0)

    # Add cached files to summaries
    for f in pre_skipped:
        summaries.append(create_file_summary(
            path=f,
            status="cached",
            hash_time=hash_times.get(f),
        ))

    return summaries, added, skipped, errors, db


def write_to_obsidian(vault: Any, db: Any, f: Path, docs_keep: int, prog: Any) -> Optional[float]:
    """Write file to Obsidian vault. Returns obsidian_time or None."""
    rec = db.get_last_add_result() or {}
    ch = rec.get('content_checksum') or rec.get('content_hash')
    txt = rec.get('text')
    if not (ch and txt is not None):
        return None

    try:
        prog.update(f"{f.name} • obsidian", advance=0)
        obs_start = time.perf_counter()
        vault.write_doc_text(ch, f, txt, keep=docs_keep)
        return time.perf_counter() - obs_start
    except Exception:
        return None


def process_single_file(
    f: Path,
    hash_times: Dict[Path, Optional[float]],
    checksums: Dict[Path, Optional[str]],
    file_sizes: Dict[Path, Optional[int]],
    extractor: Any,
    db: Any,
    vault: Any,
    docs_keep: int,
    prog: Any,
) -> Tuple[FileSummary, bool, bool]:
    """Process a single file through extract, embed, and obsidian stages.

    Returns:
        Tuple of (FileSummary, updated, error_occurred)
    """
    try:
        extraction, extract_time = extract_file_content(extractor, f, prog)
    except Exception as exc:
        prog.update(f.name, advance=1)
        return create_file_summary(
            path=f,
            status=f"error: {exc}",
            hash_time=hash_times.get(f),
        ), False, True

    try:
        updated, rec_timings = embed_file_to_db(db, f, extraction, checksums, file_sizes, prog)
    except Exception:
        prog.update(f.name, advance=1)
        return create_file_summary(
            path=f,
            status="error",
            hash_time=hash_times.get(f),
            extract_time=extract_time,
        ), False, True

    obsidian_time = write_to_obsidian(vault, db, f, docs_keep, prog) if updated else None
    prog.update(f.name, advance=1)

    summary = create_file_summary(
        path=f,
        status="updated" if updated else "unchanged",
        hash_time=hash_times.get(f),
        extract_time=extract_time,
        embed_time=rec_timings.get('embed'),
        db_time=rec_timings.get('db_update'),
        chunks_time=rec_timings.get('chunks'),
        obsidian_time=obsidian_time,
    )
    return summary, updated, False


def compute_file_checksums(files: List[Path]) -> Tuple[Dict[Path, Optional[float]], Dict[Path, Optional[str]], Dict[Path, Optional[int]]]:
    """Compute checksums, hash times, and file sizes for files."""
    hash_times: Dict[Path, Optional[float]] = {}
    checksums: Dict[Path, Optional[str]] = {}
    file_sizes: Dict[Path, Optional[int]] = {}
    for f in files:
        try:
            h_start = time.perf_counter()
            checksum = file_checksum(f)
            hash_times[f] = time.perf_counter() - h_start
            checksums[f] = checksum
        except Exception:
            hash_times[f] = None
            checksums[f] = None
        try:
            file_sizes[f] = f.stat().st_size
        except Exception:
            file_sizes[f] = None
    return hash_times, checksums, file_sizes


def precheck_files(
    files: List[Path],
    checksums: Dict[Path, Optional[str]],
    cfg: Dict[str, Any]
) -> Tuple[List[Path], List[Path]]:
    """Precheck files against database to find which need processing.

    Returns:
        Tuple of (files_to_process, pre_skipped)
    """
    pre_skipped: List[Path] = []
    files_to_process = list(files)

    try:
        client, mongo_cfg = mongo_client_params(
            server_timeout=300,
            connect_timeout=300,
            cfg=cfg,
            ensure_running=False,
        )
    except Exception:
        return files_to_process, pre_skipped

    try:
        coll = client[mongo_cfg['space_database']][mongo_cfg['space_collection']]
        to_process: List[Path] = []
        for f in files:
            checksum = checksums.get(f)
            if checksum is None:
                to_process.append(f)
                continue
            doc = coll.find_one({"path": as_file_uri_local(f)})
            try:
                record_db_activity("index.precheck", str(f))
            except Exception:
                pass
            if not doc:
                doc = coll.find_one({"path_local": str(f.resolve())})
            if doc and doc.get("checksum") == checksum:
                pre_skipped.append(f)
            else:
                to_process.append(f)
        files_to_process = to_process
    finally:
        try:
            client.close()
        except Exception:
            pass
    return files_to_process, pre_skipped


def create_file_summary(
    path: Path,
    status: str,
    hash_time: Optional[float] = None,
    extract_time: Optional[float] = None,
    embed_time: Optional[float] = None,
    db_time: Optional[float] = None,
    chunks_time: Optional[float] = None,
    obsidian_time: Optional[float] = None,
) -> FileSummary:
    """Create a FileSummary from timing data."""
    timings = FileTimings(
        hash=hash_time,
        extract=extract_time,
        embed=embed_time,
        db=db_time,
        chunks=chunks_time,
        obsidian=obsidian_time,
    )
    return FileSummary(path=path, status=status, timings=timings)


# Timing summary rendering
def fmt_duration(seconds: Optional[float]) -> str:
    """Format duration in seconds as human-readable string."""
    if seconds is None:
        return "—"
    if seconds >= 1:
        return f"{seconds:6.2f} {'s':>2}"
    return f"{seconds * 1000:6.1f} {'ms':>2}"


def get_stage_labels() -> List[Tuple[str, str]]:
    """Get stage labels for timing summary."""
    return [
        ("hash", "Hash"),
        ("extract", "Extract"),
        ("embed", "Embed"),
        ("db", "DB"),
        ("chunks", "Chunks"),
        ("obsidian", "Obsidian"),
    ]


def calculate_timing_totals(entries: List[FileSummary]) -> Tuple[Dict[str, float], Dict[str, int]]:
    """Calculate totals and counts for timing stages."""
    stage_labels = get_stage_labels()
    totals: Dict[str, float] = {key: 0.0 for key, _ in stage_labels}
    counts: Dict[str, int] = {key: 0 for key, _ in stage_labels}
    for entry in entries:
        timings = entry.timings
        for key, _ in stage_labels:
            val = getattr(timings, key)
            if isinstance(val, (int, float)):
                totals[key] += val
                counts[key] += 1
    return totals, counts


def create_rich_timing_console():
    """Create Rich Console for timing table."""
    from rich.console import Console
    return Console(
        force_terminal=True,
        color_system="standard",
        markup=True,
        highlight=False,
        soft_wrap=False,
    )


def create_rich_timing_table():
    """Create Rich Table for timing summary."""
    from rich import box
    from rich.table import Table

    stage_labels = get_stage_labels()
    detail = Table(
        show_header=True,
        header_style="bold",
        expand=False,
        box=box.SQUARE,
        pad_edge=False,
    )
    detail.add_column("#", justify="right", no_wrap=True, overflow="ignore", min_width=2, max_width=3)
    detail.add_column(
        "File",
        style="cyan",
        no_wrap=False,
        overflow="fold",
        min_width=12,
        max_width=28,
    )
    detail.add_column(
        "Status",
        style="magenta",
        no_wrap=False,
        overflow="fold",
        min_width=8,
        max_width=20,
    )
    for _, label in stage_labels:
        detail.add_column(label, justify="right", no_wrap=True, overflow="ignore", min_width=9, max_width=11)
    return detail


def add_timing_table_rows(
    table: Any,
    entries: List[FileSummary],
    totals: Dict[str, float],
    counts: Dict[str, int]
) -> None:
    """Add data rows to timing table."""
    stage_labels = get_stage_labels()
    for idx, entry in enumerate(entries, 1):
        row = [str(idx), entry.path.name, entry.status]
        for key, _ in stage_labels:
            val = getattr(entry.timings, key)
            row.append(fmt_duration(val))
        table.add_row(*row)
    total_files = max(counts.values()) if counts.values() else len(entries)
    total_row = ["-", "Totals", f"{total_files} file(s)"]
    for key, _ in stage_labels:
        total_row.append(fmt_duration(totals[key] if counts.get(key) else None))
    table.add_row(*total_row, style="bold")


def render_rich_timing_table(entries: List[FileSummary], totals: Dict[str, float], counts: Dict[str, int]) -> None:
    """Render timing summary using Rich table."""
    from rich.panel import Panel

    console = create_rich_timing_console()
    table = create_rich_timing_table()

    console.print()
    add_timing_table_rows(table, entries, totals, counts)

    console.print(Panel.fit(table, title="Timing Details", border_style="dim"), width=MAX_DISPLAY_WIDTH)


def render_plain_timing_table(entries: List[FileSummary], totals: Dict[str, float], counts: Dict[str, int]) -> None:
    """Render timing summary using plain text table."""
    stage_labels = get_stage_labels()
    header = ["#", "File", "Status"] + [label for _, label in stage_labels]

    # Build rows
    details_rows: List[List[str]] = []
    for idx, entry in enumerate(entries, 1):
        row = [str(idx), entry.path.name[:32], entry.status[:20]]
        for key, _ in stage_labels:
            val = getattr(entry.timings, key)
            row.append(fmt_duration(val))
        details_rows.append(row)

    total_files = max(counts.values()) if counts.values() else len(entries)
    totals_row = ["-", "Totals", f"{total_files} file(s)"]
    for key, _ in stage_labels:
        totals_row.append(fmt_duration(totals[key] if counts.get(key) else None))
    details_rows.append(totals_row)

    # Simple table output
    print("\nTiming Details")
    print("=" * 80)
    print(" | ".join(h.ljust(10) for h in header))
    print("-" * 80)
    for row in details_rows:
        print(" | ".join(str(cell).ljust(10)[:10] for cell in row))
    print("=" * 80)


def render_timing_summary_updated(entries: List[FileSummary], display_mode: str) -> None:
    """Render timing summary using FileSummary dataclasses."""
    if not entries:
        return

    totals, counts = calculate_timing_totals(entries)

    if display_mode == "cli":
        render_rich_timing_table(entries, totals, counts)
    else:
        render_plain_timing_table(entries, totals, counts)


# Index command
def index_cmd(args: argparse.Namespace) -> int:
    """Index files or directories (recursive) into similarity DB with progress."""
    cfg = load_config()
    include_exts = [e.lower() for e in (cfg.get('similarity', {}).get('include_extensions') or [])]
    files = iter_files(args.paths, include_exts, cfg)
    if not files:
        print("No files to process (check paths/extensions)")
        return 0

    display_mode = args.display

    if args.untrack:
        return handle_untrack_mode(files, args)

    # Compute checksums and file sizes
    hash_times, checksums, file_sizes = compute_file_checksums(files)

    # Precheck files against database
    files_to_process, pre_skipped = precheck_files(files, checksums, cfg)

    if not files_to_process:
        return handle_all_cached_case(files, pre_skipped, hash_times, cfg, display_mode, args)

    # Process files through indexing pipeline
    docs_keep = int((cfg.get('obsidian') or {}).get('docs_keep', 99))
    summaries, added, skipped, errors, db = process_files_for_indexing(
        files_to_process, pre_skipped, hash_times, checksums, file_sizes, cfg, docs_keep, args.display
    )

    # Get database summary and output results
    db_summary_obj = get_database_summary_from_db(db)
    output_index_results(args, files, added, skipped, errors, summaries, db_summary_obj, display_mode)
    return 0


def get_database_summary_from_db(db: Any) -> Optional[DatabaseSummary]:
    """Get database summary from similarity DB."""
    try:
        stats = db.get_stats()
        if stats:
            return DatabaseSummary(
                database=stats.get("database", ""),
                collection=stats.get("collection", ""),
                total_files=stats.get("total_files", 0),
                total_bytes=stats.get("total_bytes"),
            )
    except Exception:
        pass
    return None


def output_index_results(
    args: argparse.Namespace,
    files: List[Path],
    added: int,
    skipped: int,
    errors: int,
    summaries: List[FileSummary],
    db_summary_obj: Optional[DatabaseSummary],
    display_mode: str
) -> None:
    """Output index command results."""
    result = IndexResult(
        mode="index",
        requested=[str(p) for p in files],
        added=added,
        skipped=skipped,
        errors=errors,
        files=summaries,
        database=db_summary_obj,
    )
    maybe_write_json(args, result.to_dict())

    print(f"Indexed {added} file(s), skipped {skipped}, errors {errors}")

    if summaries:
        render_timing_summary_updated(summaries, display_mode)

    if db_summary_obj:
        print_database_summary(db_summary_obj)


def print_database_summary(db_summary_obj: DatabaseSummary) -> None:
    """Print database summary information."""
    if db_summary_obj.total_bytes is not None:
        print(
            f"DB: {db_summary_obj.database}.{db_summary_obj.collection} total_files={db_summary_obj.total_files} total_bytes={db_summary_obj.total_bytes}"
        )
    else:
        print(
            f"DB: {db_summary_obj.database}.{db_summary_obj.collection} total_files={db_summary_obj.total_files}"
        )


def setup_index_parser(subparsers) -> None:
    """Setup index and extract command parsers."""
    # Extract command
    extp = subparsers.add_parser("extract", help="Extract document text using the configured pipeline")
    extp.add_argument("paths", nargs="+", help="Files or directories to extract")
    extp.set_defaults(func=extract_cmd)

    # Index command
    idx = subparsers.add_parser("index", help="Index files or directories (recursive) into similarity DB with progress")
    idx.add_argument("--untrack", action="store_true", help="Remove tracked entries (and artefacts) instead of indexing")
    idx.add_argument("paths", nargs="+", help="Files or directories to process")
    idx.set_defaults(func=index_cmd)
