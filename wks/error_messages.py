"""Helpful error messages for common WKS failure modes."""

import sys
from typing import NoReturn


def mongodb_connection_error(mongo_uri: str, original_error: Exception) -> NoReturn:
    """Print helpful message for MongoDB connection failures and exit.

    Args:
        mongo_uri: The MongoDB URI that failed to connect
        original_error: The original exception
    """
    print("\n" + "=" * 70)
    print("MONGODB CONNECTION FAILED")
    print("=" * 70)
    print(f"\nCouldn't connect to MongoDB at: {mongo_uri}")
    print(f"\nOriginal error: {original_error}")
    print("\nPossible solutions:")
    print("  1. Start MongoDB if it's not running:")
    print("     - macOS: brew services start mongodb-community")
    print("     - Linux: sudo systemctl start mongod")
    print("     - Or use: wks0 daemon start (starts MongoDB automatically)")
    print("\n  2. Check if MongoDB is running:")
    print("     - macOS: brew services list | grep mongodb")
    print("     - Linux: sudo systemctl status mongod")
    print("\n  3. Verify the mongo.uri in ~/.wks/config.json")
    print("     - Default: mongodb://localhost:27017/")
    print("=" * 70 + "\n")
    sys.exit(1)


def missing_dependency_error(package_name: str, import_error: Exception) -> NoReturn:
    """Print helpful message for missing dependencies and exit.

    Args:
        package_name: Name of the missing package
        import_error: The original ImportError
    """
    print("\n" + "=" * 70)
    print(f"MISSING DEPENDENCY: {package_name}")
    print("=" * 70)
    print(f"\nCouldn't import required package: {package_name}")
    print(f"\nOriginal error: {import_error}")
    print("\nSolution:")
    print(f"  Install WKS with all dependencies:")
    print(f"     pip install -e '.[all]'")
    print("\n  Or install specific package:")
    print(f"     pip install {package_name}")
    print("=" * 70 + "\n")
    sys.exit(1)


def file_permission_error(file_path: str, operation: str, original_error: Exception) -> NoReturn:
    """Print helpful message for file permission errors and exit.

    Args:
        file_path: Path to the file that caused the error
        operation: Description of the operation (e.g., "read", "write", "delete")
        original_error: The original PermissionError
    """
    print("\n" + "=" * 70)
    print("FILE PERMISSION ERROR")
    print("=" * 70)
    print(f"\nCouldn't {operation}: {file_path}")
    print(f"\nOriginal error: {original_error}")
    print("\nPossible solutions:")
    print("  1. Check file permissions:")
    print(f"     ls -la '{file_path}'")
    print("\n  2. Grant read/write permissions:")
    print(f"     chmod u+rw '{file_path}'")
    print("\n  3. Check directory permissions:")
    print(f"     ls -la $(dirname '{file_path}')")
    print("=" * 70 + "\n")
    sys.exit(1)


def vault_path_error(vault_path: str) -> NoReturn:
    """Print helpful message when Obsidian vault path is invalid.

    Args:
        vault_path: The invalid vault path
    """
    print("\n" + "=" * 70)
    print("INVALID OBSIDIAN VAULT PATH")
    print("=" * 70)
    print(f"\nVault path does not exist: {vault_path}")
    print("\nPlease verify:")
    print("  1. The vault_path in ~/.wks/config.json points to your Obsidian vault")
    print("  2. The directory exists and is accessible")
    print("\nExample config.json:")
    print('  {')
    print('    "vault_path": "~/obsidian",')
    print('    ...')
    print('  }')
    print("=" * 70 + "\n")
    sys.exit(1)


def model_download_error(model_name: str, original_error: Exception) -> NoReturn:
    """Print helpful message for model download failures.

    Args:
        model_name: Name of the model that failed to download
        original_error: The original exception
    """
    print("\n" + "=" * 70)
    print("MODEL DOWNLOAD FAILED")
    print("=" * 70)
    print(f"\nCouldn't download model: {model_name}")
    print(f"\nOriginal error: {original_error}")
    print("\nPossible solutions:")
    print("  1. Check internet connection")
    print("  2. Verify HuggingFace is accessible:")
    print("     curl -I https://huggingface.co")
    print("\n  3. Try downloading manually:")
    print(f"     python -c 'from sentence_transformers import SentenceTransformer; SentenceTransformer(\"{model_name}\")'")
    print("\n  4. If behind proxy, set environment variables:")
    print("     export HTTP_PROXY=http://proxy:port")
    print("     export HTTPS_PROXY=http://proxy:port")
    print("=" * 70 + "\n")
    sys.exit(1)
