#!/usr/bin/env python3
"""
Migrate .wkso directories to be one level above git repositories.

This script:
1. Finds all .wkso directories
2. Checks if they are beside a .git directory
3. If yes, moves them to the parent directory
4. If parent already has .wkso, merges the contents
"""

from pathlib import Path
import shutil
import sys


def find_wkso_beside_git(search_root: Path):
    """Find .wkso directories that are beside .git directories."""
    wkso_dirs = []
    for wkso_dir in search_root.rglob(".wkso"):
        if not wkso_dir.is_dir():
            continue
        parent = wkso_dir.parent
        git_dir = parent / ".git"
        if git_dir.exists() and git_dir.is_dir():
            wkso_dirs.append((wkso_dir, parent))
    return wkso_dirs


def migrate_wkso(wkso_dir: Path, repo_dir: Path, dry_run: bool = True):
    """Migrate a .wkso directory to the parent of the repo."""
    parent_dir = repo_dir.parent
    target_wkso = parent_dir / ".wkso"

    print(f"\nFound: {wkso_dir}")
    print(f"  Repo: {repo_dir}")
    print(f"  Target: {target_wkso}")

    if not wkso_dir.exists():
        print(f"  ERROR: Source doesn't exist")
        return False

    # Count files in source
    try:
        source_files = list(wkso_dir.iterdir())
        print(f"  Source files: {len(source_files)}")
    except Exception as e:
        print(f"  ERROR reading source: {e}")
        return False

    if len(source_files) == 0:
        print(f"  Source is empty - will just remove")
        if not dry_run:
            try:
                wkso_dir.rmdir()
                print(f"  ✓ Removed empty directory")
            except Exception as e:
                print(f"  ERROR removing: {e}")
                return False
        else:
            print(f"  [DRY RUN] Would remove empty directory")
        return True

    if target_wkso.exists():
        print(f"  Target exists - will merge")
        try:
            target_files = list(target_wkso.iterdir())
            print(f"  Target files: {len(target_files)}")
        except Exception as e:
            print(f"  ERROR reading target: {e}")
            return False

        # Check for conflicts
        source_names = {f.name for f in source_files}
        target_names = {f.name for f in target_files}
        conflicts = source_names & target_names

        if conflicts:
            print(f"  WARNING: {len(conflicts)} file conflicts: {', '.join(list(conflicts)[:5])}")
            print(f"  Will skip conflicting files and move unique ones")

        if not dry_run:
            moved = 0
            skipped = 0
            for source_file in source_files:
                target_file = target_wkso / source_file.name
                if target_file.exists():
                    print(f"    Skip (exists): {source_file.name}")
                    skipped += 1
                else:
                    try:
                        shutil.move(str(source_file), str(target_file))
                        moved += 1
                    except Exception as e:
                        print(f"    ERROR moving {source_file.name}: {e}")
                        return False

            # Remove source directory if empty
            try:
                remaining = list(wkso_dir.iterdir())
                if len(remaining) == 0:
                    wkso_dir.rmdir()
                    print(f"  ✓ Moved {moved} files, skipped {skipped}, removed source directory")
                else:
                    print(f"  ✓ Moved {moved} files, skipped {skipped}, source still has {len(remaining)} files")
            except Exception as e:
                print(f"  ERROR: {e}")
                return False
        else:
            print(f"  [DRY RUN] Would move non-conflicting files and remove source if empty")

    else:
        # Target doesn't exist - simple move
        if not dry_run:
            try:
                target_wkso.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(wkso_dir), str(target_wkso))
                print(f"  ✓ Moved {len(source_files)} files to {target_wkso}")
            except Exception as e:
                print(f"  ERROR: {e}")
                return False
        else:
            print(f"  [DRY RUN] Would move to {target_wkso}")

    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Migrate .wkso directories above git repos")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Don't actually move files (default)")
    parser.add_argument("--execute", action="store_true", help="Actually perform the migration")
    parser.add_argument("--root", type=str, default=str(Path.home()), help="Root directory to search")

    args = parser.parse_args()
    dry_run = not args.execute
    search_root = Path(args.root).expanduser().resolve()

    if dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No files will be moved")
        print("Use --execute to actually perform the migration")
        print("=" * 60)
    else:
        print("=" * 60)
        print("EXECUTE MODE - Files will be moved")
        print("=" * 60)

    print(f"\nSearching for .wkso directories beside .git in: {search_root}")

    wkso_dirs = find_wkso_beside_git(search_root)

    if len(wkso_dirs) == 0:
        print("\nNo .wkso directories found beside .git directories")
        return 0

    print(f"\nFound {len(wkso_dirs)} .wkso directories beside .git directories")

    success = 0
    failed = 0
    for wkso_dir, repo_dir in wkso_dirs:
        if migrate_wkso(wkso_dir, repo_dir, dry_run):
            success += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    print(f"Summary: {success} successful, {failed} failed")
    if dry_run:
        print("Run with --execute to actually perform the migration")
    print(f"{'='*60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
