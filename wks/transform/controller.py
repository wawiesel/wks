"""Transform controller with business logic."""

import hashlib
import re
from pathlib import Path
from typing import Any

from pymongo.database import Database

from .cache import CacheManager
from .engines import get_engine
from .models import TransformRecord, now_iso


class TransformController:
    """Business logic for transform operations."""

    def __init__(self, db: Database, cache_dir: Path, max_size_bytes: int, default_engine: str = "docling"):
        """Initialize transform controller.

        Args:
            db: MongoDB database instance
            cache_dir: Directory for cached transforms
            max_size_bytes: Maximum cache size in bytes
            default_engine: Default engine to use for transforms
        """
        self.db = db
        self.cache_manager = CacheManager(cache_dir, max_size_bytes, db)
        self.default_engine = default_engine

    def _compute_file_checksum(self, file_path: Path) -> str:
        """Compute SHA-256 checksum of file.

        Args:
            file_path: Path to file

        Returns:
            Hex digest of SHA-256 checksum
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _compute_cache_key(self, file_checksum: str, engine_name: str, options_hash: str) -> str:
        """Compute cache key from file, engine, and options.

        Args:
            file_checksum: SHA-256 of file content
            engine_name: Transform engine name
            options_hash: Hash of engine options

        Returns:
            Cache key checksum
        """
        key_str = f"{file_checksum}:{engine_name}:{options_hash}"
        return hashlib.sha256(key_str.encode()).hexdigest()

    def _find_cached_transform(self, file_checksum: str, engine_name: str, options_hash: str) -> TransformRecord | None:
        """Find existing cached transform.

        Args:
            file_checksum: SHA-256 of file content
            engine_name: Transform engine name
            options_hash: Hash of engine options

        Returns:
            TransformRecord if found, None otherwise
        """
        cursor = self.db.transform.find(
            {
                "checksum": file_checksum,
                "engine": engine_name,
                "options_hash": options_hash,
            }
        )

        for doc in cursor:
            record = TransformRecord.from_dict(doc)
            cache_path = Path(record.cache_location)
            if cache_path.exists():
                return record

            return None

    def _update_last_accessed(self, file_checksum: str, engine_name: str, options_hash: str) -> None:
        """Update last_accessed timestamp for cache entry.

        Args:
            file_checksum: SHA-256 of file content
            engine_name: Transform engine name
            options_hash: Hash of engine options
        """
        self.db.transform.update_one(
            {"checksum": file_checksum, "engine": engine_name, "options_hash": options_hash},
            {"$set": {"last_accessed": now_iso()}},
        )

    def transform(
        self,
        file_path: Path,
        engine_name: str,
        options: dict[str, Any] | None = None,
        output_path: Path | None = None,
    ) -> str:
        """Transform file using specified engine.

        Args:
            file_path: Path to file to transform
            engine_name: Transform engine name (e.g., "docling")
            options: Engine-specific options (or None for defaults)
            output_path: Optional output file path

        Returns:
            Cache key checksum

        Raises:
            ValueError: If file doesn't exist or engine not found
            RuntimeError: If transform fails
        """
        file_path = file_path.resolve()

        if not file_path.exists() or not file_path.is_file():
            raise ValueError(f"File not found: {file_path}")

        # Get engine
        engine = get_engine(engine_name)
        if not engine:
            raise ValueError(f"Unknown engine: {engine_name}")

        # Get file info
        file_uri = f"file://{file_path}"
        file_checksum = self._compute_file_checksum(file_path)
        file_size = file_path.stat().st_size

        # Get options and compute hash
        options = options or {}
        options_hash = engine.compute_options_hash(options)

        # Check if already cached
        cached = self._find_cached_transform(file_checksum, engine_name, options_hash)

        if cached:
            # Update last accessed
            self._update_last_accessed(file_checksum, engine_name, options_hash)

            # Copy to output if requested
            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path = Path(cached.cache_location)
                if cache_path.exists():
                    output_path.write_bytes(cache_path.read_bytes())

            return self._compute_cache_key(file_checksum, engine_name, options_hash)

        # Not cached - need to transform
        cache_key = self._compute_cache_key(file_checksum, engine_name, options_hash)
        extension = engine.get_extension(options)
        cache_location = self.cache_manager.cache_dir / f"{cache_key}.{extension}"

        # Ensure space in cache
        self.cache_manager.ensure_space(file_size)

        # Perform transform
        engine.transform(file_path, cache_location, options)

        # Get actual output size
        output_size = cache_location.stat().st_size

        # Add to cache size tracking
        self.cache_manager.add_file(output_size)

        # Store in database
        record = TransformRecord(
            file_uri=file_uri,
            checksum=file_checksum,
            size_bytes=output_size,
            last_accessed=now_iso(),
            created_at=now_iso(),
            engine=engine_name,
            options_hash=options_hash,
            cache_location=str(cache_location),
        )

        self.db.transform.insert_one(record.to_dict())

        # Copy to output if requested
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(cache_location.read_bytes())

        return cache_key

    def remove_by_uri(self, file_uri: str) -> int:
        """Remove all transforms for a file URI.

        Args:
            file_uri: File URI to remove

        Returns:
            Number of records removed
        """
        # Find all transforms for this URI
        docs = list(self.db.transform.find({"file_uri": file_uri}))

        count = 0
        for doc in docs:
            # Remove cache file
            cache_path = Path(doc["cache_location"])
            if cache_path.exists():
                cache_path.unlink()
                self.cache_manager.remove_file(doc["size_bytes"])

            # Remove from database
            self.db.transform.delete_one({"_id": doc["_id"]})
            count += 1

        return count

    def update_uri(self, old_uri: str, new_uri: str) -> int:
        """Update file URI in all transform records.

        Args:
            old_uri: Old file URI
            new_uri: New file URI

        Returns:
            Number of records updated
        """
        result = self.db.transform.update_many({"file_uri": old_uri}, {"$set": {"file_uri": new_uri}})
        return result.modified_count

    def get_content(self, target: str, output_path: Path | None = None) -> str:
        """Retrieve content for a target (checksum or file path).

        Args:
            target: Checksum (64 hex chars) or file path
            output_path: Optional output file path

        Returns:
            Content as string

        Raises:
            ValueError: If target not found or invalid
        """
        # Check if target is a checksum
        if re.match(r"^[a-f0-9]{64}$", target):
            cache_key = target

            # First, prefer the cache directory as the source of truth.
            candidates = list(self.cache_manager.cache_dir.glob(f"{cache_key}.*"))
            cache_file: Path | None = candidates[0] if candidates else None

            if cache_file is not None and cache_file.exists():
                if output_path:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        import os

                        if output_path.exists():
                            raise FileExistsError(f"Output file already exists: {output_path}")
                        os.link(cache_file, output_path)
                    except (OSError, AttributeError):
                        output_path.write_bytes(cache_file.read_bytes())
                return cache_file.read_text(encoding="utf-8")

            # Fallback: resolve via database metadata to support older entries.
            records = list(self.db.transform.find())
            matching_record = None

            for doc in records:
                record_checksum = doc["checksum"]
                record_engine = doc["engine"]
                record_options_hash = doc["options_hash"]
                computed_key = self._compute_cache_key(record_checksum, record_engine, record_options_hash)
                if computed_key == cache_key:
                    matching_record = TransformRecord.from_dict(doc)
                    break

            if not matching_record:
                raise ValueError(f"Cache entry not found: {cache_key}")

            # Reconstruct cache file path in current cache directory using stored extension
            # This avoids using old absolute paths from previous test runs
            stored_path = Path(matching_record.cache_location)
            extension = stored_path.suffix.lstrip(".") or "md"  # Default to .md if no extension
            cache_file = self.cache_manager.cache_dir / f"{cache_key}.{extension}"

            # If file doesn't exist, try globbing one more time (in case extension differs)
            if not cache_file.exists():
                candidates = list(self.cache_manager.cache_dir.glob(f"{cache_key}.*"))
                if candidates:
                    cache_file = candidates[0]

            if not cache_file.exists():
                raise ValueError(
                    f"Cache file not found for {cache_key} in cache directory: {self.cache_manager.cache_dir}"
                )

            self._update_last_accessed(
                matching_record.checksum,
                matching_record.engine,
                matching_record.options_hash,
            )

            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    import os

                    if output_path.exists():
                        raise FileExistsError(f"Output file already exists: {output_path}")
                    os.link(cache_file, output_path)
                except (OSError, AttributeError):
                    output_path.write_bytes(cache_file.read_bytes())

            return cache_file.read_text(encoding="utf-8")

        else:
            # Target is a file path
            # We need to expand user if it's a path string, but here we expect absolute path or handle it
            # The controller usually expects Path objects or absolute strings.
            # Let's assume the caller handles expansion if it's a CLI arg,
            # but for robustness we can try to expand if it looks like a path.

            # However, in MCP context, paths should be absolute.
            # In CLI context, they are expanded before calling.
            # But let's be safe.
            from ..utils import expand_path

            try:
                file_path = expand_path(target)
            except Exception:
                file_path = Path(target).resolve()

            if not file_path.exists():
                raise ValueError(f"File not found: {file_path}")

            # Transform it (using default engine/options for now)
            # This ensures we have the content in cache
            cache_key = self.transform(file_path, self.default_engine, {})

            # Now recurse to get the content from cache
            return self.get_content(cache_key, output_path)
