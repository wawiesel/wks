from __future__ import annotations

import hashlib
import logging
import os
import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, unquote

import numpy as np
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer

from .extractor import Extractor, ExtractResult
from .status import record_db_activity


def _utc_now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 with Z suffix."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        s = ts.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _as_file_uri(path: Path) -> str:
    try:
        return path.resolve().as_uri()
    except ValueError:
        return "file://" + path.resolve().as_posix()


class SimilarityDB:
    """Space database wrapper: manages embeddings and extraction artefacts."""

    def __init__(
        self,
        database_name: str = "wks_similarity",
        collection_name: str = "file_embeddings",
        mongo_uri: str = "mongodb://localhost:27017/",
        model_name: str = "all-MiniLM-L6-v2",
        model_path: Optional[str] = None,
        offline: bool = False,
        min_chars: int = 10,
        max_chars: int = 200_000,
        chunks_collection: str = "file_chunks",
        chunk_chars: int = 1_500,
        chunk_overlap: int = 200,
        extract_engine: str = "docling",
        extract_ocr: bool = False,
        extract_timeout_secs: int = 30,
        extract_options: Optional[Dict[str, Any]] = None,
        write_extension: Optional[str] = None,
        mongo_client: Optional[MongoClient] = None,
    ) -> None:
        if mongo_client is not None:
            self.client = mongo_client
            self._own_client = False
        else:
            self.client = MongoClient(mongo_uri)
            self._own_client = True
        self.db = self.client[database_name]
        self.collection = self.db[collection_name]
        self.chunks = self.db[chunks_collection]
        self.changes = self.db["embedding_changes"]

        if offline:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        os.environ.setdefault("SENTENCE_TRANSFORMERS_DISABLE_DEFAULT_PROGRESS_BAR", "1")
        logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

        target = (model_path or model_name).strip()
        self.model_name = model_name
        self.model = SentenceTransformer(target)

        self.min_chars = int(min_chars)
        self.max_chars = int(max_chars)
        self.chunk_chars = int(chunk_chars)
        self.chunk_overlap = int(chunk_overlap)

        self.extractor = Extractor(
            engine=extract_engine or "docling",
            ocr=bool(extract_ocr),
            timeout_secs=int(extract_timeout_secs),
            options=dict(extract_options or {}),
            max_chars=self.max_chars,
            write_extension=write_extension or "md",
        )

        self._ensure_indexes()
        self._empty_embedding: Optional[List[float]] = None
        self._last_add_result: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------ #
    def _ensure_indexes(self) -> None:
        self.collection.create_index("path", unique=True)
        self.collection.create_index("checksum")
        self.collection.create_index("path_local")
        self.chunks.create_index([("file_path", 1), ("chunk_index", 1)], unique=True)
        self.chunks.create_index([("file_path", 1), ("chunk_id", 1)], unique=True)
        self.chunks.create_index("timestamp")
        self.changes.create_index([("file_path", 1), ("t_new_epoch", 1)])

    @staticmethod
    def _file_digest(path: Path) -> Tuple[str, int]:
        hasher = hashlib.sha256()
        size = 0
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                if not chunk:
                    break
                hasher.update(chunk)
                size += len(chunk)
        return hasher.hexdigest(), size

    @staticmethod
    def _chunk_text(text: str, chunk_chars: int, chunk_overlap: int) -> List[str]:
        if not text:
            return []
        n = max(256, int(chunk_chars))
        ov = max(0, min(int(chunk_overlap), n - 1))
        chunks: List[str] = []
        i = 0
        L = len(text)
        while i < L:
            j = min(L, i + n)
            chunk = text[i:j]
            if chunk:
                chunks.append(chunk)
            if j >= L:
                break
            i = j - ov
        if not chunks:
            chunks.append(text)
        return chunks

    @staticmethod
    def _cleanup_content_file(content_path: Optional[str]) -> None:
        if not content_path:
            return
        try:
            artefact = Path(content_path)
            if artefact.exists():
                artefact.unlink()
                parent = artefact.parent
                if parent.is_dir():
                    try:
                        next(parent.iterdir())
                    except StopIteration:
                        parent.rmdir()
        except Exception:
            pass

    def _update_related_paths(self, old_uri: Optional[str], new_uri: str, new_local: str) -> None:
        if not old_uri or old_uri == new_uri:
            return
        try:
            self.chunks.update_many(
                {"file_path": old_uri},
                {"$set": {"file_path": new_uri, "file_local": new_local}},
            )
        except Exception:
            pass
        try:
            self.changes.update_many(
                {"file_path": old_uri},
                {"$set": {"file_path": new_uri}},
            )
        except Exception:
            pass
        try:
            self.db["file_snapshots"].update_many(
                {"path": old_uri},
                {"$set": {"path": new_uri}},
            )
        except Exception:
            pass

    def close(self) -> None:
        if getattr(self, "_own_client", False):
            try:
                self.client.close()
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    def _embed_text(
        self,
        file_uri: str,
        path_local: str,
        text: str,
        content_checksum: Optional[str],
        timestamp: str,
    ) -> Tuple[List[float], List[Dict[str, Any]]]:
        chunks = self._chunk_text(text, self.chunk_chars, self.chunk_overlap)
        vectors: List[np.ndarray] = []
        docs: List[Dict[str, Any]] = []
        for idx, chunk in enumerate(chunks):
            try:
                vec = np.array(self.model.encode(chunk, show_progress_bar=False), dtype=float)
            except Exception:
                continue
            vectors.append(vec)
            docs.append(
                {
                    "file_path": file_uri,
                    "file_local": path_local,
                    "chunk_index": idx,
                    "chunk_id": idx,  # backwards compatibility
                    "timestamp": timestamp,
                    "text_preview": chunk[:400],
                    "embedding": vec.tolist(),
                    "content_checksum": content_checksum,
                }
            )
        if vectors:
            return np.mean(np.stack(vectors, axis=0), axis=0).tolist(), docs
        try:
            vec = self.model.encode(text, show_progress_bar=False)
            return np.array(vec, dtype=float).tolist(), docs
        except Exception:
            return [], docs

    def _empty_embed(self) -> List[float]:
        if self._empty_embedding is not None:
            return self._empty_embedding
        try:
            self._empty_embedding = self.model.encode("", show_progress_bar=False).tolist()
        except Exception:
            self._empty_embedding = []
        return self._empty_embedding

    @staticmethod
    def _angle_deg(a: List[float], b: List[float]) -> Optional[float]:
        if not a or not b:
            return None
        va = np.array(a, dtype=float)
        vb = np.array(b, dtype=float)
        denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
        if denom <= 0:
            return None
        cosv = float(np.dot(va, vb) / denom)
        cosv = max(-1.0, min(1.0, cosv))
        try:
            return math.degrees(math.acos(cosv))
        except ValueError:
            return None

    def angle_from_empty(self, embedding: List[float]) -> Optional[float]:
        base = self._empty_embed()
        return self._angle_deg(base, embedding)

    # ------------------------------------------------------------------ #
    def get_file_embedding(self, path: Path) -> Optional[List[float]]:
        file_uri = _as_file_uri(path.expanduser().resolve())
        try:
            doc = self.collection.find_one({"path": file_uri})
        except Exception:
            doc = None
        if not doc:
            return None
        record_db_activity("similarity.get_file_embedding", str(path))
        return doc.get("embedding")

    def add_file(
        self,
        path: Path,
        *,
        extraction: Optional[ExtractResult] = None,
        force: bool = False,
        file_checksum: Optional[str] = None,
        file_bytes: Optional[int] = None,
    ) -> bool:
        path = path.expanduser().resolve()
        if not path.exists() or not path.is_file():
            self._last_add_result = {
                "updated": False,
                "path_local": str(path),
                "error": "missing",
            }
            return False

        file_uri = _as_file_uri(path)
        path_local = str(path)

        timings: Dict[str, float] = {}

        checksum_start = time.perf_counter()
        computed_checksum = False
        if file_checksum is None or file_bytes is None:
            file_checksum, file_bytes = self._file_digest(path)
            computed_checksum = True
        timings["checksum"] = time.perf_counter() - checksum_start if computed_checksum else 0.0

        existing = (
            self.collection.find_one({"path": file_uri})
            or self.collection.find_one({"path_local": path_local})
        )
        rename_from_uri: Optional[str] = None
        if not existing:
            other = self.collection.find_one({"checksum": file_checksum})
            if other and other.get("path") != file_uri:
                rename_from_uri = other.get("path")
                existing = other

        rename_detected = bool(rename_from_uri and rename_from_uri != file_uri)

        if existing and not force and not rename_detected:
            if existing.get("checksum") == file_checksum:
                self._last_add_result = {
                    "updated": False,
                    "path": existing.get("path") or file_uri,
                    "path_local": existing.get("path_local") or path_local,
                    "checksum": file_checksum,
                    "content_checksum": existing.get("content_checksum"),
                    "content_hash": existing.get("content_checksum"),
                }
                return False

        try:
            result = extraction or self.extractor.extract(path, persist=True)
        except Exception as exc:
            self._last_add_result = {
                "updated": False,
                "path": file_uri,
                "path_local": path_local,
                "error": str(exc),
            }
            return False

        text = (result.text or "").strip()
        if len(text) < self.min_chars and not force:
            self._last_add_result = {
                "updated": False,
                "path": file_uri,
                "path_local": path_local,
                "skipped": "min_chars",
            }
            return False

        content_path = str(result.content_path) if result.content_path else None
        content_checksum = result.content_checksum
        content_bytes = result.content_bytes

        prev_embedding = existing.get("embedding") if existing else None
        prev_timestamp = existing.get("timestamp") if existing else None
        prev_content_path = existing.get("content_path") if existing else None

        now_iso = _utc_now_iso()
        embed_start = time.perf_counter()
        embedding, chunk_docs = self._embed_text(
            file_uri=file_uri,
            path_local=path_local,
            text=result.text or "",
            content_checksum=content_checksum,
            timestamp=now_iso,
        )
        timings["embed"] = time.perf_counter() - embed_start
        angle = self.angle_from_empty(embedding)

        if file_bytes is None:
            try:
                file_bytes = path.stat().st_size
            except Exception:
                file_bytes = 0

        doc_payload = {
            "path": file_uri,
            "path_local": path_local,
            "filename": path.name,
            "parent": str(path.parent),
            "timestamp": now_iso,
            "model": self.model_name,
            "checksum": file_checksum,
            "bytes": int(file_bytes),
            "content_path": content_path,
            "content_checksum": content_checksum,
            "content_hash": content_checksum,  # backwards compatibility
            "content_bytes": int(content_bytes) if content_bytes is not None else None,
            "embedding": embedding,
            "angle": angle,
            "text_preview": (result.text or "")[:500],
            "num_chunks": len(chunk_docs),
            "chunk_chars": self.chunk_chars,
            "chunk_overlap": self.chunk_overlap,
        }

        target = {"_id": existing["_id"]} if existing and "_id" in existing else {"path": file_uri}
        db_start = time.perf_counter()
        self.collection.update_one(target, {"$set": doc_payload}, upsert=True)
        timings["db_update"] = time.perf_counter() - db_start
        record_db_activity("similarity.add_file", str(path))

        if rename_from_uri and rename_from_uri != file_uri:
            self._update_related_paths(rename_from_uri, file_uri, path_local)

        try:
            chunk_start = time.perf_counter()
            self.chunks.delete_many({"file_path": file_uri})
            if chunk_docs:
                self.chunks.insert_many(chunk_docs, ordered=False)
            timings["chunks"] = time.perf_counter() - chunk_start
        except Exception:
            timings.setdefault("chunks", 0.0)
            pass

        try:
            if prev_embedding:
                prev_dt = _parse_iso(prev_timestamp) or datetime.now(timezone.utc)
                now_dt = datetime.now(timezone.utc)
                prev_vec = np.array(prev_embedding, dtype=float)
                new_vec = np.array(embedding, dtype=float)
                denom = float(np.linalg.norm(prev_vec) * np.linalg.norm(new_vec))
                if denom > 0:
                    cosv = float(np.dot(prev_vec, new_vec) / denom)
                    cosv = max(-1.0, min(1.0, cosv))
                    degrees = math.degrees(math.acos(cosv))
                else:
                    degrees = 0.0
                seconds = max(1.0, (now_dt - prev_dt).total_seconds())
                self.changes.insert_one(
                    {
                        "file_path": file_uri,
                        "t_prev": prev_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                        "t_new": now_iso,
                        "t_new_epoch": int(now_dt.timestamp()),
                        "seconds": float(seconds),
                        "degrees": float(degrees),
                    }
                )
        except Exception:
            pass

        if prev_content_path and prev_content_path != content_path:
            self._cleanup_content_file(prev_content_path)

        self._last_add_result = {
            "updated": True,
            "path": file_uri,
            "path_local": path_local,
            "checksum": file_checksum,
            "content_checksum": content_checksum,
            "content_hash": content_checksum,
            "content_path": content_path,
            "text": result.text,
            "timings": timings,
        }
        return True

    def get_last_add_result(self) -> Optional[Dict[str, Any]]:
        return self._last_add_result

    def remove_file(self, path: Path) -> bool:
        path = path.expanduser().resolve()
        file_uri = _as_file_uri(path)
        doc = self.collection.find_one({"path": file_uri}) or self.collection.find_one(
            {"path_local": str(path)}
        )
        if not doc:
            self._last_add_result = {
                "removed": False,
                "path": file_uri,
                "path_local": str(path),
                "error": "not_found",
            }
            return False
        self.collection.delete_one({"_id": doc["_id"]})
        try:
            self.chunks.delete_many({"file_path": doc.get("path")})
        except Exception:
            pass
        try:
            self.changes.delete_many({"file_path": doc.get("path")})
        except Exception:
            pass
        try:
            self.db["file_snapshots"].delete_many({"path": doc.get("path")})
        except Exception:
            pass
        self._cleanup_content_file(doc.get("content_path"))
        record_db_activity("similarity.remove_file", str(path))
        self._last_add_result = {
            "removed": True,
            "path": doc.get("path"),
            "path_local": doc.get("path_local"),
        }
        return True

    def rename_file(self, src: Path, dest: Path) -> bool:
        src_uri = _as_file_uri(src.expanduser().resolve())
        dest = dest.expanduser().resolve()
        dest_uri = _as_file_uri(dest)
        doc = self.collection.find_one({"path": src_uri})
        if not doc:
            return False
        now_iso = _utc_now_iso()
        update = {
            "path": dest_uri,
            "path_local": str(dest),
            "filename": dest.name,
            "parent": str(dest.parent),
            "timestamp": now_iso,
        }
        self.collection.update_one({"_id": doc["_id"]}, {"$set": update})
        self._update_related_paths(src_uri, dest_uri, str(dest))
        record_db_activity("similarity.rename_file", f"{src} -> {dest}")
        return True

    def rename_folder(self, old_dir: Path, new_dir: Path) -> int:
        old_dir = old_dir.expanduser().resolve()
        new_dir = new_dir.expanduser().resolve()
        old_local = str(old_dir)
        new_local = str(new_dir)
        pattern = f"^{re.escape(old_local)}/"
        cursor = self.collection.find({"path_local": {"$regex": pattern}})
        updated = 0
        for doc in cursor:
            local = doc.get("path_local") or ""
            if not local.startswith(old_local):
                continue
            new_path_local = local.replace(old_local, new_local, 1)
            dest_path = Path(new_path_local)
            dest_uri = _as_file_uri(dest_path)
            now_iso = _utc_now_iso()
            self.collection.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "path": dest_uri,
                        "path_local": new_path_local,
                        "filename": dest_path.name,
                        "parent": str(dest_path.parent),
                        "timestamp": now_iso,
                    }
                },
            )
            self._update_related_paths(doc.get("path"), dest_uri, new_path_local)
            updated += 1
        if updated:
            record_db_activity("similarity.rename_folder", f"{old_dir} -> {new_dir} ({updated} files)")
        return updated

    # ------------------------------------------------------------------ #
    def find_similar(
        self,
        query_path: Optional[Path] = None,
        query_text: Optional[str] = None,
        limit: int = 10,
        min_similarity: float = 0.0,
        mode: str = "file",
    ) -> List[Tuple[str, float]]:
        if query_path:
            try:
                text = self.extractor.read_text(query_path.expanduser().resolve())
            except Exception:
                return []
            query_embedding = self.model.encode(text, show_progress_bar=False)
        elif query_text:
            query_embedding = self.model.encode(query_text, show_progress_bar=False)
        else:
            raise ValueError("Must provide either query_path or query_text")

        results: List[Tuple[str, float]] = []
        if mode == "chunk":
            best: Dict[str, float] = {}
            for doc in self.chunks.find():
                emb = doc.get("embedding")
                if not emb:
                    continue
                sim = self._cosine_similarity(query_embedding, emb)
                if sim < min_similarity:
                    continue
                uri = doc.get("file_path")
                if sim > best.get(uri, -1.0):
                    best[uri] = sim
            results = list(best.items())
        else:
            for doc in self.collection.find():
                emb = doc.get("embedding")
                if not emb:
                    continue
                sim = self._cosine_similarity(query_embedding, emb)
                if sim >= min_similarity:
                    results.append((doc.get("path"), sim))
        results.sort(key=lambda item: item[1], reverse=True)
        return results[:limit]

    @staticmethod
    def _cosine_similarity(a: Any, b: Any) -> float:
        va = np.array(a, dtype=float)
        vb = np.array(b, dtype=float)
        denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
        if denom <= 0:
            return 0.0
        return float(np.dot(va, vb) / denom)

    def get_stats(self) -> Dict[str, Any]:
        try:
            total_docs = self.collection.count_documents({})
            total_bytes = (
                self.collection.aggregate(
                    [{"$group": {"_id": None, "bytes": {"$sum": {"$ifNull": ["$bytes", 0]}}}}]
                )
            )
            agg = next(total_bytes, None)
            record_db_activity("similarity.get_stats", None)
            return {
                "database": self.db.name,
                "collection": self.collection.name,
                "total_files": int(total_docs),
                "total_bytes": int(agg["bytes"]) if agg and agg.get("bytes") is not None else None,
            }
        except Exception:
            record_db_activity("similarity.get_stats.error", None)
            return {
                "database": self.db.name,
                "collection": self.collection.name,
                "total_files": 0,
                "total_bytes": None,
            }

    # ------------------------------------------------------------------ #
    def _resolve_local_path(self, doc: Dict[str, Any]) -> Optional[Path]:
        local = doc.get("path_local")
        if isinstance(local, str) and local:
            try:
                return Path(local).expanduser()
            except Exception:
                pass
        uri = doc.get("path")
        if isinstance(uri, str) and uri:
            if uri.startswith("file://"):
                try:
                    parsed = urlparse(uri)
                    return Path(unquote(parsed.path or "")).expanduser()
                except Exception:
                    return None
            try:
                return Path(uri).expanduser()
            except Exception:
                return None
        return None

    def _purge_document(self, doc: Dict[str, Any]) -> None:
        try:
            self.collection.delete_one({"_id": doc["_id"]})
        except Exception:
            pass
        try:
            self.chunks.delete_many({"file_path": doc.get("path")})
        except Exception:
            pass
        try:
            self.changes.delete_many({"file_path": doc.get("path")})
        except Exception:
            pass
        try:
            self.db["file_snapshots"].delete_many({"path": doc.get("path")})
        except Exception:
            pass
        self._cleanup_content_file(doc.get("content_path"))

    def audit_documents(
        self,
        remove_missing: bool = True,
        fix_missing_metadata: bool = True,
    ) -> Dict[str, int]:
        results = {"removed": 0, "updated": 0}
        cursor = self.collection.find(
            {},
            {
                "_id": 1,
                "path": 1,
                "path_local": 1,
                "bytes": 1,
                "content_path": 1,
                "content_checksum": 1,
                "content_bytes": 1,
            },
        )
        for doc in cursor:
            local_path = self._resolve_local_path(doc)
            exists = local_path is not None and local_path.exists()
            doc_label = doc.get("path_local") or doc.get("path") or ""

            if remove_missing and local_path is not None and not exists:
                self._purge_document(doc)
                results["removed"] += 1
                record_db_activity("similarity.audit.remove", doc_label)
                continue

            updates: Dict[str, Any] = {}
            path_before = doc.get("path") if isinstance(doc.get("path"), str) else None
            normalized_uri: Optional[str] = None
            if exists and local_path is not None and path_before and not path_before.startswith("file://"):
                try:
                    normalized_uri = _as_file_uri(local_path)
                except Exception:
                    normalized_uri = None
                if normalized_uri and normalized_uri != path_before:
                    updates["path"] = normalized_uri
                    updates.setdefault("path_local", str(local_path))
                    updates.setdefault("filename", local_path.name)
                    updates.setdefault("parent", str(local_path.parent))

            if fix_missing_metadata and exists and local_path is not None:
                try:
                    size = local_path.stat().st_size
                except Exception:
                    size = None
                if size is not None and doc.get("bytes") != size:
                    updates["bytes"] = int(size)

            content_path = doc.get("content_path")
            if content_path and isinstance(content_path, str):
                try:
                    artefact = Path(content_path)
                    if not artefact.exists():
                        updates["content_path"] = None
                        updates["content_checksum"] = None
                        updates["content_bytes"] = None
                except Exception:
                    updates["content_path"] = None
                    updates["content_checksum"] = None
                    updates["content_bytes"] = None

            if updates:
                try:
                    self.collection.update_one({"_id": doc["_id"]}, {"$set": updates})
                    results["updated"] += 1
                    record_db_activity("similarity.audit.fix", doc_label)
                    if normalized_uri:
                        self._update_related_paths(path_before, normalized_uri, str(local_path))
                except Exception:
                    pass

        return results
