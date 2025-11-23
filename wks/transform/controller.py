"""Transform controller with business logic."""

import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from pymongo.database import Database

from .models import TransformRecord, now_iso
from .cache import CacheManager
from .engines import get_engine


class TransformController:
    """Business logic for transform operations."""

    def __init__(self, db: Database, cache_dir: Path, max_size_bytes: int):
        """Initialize transform controller.

        Args:
            db: MongoDB database instance
            cache_dir: Directory for cached transforms
            max_size_bytes: Maximum cache size in bytes
        """
        self.db = db
        self.cache_manager = CacheManager(cache_dir, max_size_bytes, db)

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

    def _find_cached_transform(
        self, file_checksum: str, engine_name: str, options_hash: str
    ) -> Optional[TransformRecord]:
        """Find existing cached transform.

        Args:
            file_checksum: SHA-256 of file content
            engine_name: Transform engine name
            options_hash: Hash of engine options

        Returns:
            TransformRecord if found, None otherwise
        """
        doc = self.db.transform.find_one({
            "checksum": file_checksum,
            "engine": engine_name,
            "options_hash": options_hash
        })

        if not doc:
            return None

        return TransformRecord.from_dict(doc)

    def _update_last_accessed(self, file_checksum: str, engine_name: str, options_hash: str) -> None:
        """Update last_accessed timestamp for cache entry.

        Args:
            file_checksum: SHA-256 of file content
            engine_name: Transform engine name
            options_hash: Hash of engine options
        """
        self.db.transform.update_one(
            {
                "checksum": file_checksum,
                "engine": engine_name,
                "options_hash": options_hash
            },
            {"$set": {"last_accessed": now_iso()}}
        )

    def transform(
        self,
        file_path: Path,
        engine_name: str,
        options: Optional[Dict[str, Any]] = None,
        output_path: Optional[Path] = None
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
            cache_location=str(cache_location)
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
        result = self.db.transform.update_many(
            {"file_uri": old_uri},
            {"$set": {"file_uri": new_uri}}
        )
        return result.modified_count
