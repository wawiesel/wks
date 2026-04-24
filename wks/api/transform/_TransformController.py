import contextlib
import hashlib
import re
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from wks.api.config.normalize_path import normalize_path
from wks.api.config.now_iso import now_iso

from ..config.URI import URI
from . import MAX_GENERATOR_ITERATIONS
from ._CacheManager import _CacheManager
from ._TransformRecord import _TransformRecord

if TYPE_CHECKING:
    from wks.api.database.Database import Database

    from .TransformConfig import TransformConfig


class _TransformController:
    def __init__(self, db: "Database", config: "TransformConfig", default_engine: str):
        self.db = db
        self.config = config
        self.default_engine = default_engine
        self.cache_manager = _CacheManager(Path(config.cache.base_dir), config.cache.max_size_bytes, db)

    def _compute_file_checksum(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with file_path.open("rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _update_graph(self, file_uri: URI, output_path: Path, referenced_uris: list[URI] | None = None):
        output_uri = URI.from_path(normalize_path(output_path))
        file_uri_str = str(file_uri)
        output_uri_str = str(output_uri)

        mongo_db: Any = self.db.get_database()

        mongo_db["nodes"].update_one(
            {"uri": file_uri_str}, {"$set": {"uri": file_uri_str, "type": "file"}}, upsert=True
        )

        mongo_db["nodes"].update_one(
            {"uri": output_uri_str}, {"$set": {"uri": output_uri_str, "type": "file", "generated": True}}, upsert=True
        )

        mongo_db["edges"].update_one(
            {"source": file_uri_str, "target": output_uri_str, "type": "transform"},
            {"$set": {"source": file_uri_str, "target": output_uri_str, "type": "transform", "created_at": now_iso()}},
            upsert=True,
        )

        if referenced_uris:
            for image_uri in referenced_uris:
                image_uri_str = str(image_uri)
                mongo_db["nodes"].update_one(
                    {"uri": image_uri_str},
                    {"$set": {"uri": image_uri_str, "type": "file", "generated": True}},
                    upsert=True,
                )

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
        key_str = f"{file_checksum}:{engine_name}:{options_hash}"
        return hashlib.sha256(key_str.encode()).hexdigest()

    def _find_cached_transform(
        self, file_checksum: str, engine_name: str, options_hash: str
    ) -> _TransformRecord | None:
        cursor: Any = self.db.find(
            {
                "checksum": file_checksum,
                "engine": engine_name,
                "options_hash": options_hash,
            }
        )

        cache_key = self._compute_cache_key(file_checksum, engine_name, options_hash)

        for doc in cursor:
            record = _TransformRecord.from_dict(doc)
            stored_path = Path(record.cache_path_from_uri())
            extension = stored_path.suffix.lstrip(".") or "md"
            cache_file = self.cache_manager.cache_dir / f"{cache_key}.{extension}"

            if cache_file.exists():
                if self._cached_transform_has_missing_local_refs(cache_file, record):
                    self._prune_stale_cached_transform(cache_file, record)
                    continue
                return record

        return None

    def _cached_transform_has_missing_local_refs(self, cache_file: Path, record: _TransformRecord) -> bool:
        if record.referenced_uris:
            return any(uri.is_file and not uri.path.exists() for uri in record.referenced_uris)

        if cache_file.suffix != ".md":
            return False

        content = cache_file.read_text(encoding="utf-8", errors="replace")
        destinations = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", content)
        for destination in destinations:
            local_path = self._resolve_local_markdown_destination(cache_file, destination)
            if local_path is not None and not local_path.exists():
                return True
        return False

    def _resolve_local_markdown_destination(self, cache_file: Path, destination: str) -> Path | None:
        cleaned = destination.strip()
        if cleaned.startswith("<") and cleaned.endswith(">"):
            cleaned = cleaned[1:-1].strip()

        if cleaned.startswith(("http://", "https://", "data:", "vault://")):
            return None

        if "://" in cleaned:
            uri = URI(cleaned)
            return uri.path if uri.is_file else None

        path = Path(cleaned)
        return path if path.is_absolute() else cache_file.parent / path

    def _prune_stale_cached_transform(self, cache_file: Path, record: _TransformRecord) -> None:
        if cache_file.exists():
            self.cache_manager.remove_file(cache_file.stat().st_size)
            cache_file.unlink()

        for uri in record.referenced_uris:
            if not uri.is_file:
                continue
            artifact_path = uri.path
            if artifact_path.exists():
                artifact_path.unlink()
                with contextlib.suppress(OSError):
                    artifact_path.parent.rmdir()

        self.db.delete_one(
            {
                "checksum": record.checksum,
                "engine": record.engine,
                "options_hash": record.options_hash,
            }
        )

    def _update_last_accessed(self, file_checksum: str, engine_name: str, options_hash: str) -> None:
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
        self._update_last_accessed(file_checksum, engine_name, options_hash)

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
        cache_key = self._compute_cache_key(file_checksum, engine_name, options_hash)
        extension = engine.get_extension(options)
        cache_location = self.cache_manager.cache_dir / f"{cache_key}.{extension}"

        cache_location.parent.mkdir(parents=True, exist_ok=True)

        self.cache_manager.ensure_space(file_size)

        gen = engine.transform(file_path, cache_location, options)
        referenced_uris_str: list[str] = []
        try:
            for _ in range(MAX_GENERATOR_ITERATIONS):
                msg = next(gen)
                yield msg
            next(gen)
            raise RuntimeError("Transform engine exceeded MAX_GENERATOR_ITERATIONS")
        except StopIteration as e:
            referenced_uris_str = e.value or []

        referenced_uris = [URI(uri_str) for uri_str in referenced_uris_str]

        if not cache_location.exists():
            raise RuntimeError(
                f"Transform engine failed to create cache file at {cache_location}. "
                f"Engine {engine_name} completed without error but file does not exist."
            )

        output_size = cache_location.stat().st_size

        self.cache_manager.add_file(output_size)

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

        self._update_graph(file_uri, cache_location, referenced_uris)

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
        file_path = normalize_path(file_path)

        if not file_path.exists() or not file_path.is_file():
            raise ValueError(f"File not found: {file_path}")

        from ._resolve_engine_selection import resolve_engine_selection

        selection = resolve_engine_selection(self.config.engines, engine_name, file_path, options)
        engine = selection.engine
        engine_name_for_cache = selection.cache_engine_name
        merged_options = selection.options

        file_uri = URI.from_path(file_path)
        file_checksum = self._compute_file_checksum(file_path)
        file_size = file_path.stat().st_size
        options_hash = engine.compute_options_hash(merged_options)

        cached = self._find_cached_transform(file_checksum, engine_name_for_cache, options_hash)

        if cached:
            return self._handle_cached_transform(
                cached, file_checksum, engine_name_for_cache, options_hash, output_path
            )

        return (
            yield from self._perform_new_transform(
                file_path,
                file_uri,
                file_checksum,
                file_size,
                engine_name_for_cache,
                engine,
                merged_options,
                options_hash,
                output_path,
            )
        )

    def _copy_cache_file_to_output(self, cache_file: Path, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists():
            raise FileExistsError(f"Output file already exists: {output_path}")

        try:
            import os

            os.link(cache_file, output_path)
        except (OSError, AttributeError):
            output_path.write_bytes(cache_file.read_bytes())

    def _find_matching_record_in_db(self, cache_key: str) -> _TransformRecord | None:
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
        stored_path = Path(matching_record.cache_path_from_uri())
        extension = stored_path.suffix.lstrip(".") or "md"  # Default to .md if no extension
        cache_file = self.cache_manager.cache_dir / f"{cache_key}.{extension}"

        if not cache_file.exists():
            candidates = list(self.cache_manager.cache_dir.glob(f"{cache_key}.*"))
            if candidates:
                cache_file = candidates[0]

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
        matching_record = self._find_matching_record_in_db(cache_key)

        if not matching_record:
            raise ValueError(f"Checksum not found in database: {cache_key}")

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
        from wks.api.config.normalize_path import normalize_path

        file_path = normalize_path(target)

        if not file_path.exists():
            raise ValueError(f"File not found: {file_path}")

        gen = self.transform(file_path, self.default_engine, {})
        try:
            for _ in range(MAX_GENERATOR_ITERATIONS):
                next(gen)
            next(gen)
            raise RuntimeError("Transform generator exceeded MAX_GENERATOR_ITERATIONS")
        except StopIteration as e:
            cache_key, _ = e.value

        return self.get_content(cache_key, output_path)

    def get_content(self, target: str, output_path: Path | None = None) -> str:
        if re.match(r"^[a-f0-9]{64}$", target):
            return self._get_content_by_checksum(target, output_path)
        else:
            return self._get_content_by_file_path(target, output_path)
