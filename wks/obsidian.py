"""
Obsidian vault integration for WKS.

Handles:
- Creating and updating project notes
- Managing symlinks in links/ directory
- Updating links when files move
"""

import hashlib
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime


class ObsidianVault:
    """Interface to an Obsidian vault for WKS."""

    def __init__(self, vault_path: Path):
        """
        Initialize vault interface.

        Args:
            vault_path: Path to Obsidian vault (e.g., ~/obsidian)
        """
        self.vault_path = Path(vault_path)
        self.links_dir = self.vault_path / "links"
        self.projects_dir = self.vault_path / "Projects"
        self.people_dir = self.vault_path / "People"
        self.topics_dir = self.vault_path / "Topics"
        self.ideas_dir = self.vault_path / "Ideas"
        self.orgs_dir = self.vault_path / "Organizations"
        self.records_dir = self.vault_path / "Records"
        self.file_log_path = self.vault_path / "FileOperations.md"
        self.activity_log_path = self.vault_path / "ActiveFiles.md"

    def ensure_structure(self):
        """Create vault folder structure if it doesn't exist."""
        for directory in [
            self.links_dir,
            self.projects_dir,
            self.people_dir,
            self.topics_dir,
            self.ideas_dir,
            self.orgs_dir,
            self.records_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def create_project_note(
        self,
        project_path: Path,
        status: str = "Active",
        description: Optional[str] = None
    ) -> Path:
        """
        Create or update a project note in Projects/ folder.

        Args:
            project_path: Path to project directory (e.g., ~/2025-WKS)
            status: Project status
            description: Optional project description

        Returns:
            Path to created note
        """
        project_name = project_path.name
        note_path = self.projects_dir / f"{project_name}.md"

        # Extract date and name from project folder
        parts = project_name.split("-", 1)
        year = parts[0] if len(parts) > 0 else ""
        name = parts[1] if len(parts) > 1 else project_name

        content = f"""# {project_name}

**Status:** {status}
**Created:** {datetime.now().strftime('%Y-%m-%d')}
**Location:** `{project_path}`

## Overview

{description or f"Project: {name}"}

## Links

- Project directory: [[links/{project_name}]]
- Related topics:

## Notes

"""

        note_path.write_text(content)
        return note_path

    def link_file(self, source_file: Path, preserve_structure: bool = True) -> Optional[Path]:
        """
        Create a symlink to a file in the links/ directory.

        Args:
            source_file: File to link to
            preserve_structure: If True, mirror directory structure from home

        Returns:
            Path to created symlink, or None if failed
        """
        if not source_file.exists():
            return None

        if preserve_structure:
            # Mirror structure from home directory
            home = Path.home()
            try:
                relative = source_file.relative_to(home)
                link_path = self.links_dir / relative
            except ValueError:
                # File not under home, use project-based structure
                link_path = self.links_dir / source_file.name
        else:
            link_path = self.links_dir / source_file.name

        # Create parent directories
        link_path.parent.mkdir(parents=True, exist_ok=True)

        # Create symlink if it doesn't exist
        if not link_path.exists():
            link_path.symlink_to(source_file)

        return link_path

    def link_project(self, project_path: Path) -> list[Path]:
        """
        Create symlinks for key files in a project.

        Args:
            project_path: Path to project directory

        Returns:
            List of created symlink paths
        """
        links_created = []

        # Common files to link
        common_files = [
            "README.md",
            "SPEC.md",
            "TODO.md",
            "NOTES.md",
        ]

        for filename in common_files:
            file_path = project_path / filename
            if file_path.exists():
                link = self.link_file(file_path)
                if link:
                    links_created.append(link)

        return links_created

    def update_link_on_move(self, old_path: Path, new_path: Path):
        """
        Update symlink when a file is moved.

        Args:
            old_path: Previous file location
            new_path: New file location
        """
        # Find existing symlink
        home = Path.home()
        try:
            relative_old = old_path.relative_to(home)
            old_link = self.links_dir / relative_old

            if old_link.exists() and old_link.is_symlink():
                # Remove old link
                old_link.unlink()

                # Create new link
                self.link_file(new_path)
        except (ValueError, OSError):
            pass  # File not tracked or operation failed

    def find_broken_links(self) -> list[Path]:
        """
        Find all broken symlinks in the vault.

        Returns:
            List of broken symlink paths
        """
        broken = []

        for link in self.links_dir.rglob("*"):
            if link.is_symlink() and not link.exists():
                broken.append(link)

        return broken

    def cleanup_broken_links(self) -> int:
        """
        Remove all broken symlinks from the vault.

        Returns:
            Number of links removed
        """
        broken = self.find_broken_links()
        for link in broken:
            link.unlink()
        return len(broken)

    def _get_file_checksum(self, path: Path) -> Optional[str]:
        """
        Calculate SHA256 checksum of a file.

        Args:
            path: Path to file

        Returns:
            Hex digest of checksum, or None if file doesn't exist/can't be read
        """
        try:
            if path.exists() and path.is_file():
                sha256 = hashlib.sha256()
                with open(path, 'rb') as f:
                    for block in iter(lambda: f.read(4096), b''):
                        sha256.update(block)
                return sha256.hexdigest()[:12]  # First 12 chars for brevity
        except (OSError, PermissionError):
            pass
        return None

    def log_file_operation(
        self,
        operation: str,
        path: Path,
        destination: Optional[Path] = None,
        details: Optional[str] = None
    ):
        """
        Log a file operation to FileOperations.md in reverse chronological order.

        Args:
            operation: Type of operation (created, modified, moved, deleted, renamed)
            path: Source path
            destination: Destination path (for moves/renames)
            details: Optional additional details
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Get checksums
        source_checksum = self._get_file_checksum(path)
        dest_checksum = self._get_file_checksum(destination) if destination else None

        # Build log entry in table format
        if operation == "moved" and destination:
            entry = f"| {timestamp} | `MOVED` | `{path}` | `{destination}` | {source_checksum or 'N/A'} |"
        elif operation == "renamed" and destination:
            entry = f"| {timestamp} | `RENAMED` | `{path}` | `{destination}` | {source_checksum or 'N/A'} |"
        elif operation == "created":
            checksum = source_checksum or 'N/A'
            entry = f"| {timestamp} | `CREATED` | `{path}` | — | {checksum} |"
        elif operation == "deleted":
            entry = f"| {timestamp} | `DELETED` | `{path}` | — | N/A |"
        elif operation == "modified":
            checksum = source_checksum or 'N/A'
            entry = f"| {timestamp} | `MODIFIED` | `{path}` | — | {checksum} |"
        else:
            entry = f"| {timestamp} | `{operation.upper()}` | `{path}` | — | N/A |"

        if details:
            entry += f"\n> {details}"

        entry += "\n"

        # Initialize file if it doesn't exist
        if not self.file_log_path.exists():
            self.file_log_path.write_text(f"""# File Operations Log

Reverse chronological log of all file operations tracked by WKS.

| Date/Time | Operation | Source | Destination | Checksum |
|-----------|-----------|--------|-------------|----------|
{entry}""")
        else:
            # Read existing content
            content = self.file_log_path.read_text()

            # Find the table header
            if "| Date/Time | Operation |" in content:
                parts = content.split("|-", 1)
                if len(parts) == 2:
                    header_part = parts[0] + "|-" + parts[1].split("\n", 1)[0] + "\n"
                    # Insert new entry right after header
                    new_content = header_part + entry + parts[1].split("\n", 1)[1] if len(parts[1].split("\n", 1)) > 1 else header_part + entry
                else:
                    new_content = content + "\n" + entry
            else:
                # Fallback if table not found
                new_content = content + "\n" + entry

            self.file_log_path.write_text(new_content)

    def get_recent_operations(self, limit: int = 50) -> str:
        """
        Get the most recent file operations.

        Args:
            limit: Maximum number of entries to return

        Returns:
            String containing recent operations
        """
        if not self.file_log_path.exists():
            return "No operations logged yet."

        content = self.file_log_path.read_text()
        lines = content.split('\n')

        # Find entries (lines starting with '- **')
        entries = [line for line in lines if line.strip().startswith('- **')]

        return '\n'.join(entries[:limit])

    def update_active_files(self, active_files: list[tuple[str, float, float]]):
        """
        Update the ActiveFiles.md view with recently changed files and angles.

        Args:
            active_files: List of (path, angle, delta_angle) tuples
        """
        content = """# Active Files

Files with recent activity, sorted by attention angle.

**Angle**: Measure of recent activity (higher = more active)
**Δ**: Change in angle (positive = increasing activity)

| File | Location | Angle | Δ | Modified |
|------|----------|-------|---|----------|
"""

        for path_str, angle, delta in active_files:
            path = Path(path_str)

            # Just show filename
            filename = path.name

            # Show parent directory compactly
            try:
                rel_path = path.relative_to(Path.home())
                parent = str(rel_path.parent)
                if parent == '.':
                    location = '~'
                else:
                    location = f"~/{parent}"
            except ValueError:
                location = str(path.parent)

            # Format last modified
            if path.exists():
                mod_time = datetime.fromtimestamp(path.stat().st_mtime)
                time_str = mod_time.strftime('%m/%d %H:%M')
            else:
                time_str = "—"

            # Format delta compactly
            delta_str = f"{delta:+.1f}"

            content += f"| `{filename}` | {location} | {angle:.1f} | {delta_str} | {time_str} |\n"

        content += f"\n*Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n"

        self.activity_log_path.write_text(content)


if __name__ == "__main__":
    # Example usage
    from rich.console import Console

    console = Console()

    vault = ObsidianVault(Path.home() / "obsidian")
    vault.ensure_structure()

    console.print("[green]Vault structure created![/green]")

    # Create a project note
    wks_project = Path.home() / "2025-WKS"
    if wks_project.exists():
        note = vault.create_project_note(
            wks_project,
            description="Wieselquist Knowledge System - AI-assisted file organization"
        )
        console.print(f"[blue]Created project note:[/blue] {note}")

        # Link project files
        links = vault.link_project(wks_project)
        console.print(f"[yellow]Created {len(links)} symlinks[/yellow]")
