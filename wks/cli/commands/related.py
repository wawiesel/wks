"""Related command - find semantically similar documents (Semantic Engines layer)."""

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse

from .index import load_similarity_required


def parse_related_query_path(path_str: str, display: Any) -> Optional[Path]:
    """Parse and validate query path for related command."""
    query_path = Path(path_str).expanduser().resolve()
    if not query_path.exists():
        display.error(f"File not found: {query_path}")
        return None
    return query_path


def load_similarity_for_related(display: Any) -> Tuple[Any, int]:
    """Load similarity database for related command.

    Returns:
        Tuple of (db, exit_code) where exit_code is 0 on success
    """
    display.status("Loading similarity database...")
    try:
        db, _ = load_similarity_required()
        display.success("Connected to database")
        return db, 0
    except SystemExit as e:
        return None, (e.code if isinstance(e.code, int) else 1)
    except Exception as e:
        display.error(f"Error loading similarity database: {e}")
        return None, 2


def find_similar_documents(db: Any, query_path: Path, limit: int, min_similarity: float, display: Any) -> Tuple[List[Tuple[str, float]], int]:
    """Find similar documents.

    Returns:
        Tuple of (results, exit_code)
    """
    display.status(f"Finding similar documents to: {query_path.name}")
    try:
        results = db.find_similar(
            query_path=query_path,
            limit=limit,
            min_similarity=min_similarity,
            mode="file"
        )
        return results, 0
    except Exception as e:
        display.error(f"Error finding similar documents: {e}")
        return [], 2
    finally:
        try:
            db.client.close()
        except Exception:
            pass


def uri_to_path(path_uri: str) -> Path:
    """Convert file:// URI to Path."""
    if path_uri.startswith("file://"):
        parsed = urlparse(path_uri)
        return Path(unquote(parsed.path or ""))
    return Path(path_uri)


def format_related_results_json(results: List[Tuple[str, float]]) -> List[Dict[str, Any]]:
    """Format related results as JSON."""
    output = []
    for path_uri, similarity in results:
        display_path = uri_to_path(path_uri)
        output.append({
            "path": str(display_path),
            "similarity": round(similarity, 3)
        })
    return output


def format_related_results_table(results: List[Tuple[str, float]], query_path: Path) -> List[Dict[str, str]]:
    """Format related results as table data."""
    table_data = []
    for path_uri, similarity in results:
        display_path = uri_to_path(path_uri)
        sim_pct = similarity * 100
        table_data.append({
            "Similarity": f"{sim_pct:5.1f}%",
            "Path": str(display_path)
        })
    return table_data


def related_cmd(args: argparse.Namespace) -> int:
    """Find semantically similar documents."""
    display = args.display_obj

    # Parse input path
    query_path = parse_related_query_path(args.path, display)
    if query_path is None:
        return 2

    # Load similarity DB
    db, exit_code = load_similarity_for_related(display)
    if db is None:
        return exit_code

    # Find similar documents
    results, exit_code = find_similar_documents(db, query_path, args.limit, args.min_similarity, display)
    if exit_code != 0:
        return exit_code

    # Format output
    if args.format == "json" or args.display == "mcp":
        output = format_related_results_json(results)
        display.json_output(output)
    else:
        if not results:
            display.info(f"No similar documents found for: {query_path}")
            return 0
        table_data = format_related_results_table(results, query_path)
        display.table(table_data, title=f"Similar to: {query_path}")

    return 0


def setup_related_parser(subparsers) -> None:
    """Setup related command parser."""
    rel = subparsers.add_parser("related", help="Find semantically similar documents")
    rel.add_argument("path", help="Reference file to find similar documents for")
    rel.add_argument("--limit", type=int, default=10, help="Maximum number of results (default: 10)")
    rel.add_argument("--min-similarity", type=float, default=0.0, help="Minimum similarity threshold 0.0-1.0 (default: 0.0)")
    rel.add_argument("--format", choices=["table", "json"], default="table", help="Output format (default: table)")
    rel.set_defaults(func=related_cmd)

