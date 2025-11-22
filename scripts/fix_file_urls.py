#!/usr/bin/env python3
"""Fix file:// URLs in Obsidian vault by replacing with _links symlinks."""

import re
from pathlib import Path
from typing import Dict, List, Tuple

VAULT_PATH = Path.home() / "_vault"
LINKS_DIR = VAULT_PATH / "_links"


def find_file_urls(vault_path: Path) -> Dict[Path, List[Tuple[str, str]]]:
    """Find all file:// URLs in markdown files.

    Returns:
        Dict mapping file paths to list of (full_match, filesystem_path) tuples
    """
    pattern = re.compile(r'\[([^\]]+)\]\((file:///Users/ww5/[^)]+)\)')
    results = {}

    for md_file in vault_path.rglob("*.md"):
        # Skip broken symlinks
        if not md_file.exists() or md_file.is_symlink():
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


def create_symlink_if_needed(target: Path, links_dir: Path) -> Path:
    """Create symlink in _links/ if it doesn't exist.

    Returns:
        Path to the symlink (relative to vault)
    """
    # Use project name as symlink name
    link_name = target.name
    link_path = links_dir / link_name

    if not link_path.exists():
        print(f"Creating symlink: {link_path} -> {target}")
        link_path.symlink_to(target)

    return Path("_links") / link_name


def replace_file_urls(vault_path: Path, links_dir: Path):
    """Replace all file:// URLs with _links symlinks."""

    # Ensure _links directory exists
    links_dir.mkdir(exist_ok=True)

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

            # Create symlink
            symlink_path = create_symlink_if_needed(target, links_dir)

            # Replace file:// URL with relative link to symlink
            if target.is_dir():
                new_link = f"[{link_text}]({symlink_path}/)"
            else:
                new_link = f"[{link_text}]({symlink_path})"

            content = content.replace(full_match, new_link)
            modified = True
            print(f"  ✓ {fs_path} -> {symlink_path}")

        if modified:
            md_file.write_text(content)
            print(f"  → Updated {md_file.name}")


if __name__ == "__main__":
    replace_file_urls(VAULT_PATH, LINKS_DIR)
    print("\n✓ Done!")
