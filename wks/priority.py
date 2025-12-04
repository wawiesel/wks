"""Priority calculation for file importance scoring."""

from pathlib import Path
from typing import Any


def find_managed_directory(path: Path, managed_dirs: dict[str, int]) -> tuple[Path | None, int]:
    """Find the deepest matching managed directory for a path.

    Args:
        path: File path (should be resolved/absolute)
        managed_dirs: Dict mapping directory paths to base priorities

    Returns:
        Tuple of (matched_directory_path, base_priority)
        Returns (None, 100) if no match (default priority)
    """
    # Resolve path to absolute
    path = path.resolve()

    # Convert managed_dirs keys to resolved Paths
    resolved_managed = {Path(k).expanduser().resolve(): v for k, v in managed_dirs.items()}

    # Find all ancestors of the path
    ancestors = [path, *list(path.parents)]

    # Find deepest (most specific) match
    best_match = None
    best_priority = 100  # Default

    for ancestor in ancestors:
        if ancestor in resolved_managed and (best_match is None or len(ancestor.parts) > len(best_match.parts)):
            # Deeper match wins (first match is deepest)
            best_match = ancestor
            best_priority = resolved_managed[ancestor]

    return best_match, best_priority


def count_leading_underscores(name: str) -> int:
    """Count leading underscores in a name.

    Args:
        name: Path component name

    Returns:
        Number of leading underscores (0 if none)
    """
    count = 0
    for char in name:
        if char == "_":
            count += 1
        else:
            break
    return count


def calculate_underscore_penalty(name: str) -> float:
    """Calculate penalty multiplier for underscore prefixes.

    Rules:
    - Single "_" component: ÷64
    - Each leading "_": ÷2

    Args:
        name: Path component name

    Returns:
        Penalty multiplier (e.g., 0.5 for one underscore, 0.25 for two)
    """
    if name == "_":
        return 1.0 / 64.0

    underscore_count = count_leading_underscores(name)
    if underscore_count == 0:
        return 1.0

    # Each underscore divides by 2
    return 1.0 / (2**underscore_count)


def calculate_priority(path: Path, managed_dirs: dict[str, int], priority_config: dict) -> int:
    """Calculate priority score for a file.

    Algorithm:
    1. Find managed directory (deepest match)
    2. Start with base priority from that directory
    3. For each path component after base:
       - Apply depth multiplier (default 0.9)
       - Apply underscore penalty (÷2 per _, ÷64 for single _)
    4. Apply extension weight
    5. Round to integer (minimum 1)

    Args:
        path: File path (will be resolved)
        managed_dirs: Dict mapping directory paths to base priorities
        priority_config: Dict with keys:
            - depth_multiplier: float (default 0.9)
            - underscore_divisor: int (default 2)
            - single_underscore_divisor: int (default 64)
            - extension_weights: dict mapping extensions to weights

    Returns:
        Priority score (integer, minimum 1)

    Examples:
        >>> # /Users/ww5/Documents/reports/_old/draft.pdf
        >>> # Managed: ~/Documents (100), relative: reports/_old/draft.pdf
        >>> # reports: 100 * 0.9 = 90
        >>> # _old: 90 * 0.9 * 0.5 = 40.5
        >>> # Extension .pdf: 40.5 * 1.1 = 44.55
        >>> # Result: 45
    """
    # Resolve path
    path = path.resolve()

    # Find managed directory
    managed_dir, base_priority = find_managed_directory(path, managed_dirs)

    # Get config values
    depth_multiplier = priority_config.get("depth_multiplier", 0.9)
    extension_weights = priority_config.get("extension_weights", {})
    default_weight = extension_weights.get("default", 1.0)

    # Start with base priority
    score = float(base_priority)

    # Calculate relative path from managed directory
    if managed_dir:
        try:
            relative_parts = path.relative_to(managed_dir).parts
        except ValueError:
            # Path not under managed_dir (shouldn't happen)
            relative_parts = path.parts
    else:
        # No managed directory match, use full path
        relative_parts = path.parts

    # Process each directory component (exclude filename)
    for component in relative_parts[:-1]:
        # Apply depth penalty
        score *= depth_multiplier

        # Apply underscore penalty
        underscore_penalty = calculate_underscore_penalty(component)
        score *= underscore_penalty

    # Process filename stem ONLY if it has leading underscores
    filename_stem = path.stem
    if filename_stem and (filename_stem.startswith("_") or filename_stem == "_"):
        # Apply depth penalty for filename level
        score *= depth_multiplier

        # Apply underscore penalty to stem
        underscore_penalty = calculate_underscore_penalty(filename_stem)
        score *= underscore_penalty

    # Apply extension weight to final score
    extension = path.suffix.lower()
    weight = extension_weights.get(extension, default_weight)
    score *= weight

    # Round to integer (round half up), minimum 1
    # Use int(score + 0.5) for round-half-up behavior instead of Python's round-half-to-even
    return max(1, int(score + 0.5))


def priority_examples() -> list[dict[str, Any]]:
    """Return example priority calculations for testing/documentation."""
    managed_dirs = {
        "~/Desktop": 150,
        "~/deadlines": 120,
        "~": 100,
        "~/Documents": 100,
        "~/Pictures": 80,
        "~/Downloads": 50,
    }

    priority_config = {
        "depth_multiplier": 0.9,
        "underscore_divisor": 2,
        "single_underscore_divisor": 64,
        "extension_weights": {".docx": 1.3, ".pptx": 1.3, ".pdf": 1.1, "default": 1.0},
    }

    home = Path.home()

    examples = [
        # Example 1: Deep nesting with underscores
        (home / "Documents/my/full/_path/__file.txt", "~/Documents/my/full/_path/__file.txt", 8),
        # Example 2: Single underscore directory
        (home / "Documents/my/_/path/file.txt", "~/Documents/my/_/path/file.txt", 1),
        # Example 3: DOCX with high weight
        (
            home / "Documents/reports/2025/annual_report.docx",
            "~/Documents/reports/2025/annual_report.docx",
            105,
        ),
        # Example 4: Project with archive
        (home / "2025-Project/_old/draft.pdf", "~/2025-Project/_old/draft.pdf", 45),
        # Example 5: Pictures directory (lower base)
        (
            home / "Pictures/2025-Memes/funny_diagram.png",
            "~/Pictures/2025-Memes/funny_diagram.png",
            72,
        ),
        # Example 6: Downloads
        (home / "Downloads/report.docx", "~/Downloads/report.docx", 65),
        # Example 7: Deadlines (high base)
        (
            home / "deadlines/2025_12_15-Proposal/draft_v3.pdf",
            "~/deadlines/2025_12_15-Proposal/draft_v3.pdf",
            119,
        ),
        # Example 8: Downloads archive
        (home / "Downloads/_archive/old_file.txt", "~/Downloads/_archive/old_file.txt", 23),
    ]

    results = []
    for path, display_path, expected in examples:
        calculated = calculate_priority(path, managed_dirs, priority_config)
        results.append(
            {
                "path": display_path,
                "expected": expected,
                "calculated": calculated,
                "match": calculated == expected,
            }
        )

    return results
