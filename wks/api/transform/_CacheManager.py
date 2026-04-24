import json
from pathlib import Path
from typing import Any

from wks.api.config.URI import URI
from wks.api.database.Database import Database


class _CacheManager:
    def __init__(self, cache_dir: Path, max_size_bytes: int, db: Database):
        self.cache_dir = Path(cache_dir)
        self.max_size_bytes = max_size_bytes
        self.db = db
        self.cache_json = self.cache_dir / "cache.json"

        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_cache_size(self) -> int:
        if not self.cache_json.exists():
            return 0
        try:
            with self.cache_json.open() as f:
                data = json.load(f)
            if "total_size_bytes" in data:
                return data["total_size_bytes"]
            return 0
        except Exception:
            return 0

    def _save_cache_size(self, total_size_bytes: int) -> None:
        with self.cache_json.open("w") as f:
            json.dump({"total_size_bytes": total_size_bytes}, f)

    def _get_lru_entries(self, bytes_needed: int) -> list[tuple[str, int, str]]:
        collection = self.db
        entries: list[tuple[str, int, str]] = []
        total_freed = 0

        cursor_bin: Any = collection.find().sort("last_accessed", 1)
        bin_entries: list[tuple[str, int, str, str]] = []
        for doc in cursor_bin:
            cache_uri = doc["cache_uri"]
            cache_path = URI(cache_uri).path
            if cache_path.suffix == ".bin":
                size_bytes = doc["size_bytes"]
                bin_entries.append((doc["checksum"], size_bytes, cache_uri, doc.get("last_accessed", "")))

        cursor_txt: Any = collection.find().sort("last_accessed", 1)
        txt_entries: list[tuple[str, int, str, str]] = []
        for doc in cursor_txt:
            cache_uri = doc["cache_uri"]
            cache_path = URI(cache_uri).path
            if cache_path.suffix == ".txt":
                size_bytes = doc["size_bytes"]
                txt_entries.append((doc["checksum"], size_bytes, cache_uri, doc.get("last_accessed", "")))

        cursor_other: Any = collection.find().sort("last_accessed", 1)
        other_entries: list[tuple[str, int, str, str]] = []
        for doc in cursor_other:
            cache_uri = doc["cache_uri"]
            cache_path = URI(cache_uri).path
            if cache_path.suffix not in (".bin", ".txt"):
                size_bytes = doc["size_bytes"]
                other_entries.append((doc["checksum"], size_bytes, cache_uri, doc.get("last_accessed", "")))

        bin_entries.sort(key=lambda x: x[3])
        txt_entries.sort(key=lambda x: x[3])
        other_entries.sort(key=lambda x: x[3])

        all_entries = bin_entries + txt_entries + other_entries

        for checksum, size_bytes, cache_uri, _ in all_entries:
            if total_freed >= bytes_needed:
                break
            entries.append((checksum, size_bytes, cache_uri))
            total_freed += size_bytes

        return entries

    def ensure_space(self, new_file_size: int) -> list[str] | None:
        current_size = self._load_cache_size()

        if current_size + new_file_size <= self.max_size_bytes:
            return None

        bytes_needed = (current_size + new_file_size) - self.max_size_bytes

        entries_to_evict = self._get_lru_entries(bytes_needed)

        if not entries_to_evict:
            return None

        evicted_locations: list[str] = []
        total_freed = 0

        for checksum, size_bytes, cache_uri in entries_to_evict:
            cache_path = URI(cache_uri).path
            if cache_path.exists():
                cache_path.unlink()

            self.db.delete_one({"checksum": checksum})

            evicted_locations.append(cache_uri)
            total_freed += size_bytes

        new_size = current_size - total_freed
        self._save_cache_size(new_size)

        return evicted_locations

    def add_file(self, file_size: int) -> None:
        current_size = self._load_cache_size()
        self._save_cache_size(current_size + file_size)

    def remove_file(self, file_size: int) -> None:
        current_size = self._load_cache_size()
        self._save_cache_size(max(0, current_size - file_size))

    def get_current_size(self) -> int:
        return self._load_cache_size()
