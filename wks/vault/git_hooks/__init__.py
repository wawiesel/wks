"""Git hooks for vault link validation."""

from __future__ import annotations

__all__ = ["install_hooks", "uninstall_hooks", "is_hook_installed"]

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def get_hook_source_path() -> Path:
    """Get path to pre-commit hook template."""
    return Path(__file__).parent / "pre-commit"


def get_hook_install_path(vault_path: Path) -> Path:
    """Get path where hook should be installed."""
    return vault_path / ".git" / "hooks" / "pre-commit"


def is_hook_installed(vault_path: Path) -> bool:
    """Check if pre-commit hook is installed.

    Args:
        vault_path: Path to vault root

    Returns:
        True if hook is installed and executable
    """
    hook_path = get_hook_install_path(vault_path)
    return bool(hook_path.exists() and hook_path.stat().st_mode & 0o111)


def install_hooks(vault_path: Path, force: bool = False) -> bool:
    """Install pre-commit hook to vault repository.

    Args:
        vault_path: Path to vault root directory
        force: If True, overwrite existing hook

    Returns:
        True if hook was installed successfully

    Raises:
        RuntimeError: If vault is not a git repository
        FileExistsError: If hook exists and force=False
    """
    # Verify git repo
    git_dir = vault_path / ".git"
    if not git_dir.exists() or not git_dir.is_dir():
        raise RuntimeError(f"Not a git repository: {vault_path}")

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    hook_source = get_hook_source_path()
    hook_dest = get_hook_install_path(vault_path)

    # Check if hook already exists
    if hook_dest.exists() and not force:
        raise FileExistsError(f"Hook already exists: {hook_dest}\nUse force=True to overwrite")

    try:
        # Copy hook script
        shutil.copy2(hook_source, hook_dest)

        # Make executable
        hook_dest.chmod(0o755)

        logger.info(f"Installed pre-commit hook: {hook_dest}")
        return True

    except Exception as exc:
        logger.error(f"Failed to install hook: {exc}")
        return False


def uninstall_hooks(vault_path: Path) -> bool:
    """Uninstall pre-commit hook from vault repository.

    Args:
        vault_path: Path to vault root directory

    Returns:
        True if hook was uninstalled successfully
    """
    hook_path = get_hook_install_path(vault_path)

    if not hook_path.exists():
        logger.debug("Hook not installed, nothing to uninstall")
        return True

    try:
        hook_path.unlink()
        logger.info(f"Uninstalled pre-commit hook: {hook_path}")
        return True

    except Exception as exc:
        logger.error(f"Failed to uninstall hook: {exc}")
        return False
