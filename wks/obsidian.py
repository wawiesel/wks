"""
Obsidian vault integration for WKS.

Handles:
- Creating and updating project notes
- Managing symlinks in links/ directory
- Updating links when files move
"""

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

        # Build log entry
        if operation == "moved" and destination:
            entry = f"- **{timestamp}** - `MOVED` {path} → {destination}"
        elif operation == "renamed" and destination:
            entry = f"- **{timestamp}** - `RENAMED` {path.name} → {destination.name} (in {path.parent})"
        elif operation == "created":
            entry = f"- **{timestamp}** - `CREATED` {path}"
        elif operation == "deleted":
            entry = f"- **{timestamp}** - `DELETED` {path}"
        elif operation == "modified":
            entry = f"- **{timestamp}** - `MODIFIED` {path}"
        else:
            entry = f"- **{timestamp}** - `{operation.upper()}` {path}"

        if details:
            entry += f"\n  > {details}"

        entry += "\n"

        # Initialize file if it doesn't exist
        if not self.file_log_path.exists():
            self.file_log_path.write_text(f"""# File Operations Log

Reverse chronological log of all file operations tracked by WKS.

---

{entry}""")
        else:
            # Read existing content
            content = self.file_log_path.read_text()

            # Find the separator
            if "---" in content:
                header, log_entries = content.split("---", 1)
                # Insert new entry at the top of the log
                new_content = f"{header}---\n\n{entry}{log_entries}"
            else:
                # Fallback if separator not found
                new_content = f"{content}\n{entry}"

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
