"""Helpful error messages for common WKS failure modes."""

import logging
import sys
from typing import NoReturn

logger = logging.getLogger(__name__)


def _emit_error(*lines: str) -> None:
    """Write error message lines to STDERR."""
    for line in lines:
        sys.stderr.write(line + "\n")


def mongodb_connection_error(mongo_uri: str, original_error: Exception) -> NoReturn:
    """Log and display helpful message for MongoDB connection failures and exit.

    Args:
        mongo_uri: The MongoDB URI that failed to connect
        original_error: The original exception
    """
    logger.error(f"MongoDB connection failed: {mongo_uri} - {original_error}")
    _emit_error(
        "",
        "=" * 70,
        "MONGODB CONNECTION FAILED",
        "=" * 70,
        f"\nCouldn't connect to MongoDB at: {mongo_uri}",
        f"\nOriginal error: {original_error}",
        "\nPossible solutions:",
        "  1. Start MongoDB if it's not running:",
        "     - macOS: brew services start mongodb-community",
        "     - Linux: sudo systemctl start mongod",
        "     - Or use: wksc daemon start (starts MongoDB automatically)",
        "\n  2. Check if MongoDB is running:",
        "     - macOS: brew services list | grep mongodb",
        "     - Linux: sudo systemctl status mongod",
        "\n  3. Verify the mongo.uri in ~/.wks/config.json",
        "     - Default: mongodb://localhost:27017/",
        "=" * 70,
        "",
    )
    sys.exit(1)


def missing_dependency_error(package_name: str, import_error: Exception) -> NoReturn:
    """Log and display helpful message for missing dependencies and exit.

    Args:
        package_name: Name of the missing package
        import_error: The original ImportError
    """
    logger.error(f"Missing dependency: {package_name} - {import_error}")
    _emit_error(
        "",
        "=" * 70,
        f"MISSING DEPENDENCY: {package_name}",
        "=" * 70,
        f"\nCouldn't import required package: {package_name}",
        f"\nOriginal error: {import_error}",
        "\nSolution:",
        "  Install WKS with all dependencies:",
        "     pip install -e '.[all]'",
        "\n  Or install specific package:",
        f"     pip install {package_name}",
        "=" * 70,
        "",
    )
    sys.exit(1)


def file_permission_error(file_path: str, operation: str, original_error: Exception) -> NoReturn:
    """Log and display helpful message for file permission errors and exit.

    Args:
        file_path: Path to the file that caused the error
        operation: Description of the operation (e.g., "read", "write", "delete")
        original_error: The original PermissionError
    """
    logger.error(f"File permission error: {operation} {file_path} - {original_error}")
    _emit_error(
        "",
        "=" * 70,
        "FILE PERMISSION ERROR",
        "=" * 70,
        f"\nCouldn't {operation}: {file_path}",
        f"\nOriginal error: {original_error}",
        "\nPossible solutions:",
        "  1. Check file permissions:",
        f"     ls -la '{file_path}'",
        "\n  2. Grant read/write permissions:",
        f"     chmod u+rw '{file_path}'",
        "\n  3. Check directory permissions:",
        f"     ls -la $(dirname '{file_path}')",
        "=" * 70,
        "",
    )
    sys.exit(1)


def vault_path_error(vault_path: str) -> NoReturn:
    """Log and display helpful message when Obsidian vault path is invalid.

    Args:
        vault_path: The invalid vault path
    """
    logger.error(f"Invalid Obsidian vault path: {vault_path}")
    _emit_error(
        "",
        "=" * 70,
        "INVALID OBSIDIAN VAULT PATH",
        "=" * 70,
        f"\nVault path does not exist: {vault_path}",
        "\nPlease verify:",
        "  1. ~/.wks/config.json includes either the new:",
        '       "vault": { "base_dir": "/path/to/vault", "wks_dir": "WKS", ... }',
        "     or the legacy:",
        '       "vault_path": "/path/to/vault"',
        "  2. The referenced directory exists and is accessible",
        "=" * 70,
        "",
    )
    sys.exit(1)


def model_download_error(model_name: str, original_error: Exception) -> NoReturn:
    """Log and display helpful message for model download failures.

    Args:
        model_name: Name of the model that failed to download
        original_error: The original exception
    """
    logger.error(f"Model download failed: {model_name} - {original_error}")
    _emit_error(
        "",
        "=" * 70,
        "MODEL DOWNLOAD FAILED",
        "=" * 70,
        f"\nCouldn't download model: {model_name}",
        f"\nOriginal error: {original_error}",
        "\nPossible solutions:",
        "  1. Check internet connection",
        "  2. Verify HuggingFace is accessible:",
        "     curl -I https://huggingface.co",
        "\n  3. Try downloading manually:",
        f"     python -c 'from sentence_transformers import SentenceTransformer; SentenceTransformer(\"{model_name}\")'",
        "\n  4. If behind proxy, set environment variables:",
        "     export HTTP_PROXY=http://proxy:port",
        "     export HTTPS_PROXY=http://proxy:port",
        "=" * 70,
        "",
    )
    sys.exit(1)
