#!/usr/bin/env python3
"""Fix file:// URLs in Obsidian vault by replacing with proper _links structure.

According to SPEC.md, external files should be linked via:
  _links/<machine>/Users/ww5/path/to/file

NOT direct symlinks in _links/.
"""

import re
import socket
from pathlib import Path
from typing import Dict, List, Tuple

VAULT_PATH = Path.home() / "_vault"
MACHINE_NAME = socket.gethostname().split(".")[0]  # lap139160


def find_file_urls(vault_path: Path) -> Dict[Path, List[Tuple[str, str, str]]]:
    """Find all file:// URLs in markdown files.

    Returns:
        Dict mapping file paths to list of (full_match, filesystem_path, link_text) tuples
    """
    pattern = re.compile(r'\[([^\]]+)\]\((file:///Users/ww5/[^)]+)\)')
    results = {}

    for md_file in vault_path.rglob("*.md"):
        # Skip broken symlinks and _links directory
        if not md_file.exists() or md_file.is_symlink() or "_links" in md_file.parts:
            continue

        matches = []
        try:
            content = md_file.read_text()
        except (FileNotFoundError, OSError) as e:
            print(f"Skip {md_file}: {e}")
            continue

        for match in pattern.finditer(content):
            link_text = match.group(1)
            file_url = match.group(2)
            # Convert file:// URL to path
            fs_path = file_url.replace("file://", "")
            matches.append((match.group(0), fs_path, link_text))

        if matches:
            results[md_file] = matches

    return results


def replace_file_urls_with_links_structure(vault_path: Path):
    """Replace all file:// URLs with proper _links/<machine>/ paths."""

    file_urls = find_file_urls(vault_path)
    print(f"Found file:// URLs in {len(file_urls)} files")

    for md_file, matches in file_urls.items():
        print(f"\n{md_file.relative_to(vault_path)}:")
        content = md_file.read_text()
        modified = False

        for full_match, fs_path, link_text in matches:
            target = Path(fs_path)

            # Check if target exists
            if not target.exists():
                print(f"  ⚠ SKIP (missing): {fs_path}")
                continue

            # Convert to _links/<machine>/<full_path> format
            # Remove leading / from fs_path
            relative_fs_path = fs_path.lstrip("/")
            links_path = f"_links/{MACHINE_NAME}/{relative_fs_path}"

            # Create proper markdown link (wiki-style)
            if target.is_dir():
                new_link = f"[[{links_path}/|{link_text}]]"
            else:
                new_link = f"[[{links_path}|{link_text}]]"

            content = content.replace(full_match, new_link)
            modified = True
            print(f"  ✓ {fs_path}")
            print(f"    → [[{links_path}]]")

        if modified:
            md_file.write_text(content)
            print(f"  → Updated {md_file.name}")


def remove_incorrect_flat_symlinks():
    """Remove the flat symlinks we incorrectly created in _links/."""
    links_dir = VAULT_PATH / "_links"

    # These are the ones created by the first script (incorrect)
    incorrect_symlinks = [
        "2024_11-DAF", "2024_11-ANS_Winter", "2024_11-ANSWER", "2024_10-snamc",
        "2025-SCALE_Development", "2025-SCALE_SQA", "_old",
        "2025-SCALE_Info_Management", "2025-OrigamiTest", "2025-SCALE_Icons",
        "2025-SCALE_Procedures", "2025-Copulas", "2025-ServerCommander",
        "2025-GaussianSplat", "2025-PyDecay", "2025-OECD_NEA_SG8",
        "2024_09-wpncs", "2025-GridChallenge", "2025-SCALE_Intro_Slides",
        "2025-RainyDays", "2025-SCALE_Runtime_Estimator",
        "2025-PolarisTritonDepletionGridStudy", "2025-BudgetFix",
        "2025-Johnny5", "2025-SDRM", "2025-MonotoneSpline",
        "2025-ENSDF_Parser", "2025-Strategery", "2025-Inference",
        "2025-OGCrawler", "2025-Document_Interpretation", "2025-SCALE_7"
    ]

    print("\nRemoving incorrect flat symlinks:")
    for name in incorrect_symlinks:
        symlink_path = links_dir / name
        if symlink_path.exists() or symlink_path.is_symlink():
            print(f"  Removing: {symlink_path}")
            if symlink_path.is_dir() and not symlink_path.is_symlink():
                # It's a directory, remove recursively
                import shutil
                shutil.rmtree(symlink_path)
            else:
                symlink_path.unlink()


if __name__ == "__main__":
    print(f"Machine: {MACHINE_NAME}")
    print(f"Vault: {VAULT_PATH}")

    # Step 1: Remove incorrect symlinks
    remove_incorrect_flat_symlinks()

    # Step 2: Replace file:// URLs with wiki-style links
    replace_file_urls_with_links_structure(VAULT_PATH)

    print("\n✓ Done!")
    print("\nNOTE: The vault scanner will create symlinks in _links/lap139160/")
    print("      as it scans the markdown files.")
