"""Transform controller with business logic."""

import hashlib
import re
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from wks.api.config.normalize_path import normalize_path
from wks.api.config.now_iso import now_iso

from ..config.URI import URI
from ._CacheManager import _CacheManager
from ._get_engine_by_type import _get_engine_by_type
from ._TransformRecord import _TransformRecord

if TYPE_CHECKING:
    from wks.api.database.Database import Database

    from .TransformConfig import TransformConfig


class _TransformController:
    """Business logic for transform operations."""

    def __init__(self, db: "Database", config: "TransformConfig", default_engine: str):
        """Initialize transform controller.

        Args:
            db: Database facade
            config: Transform configuration object
            default_engine: Default engine name (from CatConfig)
        """
        self.db = db
        self.config = config
        self.default_engine = default_engine
        self.cache_manager = _CacheManager(Path(config.cache.base_dir), config.cache.max_size_bytes, db)

    def _compute_file_checksum(self, file_path: Path) -> str:
        """Compute SHA-256 checksum of file.

        Args:
            file_path: Path to file

        Returns:
            Hex digest of SHA-256 checksum
        """
        sha256 = hashlib.sha256()
        with file_path.open("rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _update_graph(self, file_uri: URI, output_path: Path, referenced_uris: list[URI] | None = None):
        """Update Knowledge Graph with new transform edge.

        Args:
            file_uri: Source file URI (file://...)
            output_path: Path to the cached output file
            referenced_uris: List of referenced image URIs
        """
        output_uri = URI.from_path(normalize_path(output_path))
        file_uri_str = str(file_uri)
        output_uri_str = str(output_uri)

        # Get raw database object for accessing other collections
        mongo_db: Any = self.db.get_database()

        # 1. Upsert Source Node
        mongo_db["nodes"].update_one(
            {"uri": file_uri_str}, {"$set": {"uri": file_uri_str, "type": "file"}}, upsert=True
        )

        # 2. Upsert Output Node
        mongo_db["nodes"].update_one(
            {"uri": output_uri_str}, {"$set": {"uri": output_uri_str, "type": "file", "generated": True}}, upsert=True
        )

        # 3. Upsert Edge (Source -> Output)
        mongo_db["edges"].update_one(
            {"source": file_uri_str, "target": output_uri_str, "type": "transform"},
            {"$set": {"source": file_uri_str, "target": output_uri_str, "type": "transform", "created_at": now_iso()}},
            upsert=True,
        )

        # 4. Handle Referenced Images (Output -> Image)
        if referenced_uris:
            for image_uri in referenced_uris:
                image_uri_str = str(image_uri)
                # 4a. Upsert Image Node
                mongo_db["nodes"].update_one(
                    {"uri": image_uri_str},
                    {"$set": {"uri": image_uri_str, "type": "file", "generated": True}},
                    upsert=True,
                )

                # 4b. Upsert Edge (Output -> Image)
                mongo_db["edges"].update_one(
                    {"source": output_uri_str, "target": image_uri_str, "type": "refers_to"},
                    {
                        "$set": {
                            "source": output_uri_str,
                            "target": image_uri_str,
                            "type": "refers_to",
                            "created_at": now_iso(),
                        }
                    },
                    upsert=True,
                )

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
    ) -> _TransformRecord | None:
        """Find existing cached transform.

        Args:
            file_checksum: SHA-256 of file content
            engine_name: Transform engine name
            options_hash: Hash of engine options

        Returns:
            TransformRecord if found, None otherwise
        """
        cursor: Any = self.db.find(
            {
                "checksum": file_checksum,
                "engine": engine_name,
                "options_hash": options_hash,
            }
        )

        # Compute cache key to find file in current cache directory
        cache_key = self._compute_cache_key(file_checksum, engine_name, options_hash)

        for doc in cursor:
            record = _TransformRecord.from_dict(doc)
            # Check if file exists in current cache directory (not stored absolute path)
            # This handles cases where temp directories are cleaned up between test runs
            stored_path = Path(record.cache_path_from_uri())
            extension = stored_path.suffix.lstrip(".") or "md"
            cache_file = self.cache_manager.cache_dir / f"{cache_key}.{extension}"

            if cache_file.exists():
                return record

        return None

    def _update_last_accessed(self, file_checksum: str, engine_name: str, options_hash: str) -> None:
        """Update last_accessed timestamp for cache entry.

        Args:
            file_checksum: SHA-256 of file content
            engine_name: Transform engine name
            options_hash: Hash of engine options
        """
        self.db.update_one(
            {"checksum": file_checksum, "engine": engine_name, "options_hash": options_hash},
            {"$set": {"last_accessed": now_iso()}},
        )

    def _handle_cached_transform(
        self,
        cached: _TransformRecord,
        file_checksum: str,
        engine_name: str,
        options_hash: str,
        output_path: Path | None,
    ) -> tuple[str, bool]:
        """Handle transform when result is already cached.

        Args:
            cached: Cached transform record
            file_checksum: File checksum
            engine_name: Engine name
            options_hash: Options hash
            output_path: Optional output path

        Returns:
            Tuple of (Cache key, cached_status=True)
        """
        # Update last accessed
        self._update_last_accessed(file_checksum, engine_name, options_hash)

        # Copy to output if requested
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path = Path(cached.cache_path_from_uri())
            if cache_path.exists():
                output_path.write_bytes(cache_path.read_bytes())

        cache_key = self._compute_cache_key(file_checksum, engine_name, options_hash)
        return cache_key, True

    def _perform_new_transform(
        self,
        file_path: Path,
        file_uri: URI,
        file_checksum: str,
        file_size: int,
        engine_name: str,
        engine: Any,
        options: dict[str, Any],
        options_hash: str,
        output_path: Path | None,
    ) -> Generator[str, None, tuple[str, bool]]:
        """Perform a new transform (not cached).

        Args:
            file_path: Path to file
            file_uri: File URI
            file_checksum: File checksum
            file_size: File size in bytes
            engine_name: Engine name
            engine: Engine instance
            options: Engine options
            options_hash: Options hash
            output_path: Optional output path

        Returns:
            Generator yielding progress strings and returning (Cache key, cached_status=False)

        Raises:
            RuntimeError: If transform fails to create cache file
        """
        cache_key = self._compute_cache_key(file_checksum, engine_name, options_hash)
        extension = engine.get_extension(options)
        cache_location = self.cache_manager.cache_dir / f"{cache_key}.{extension}"

        # Ensure cache directory exists
        cache_location.parent.mkdir(parents=True, exist_ok=True)

        # Ensure space in cache
        self.cache_manager.ensure_space(file_size)

        # Perform transform
        # Engine yields progress string, returns referenced_uris (list[str])
        gen = engine.transform(file_path, cache_location, options)
        referenced_uris_str: list[str] = []
        try:
            while True:
                msg = next(gen)
                yield msg
        except StopIteration as e:
            referenced_uris_str = e.value or []

        # Convert referenced URIs to URI objects
        referenced_uris = [URI(uri_str) for uri_str in referenced_uris_str]

        # Verify file was created
        if not cache_location.exists():
            raise RuntimeError(
                f"Transform engine failed to create cache file at {cache_location}. "
                f"Engine {engine_name} completed without error but file does not exist."
            )

        # Get actual output size
        output_size = cache_location.stat().st_size

        # Add to cache size tracking
        self.cache_manager.add_file(output_size)

        # Store in database
        record = _TransformRecord(
            file_uri=file_uri,
            cache_uri=URI.from_path(cache_location),
            checksum=file_checksum,
            size_bytes=output_size,
            last_accessed=now_iso(),
            created_at=now_iso(),
            engine=engine_name,
            options_hash=options_hash,
            referenced_uris=referenced_uris,
        )

        self.db.insert_one(record.to_dict())

        # Update Graph
        # We need the output path corresponding to the cache file?
        # Graph updates use the cache URI as the 'output' node.
        # But wait, original _update_graph isn't called here?
        # Ah, _update_graph is missing from _perform_new_transform in the original code?
        # Let me check... I don't see _update_graph called in the view_file of 1.
        # It seems graph updating was missing or implicit?
        # Wait, step 3947 view shows _update_graph method existing but NOT CALLED in _perform_new_transform.
        # This might be a bug or intentional separation.
        # If I want to update the graph, I should call it here.
        # The user specifically requested "additional edges".
        self._update_graph(file_uri, cache_location, referenced_uris)

        # Copy to output if requested
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(cache_location.read_bytes())

        return cache_key, False

    def transform(
        self,
        file_path: Path,
        engine_name: str,
        options: dict[str, Any] | None = None,
        output_path: Path | None = None,
    ) -> Generator[str, None, tuple[str, bool]]:
        """Transform file using specified engine.

        Returns:
            Generator yielding progress strings.
            Returns tuple (cache_key, cached_boolean) on completion.
        """
        file_path = normalize_path(file_path)

        if not file_path.exists() or not file_path.is_file():
            raise ValueError(f"File not found: {file_path}")

        # Get engine config
        if engine_name not in self.config.engines:
            raise ValueError(
                f"Engine '{engine_name}' not found in config. Available engines: {list(self.config.engines.keys())}"
            )

        engine_config = self.config.engines[engine_name]

        # Get engine instance
        engine = _get_engine_by_type(engine_config.type)

        # Merge base options with overrides
        merged_options = {**engine_config.data, **(options or {})}

        # Compute file info
        file_uri = URI.from_path(file_path)
        file_checksum = self._compute_file_checksum(file_path)
        file_size = file_path.stat().st_size
        options_hash = engine.compute_options_hash(merged_options)

        # Check cache
        cached = self._find_cached_transform(file_checksum, engine_name, options_hash)

        if cached:
            return self._handle_cached_transform(cached, file_checksum, engine_name, options_hash, output_path)

        # Perform new transform
        return (
            yield from self._perform_new_transform(
                file_path,
                file_uri,
                file_checksum,
                file_size,
                engine_name,
                engine,
                merged_options,
                options_hash,
                output_path,
            )
        )

    def _copy_cache_file_to_output(self, cache_file: Path, output_path: Path) -> None:
        """Copy cache file to output path.

        Args:
            cache_file: Source cache file path
            output_path: Destination output file path

        Raises:
            FileExistsError: If output file already exists (when hard link fails)
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists():
            raise FileExistsError(f"Output file already exists: {output_path}")

        try:
            import os

            os.link(cache_file, output_path)
        except (OSError, AttributeError):
            output_path.write_bytes(cache_file.read_bytes())

    def _find_matching_record_in_db(self, cache_key: str) -> _TransformRecord | None:
        """Find matching transform record in database by cache key.

        Args:
            cache_key: Cache key to search for

        Returns:
            TransformRecord if found, None otherwise
        """
        records: list[dict[str, Any]] = list(self.db.find())
        for doc in records:
            record_checksum = doc["checksum"]
            record_engine = doc["engine"]
            record_options_hash = doc["options_hash"]
            computed_key = self._compute_cache_key(record_checksum, record_engine, record_options_hash)
            if computed_key == cache_key:
                return _TransformRecord.from_dict(doc)
        return None

    def _resolve_cache_file_from_db(self, cache_key: str, matching_record: _TransformRecord) -> Path:
        """Resolve cache file path from database record and verify existence.

        This method enforces Cache-Database Sync Invariant #3: All access through
        database. If the file is missing from the cache directory but a record
        exists in the database, the record is considered stale and is pruned.

        Args:
            cache_key: Cache key checksum
            matching_record: Matching transform record from database

        Returns:
            Path to existing cache file

        Raises:
            ValueError: If cache file not found; stale record is pruned from DB.
        """
        stored_path = Path(matching_record.cache_path_from_uri())
        extension = stored_path.suffix.lstrip(".") or "md"  # Default to .md if no extension
        cache_file = self.cache_manager.cache_dir / f"{cache_key}.{extension}"

        # If file doesn't exist, try globbing one more time (in case extension differs)
        if not cache_file.exists():
            candidates = list(self.cache_manager.cache_dir.glob(f"{cache_key}.*"))
            if candidates:
                cache_file = candidates[0]

        # If file still doesn't exist, clean up stale record and raise error
        if not cache_file.exists():
            self.db.delete_one(
                {
                    "checksum": matching_record.checksum,
                    "engine": matching_record.engine,
                    "options_hash": matching_record.options_hash,
                }
            )
            raise ValueError(
                f"Cache file missing for {cache_key}. Database record existed but "
                f"file was not found in {self.cache_manager.cache_dir}. Stale record pruned."
            )

        return cache_file

    def _get_content_by_checksum(self, cache_key: str, output_path: Path | None = None) -> str:
        """Get content by cache key (checksum).

        Per Cache-Database Sync Invariant #3: All access through database.
        The database is the sole authority - we MUST verify the checksum
        exists in the database before reading the cache file.

        Args:
            cache_key: 64-character hex cache key
            output_path: Optional output file path

        Returns:
            Content as string

        Raises:
            ValueError: If cache entry not found in database or cache file is missing.
        """
        # Per spec: Database is sole authority - check DB first
        matching_record = self._find_matching_record_in_db(cache_key)

        if not matching_record:
            raise ValueError(f"Checksum not found in database: {cache_key}")

        # Get cache file path from database record. This will prune DB if file missing.
        cache_file = self._resolve_cache_file_from_db(cache_key, matching_record)

        self._update_last_accessed(
            matching_record.checksum,
            matching_record.engine,
            matching_record.options_hash,
        )

        if output_path:
            self._copy_cache_file_to_output(cache_file, output_path)

        return cache_file.read_text(encoding="utf-8")

    def _get_content_by_file_path(self, target: str, output_path: Path | None = None) -> str:
        """Get content by file path (transforms file first).

        Args:
            target: File path string
            output_path: Optional output file path

        Returns:
            Content as string

        Raises:
            ValueError: If file not found
        """
        from wks.api.config.normalize_path import normalize_path

        file_path = normalize_path(target)

        if not file_path.exists():
            raise ValueError(f"File not found: {file_path}")

        # Transform it (using default engine/options for now)
        # This ensures we have the content in cache
        gen = self.transform(file_path, self.default_engine, {})
        # Consume generator to get return value
        try:
            while True:
                next(gen)
        except StopIteration as e:
            cache_key, _ = e.value

        # Now recurse to get the content from cache
        return self.get_content(cache_key, output_path)

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
            return self._get_content_by_checksum(target, output_path)
        else:
            return self._get_content_by_file_path(target, output_path)
