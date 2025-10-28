"""
Semantic similarity using MongoDB and sentence-transformers.
Includes lightweight text extractors for common binary formats.
"""

import hashlib
import shutil
import subprocess
import tempfile
import zipfile
import io
import re
from pathlib import Path
import os
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime

from pymongo import MongoClient
from sentence_transformers import SentenceTransformer


class SimilarityDB:
    """
    Semantic similarity database using MongoDB and embeddings.
    """

    def __init__(
        self,
        database_name: str = "wks_similarity",
        collection_name: str = "file_embeddings",
        mongo_uri: str = "mongodb://localhost:27017/",
        model_name: str = 'all-MiniLM-L6-v2',
        model_path: Optional[str] = None,
        offline: bool = False,
        max_chars: int = 200000,
        chunks_collection: str = "file_chunks",
        chunk_chars: int = 1500,
        chunk_overlap: int = 200,
        extract_engine: str = 'builtin',
        extract_ocr: bool = False,
        extract_timeout_secs: int = 30,
    ):
        """
        Initialize similarity database.

        Args:
            database_name: MongoDB database name
            collection_name: Collection name for embeddings
            mongo_uri: MongoDB connection URI
        """
        self.client = MongoClient(mongo_uri)
        self.db = self.client[database_name]
        self.collection = self.db[collection_name]
        self.chunks = self.db[chunks_collection]
        # Embedding change events (degrees between consecutive embeddings)
        self.changes = self.db["embedding_changes"]

        # Load sentence transformer model
        # Using a small, fast model suitable for semantic search
        self.model_name = model_name
        # Offline hints to avoid network access
        if offline:
            os.environ.setdefault('HF_HUB_OFFLINE', '1')
            os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
        target = (model_path or model_name).strip()
        self.model = SentenceTransformer(target)

        # Create indexes
        self._ensure_indexes()
        # Default maximum characters to read from files for embedding
        self.max_chars = int(max_chars)
        self.chunk_chars = int(chunk_chars)
        self.chunk_overlap = int(chunk_overlap)
        self.extract_engine = extract_engine
        self.extract_ocr = bool(extract_ocr)
        self.extract_timeout_secs = int(extract_timeout_secs)
        # Track last add result for downstream consumers
        self._last_add_result = None

    def _ensure_indexes(self):
        """Create necessary indexes."""
        self.collection.create_index("path", unique=True)
        self.collection.create_index("content_hash")
        self.collection.create_index("timestamp")
        self.chunks.create_index([("file_path", 1), ("chunk_id", 1)], unique=True)
        self.chunks.create_index("timestamp")
        # Changes: query by file and time
        self.changes.create_index([("file_path", 1), ("t_new_epoch", 1)])

    # --- Convenience API ---------------------------------------------------- #
    def get_file_embedding(self, path: Path) -> Optional[list]:
        try:
            doc = self.collection.find_one({"path": str(path)})
            return doc.get("embedding") if doc else None
        except Exception:
            return None

    def rename_file(self, src: Path, dest: Path) -> bool:
        """Rename a file's path across collections without recomputing embeddings.

        Updates file-level doc, chunk docs, and change history to new path.
        """
        try:
            srcs = str(src)
            dsts = str(dest)
            self.collection.update_one({"path": srcs}, {"$set": {"path": dsts, "filename": dest.name, "parent": str(dest.parent)}})
            try:
                self.chunks.update_many({"file_path": srcs}, {"$set": {"file_path": dsts}})
            except Exception:
                pass
            try:
                self.changes.update_many({"file_path": srcs}, {"$set": {"file_path": dsts}})
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _empty_embed(self) -> list:
        """Return the embedding vector for the empty string (cached)."""
        try:
            if hasattr(self, "__empty_emb") and self.__empty_emb is not None:
                return self.__empty_emb  # type: ignore[attr-defined]
            vec = self.model.encode("").tolist()
            self.__empty_emb = vec  # type: ignore[attr-defined]
            return vec
        except Exception:
            return []

    @staticmethod
    def _angle_deg(a: list, b: list) -> Optional[float]:
        try:
            import numpy as _np, math as _math
            va = _np.array(a, dtype=float); vb = _np.array(b, dtype=float)
            denom = (_np.linalg.norm(va) * _np.linalg.norm(vb))
            if denom <= 0:
                return None
            cosv = float(_np.dot(va, vb) / denom)
            cosv = max(-1.0, min(1.0, cosv))
            return float(_math.degrees(_math.acos(cosv)))
        except Exception:
            return None

    def angle_from_empty(self, embedding: list) -> Optional[float]:
        base = self._empty_embed()
        if not base or not embedding:
            return None
        return self._angle_deg(base, embedding)

    def _compute_hash(self, text: str) -> str:
        """Compute SHA256 hash of text."""
        return hashlib.sha256(text.encode()).hexdigest()

    def _read_file_text(self, path: Path, max_chars: Optional[int] = None) -> Optional[str]:
        """
        Read text content from a file.

        Args:
            path: Path to file
            max_chars: Maximum characters to read

        Returns:
            Text content or None if can't read
        """
        eff_max = self.max_chars if max_chars is None else int(max_chars)
        if self.extract_engine == 'docling':
            try:
                from docling.document_converter import DocumentConverter
            except Exception as e:
                raise RuntimeError("extract.engine 'docling' requested but package not available") from e
            try:
                converter = DocumentConverter()
                result = converter.convert(str(path))
                txt = None
                # Common docling result accessors
                txt = getattr(result, 'text', None)
                if not txt:
                    doc = getattr(result, 'document', None)
                    if doc and hasattr(doc, 'export_to_markdown'):
                        try:
                            txt = doc.export_to_markdown()
                        except Exception:
                            txt = None
                if not txt:
                    txt = str(result)
                return txt[:eff_max]
            except Exception:
                return None
        if self.extract_engine == 'unstructured':
            try:
                from unstructured.partition.auto import partition
            except Exception as e:
                raise RuntimeError("extract.engine 'unstructured' requested but package not available") from e
            try:
                elements = partition(filename=str(path))
                # Join element texts
                texts = [getattr(el, 'text', '') for el in elements if getattr(el, 'text', None)]
                txt = "\n".join(texts)
                return txt[:eff_max]
            except Exception:
                return None
        suffix = path.suffix.lower()
        # Direct text read for common text-like files
        if suffix in {'.txt', '.md', '.py', '.json', '.yaml', '.yml', '.toml', '.tex', '.rst'}:
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read(eff_max)
            except Exception:
                return None

        # Office Open XML formats
        if suffix == '.docx':
            return self._extract_docx_text(path, eff_max)
        if suffix == '.pptx':
            return self._extract_pptx_text(path, eff_max)

        # PDFs (best-effort using system tools)
        if suffix == '.pdf':
            return self._extract_pdf_text(path, eff_max)

        # Fallback: try to read as text anyway
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read(eff_max)
        except Exception:
            return None

    def _extract_docx_text(self, path: Path, max_chars: int) -> Optional[str]:
        try:
            with zipfile.ZipFile(path) as z:
                # Main document
                with z.open('word/document.xml') as f:
                    xml_bytes = f.read()
            # Parse XML and extract w:t nodes
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_bytes)
            # Namespaces
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            texts = []
            for t in root.findall('.//w:t', ns):
                if t.text:
                    texts.append(t.text)
            text = '\n'.join(texts)
            return text[:max_chars]
        except Exception:
            return None

    def _extract_pptx_text(self, path: Path, max_chars: int) -> Optional[str]:
        try:
            with zipfile.ZipFile(path) as z:
                slide_names = [n for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')]
                texts = []
                import xml.etree.ElementTree as ET
                ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
                for name in sorted(slide_names):
                    try:
                        with z.open(name) as f:
                            xml_bytes = f.read()
                        root = ET.fromstring(xml_bytes)
                        for t in root.findall('.//a:t', ns):
                            if t.text:
                                texts.append(t.text)
                    except Exception:
                        continue
            text = '\n'.join(texts)
            return text[:max_chars]
        except Exception:
            return None

    def _extract_pdf_text(self, path: Path, max_chars: int) -> Optional[str]:
        # Prefer pdftotext if available
        try:
            if shutil.which('pdftotext'):
                with tempfile.NamedTemporaryFile(suffix='.txt', delete=True) as tmp:
                    # -layout to preserve roughly reading order
                    subprocess.run(['pdftotext', '-layout', str(path), tmp.name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    try:
                        txt = Path(tmp.name).read_text(encoding='utf-8', errors='ignore')
                        if txt and txt.strip():
                            return txt[:max_chars]
                    except Exception:
                        pass
        except Exception:
            pass
        # Fallback to 'strings' to extract ASCII snippets
        try:
            if shutil.which('strings'):
                out = subprocess.check_output(['strings', '-n', '4', str(path)], stderr=subprocess.DEVNULL)
                txt = out.decode('utf-8', errors='ignore')
                # Collapse excessive whitespace
                txt = re.sub(r"\s+", " ", txt)
                return txt[:max_chars]
        except Exception:
            pass
        return None

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks of approx chunk_chars length."""
        n = max(256, self.chunk_chars)
        ov = max(0, min(n//2, self.chunk_overlap))
        chunks: List[str] = []
        i = 0
        L = len(text)
        while i < L:
            j = min(L, i + n)
            chunk = text[i:j]
            chunks.append(chunk)
            if j >= L:
                break
            i = j - ov
        return chunks

    def add_file(self, path: Path, force: bool = False) -> bool:
        """
        Add or update a file's embedding in the database.

        Args:
            path: Path to file

        Returns:
            True if added/updated, False if skipped
        """
        if not path.exists() or not path.is_file():
            return False

        path_str = str(path.resolve())

        # Read file content
        text = self._read_file_text(path)
        if not text or len(text.strip()) < 10:
            # Not enough text content
            return False

        content_hash = self._compute_hash(text)

        # Check if already exists with same hash
        existing = self.collection.find_one({"path": path_str})
        if (existing and existing.get("content_hash") == content_hash) and not force:
            # Content hasn't changed, skip
            self._last_add_result = {
                "updated": False,
                "path": path_str,
                "content_hash": content_hash,
                "text": text,
            }
            return False

        # Rename detection: if no record at this path, but another record exists with same content_hash,
        # treat this as a rename (update path in-place) rather than creating a new document.
        if not existing:
            try:
                other = self.collection.find_one({"content_hash": content_hash})
            except Exception:
                other = None
            if other and other.get("path") != path_str:
                old_path = Path(other.get("path"))
                # If old path no longer exists or differs from new path, update references
                try:
                    if (not old_path.exists()):
                        self.rename_file(old_path, path)
                        # Update basic metadata on the file doc
                        from datetime import datetime as _dt
                        now_iso = _dt.now().isoformat()
                        self.collection.update_one({"path": path_str}, {"$set": {
                            "filename": path.name,
                            "parent": str(path.parent),
                            "timestamp": now_iso,
                            "model": self.model_name,
                        }})
                        self._last_add_result = {
                            "updated": True,
                            "renamed": True,
                            "from": str(old_path),
                            "path": path_str,
                            "content_hash": content_hash,
                            "text": text,
                        }
                        return True
                except Exception:
                    pass

        # Chunk text and generate per-chunk and aggregated embeddings
        chunks = self._chunk_text(text)
        import numpy as np
        vecs: List[np.ndarray] = []
        chunk_docs: List[Dict[str, Any]] = []
        for idx, ch in enumerate(chunks):
            try:
                v = self.model.encode(ch)
                vecs.append(np.array(v))
                chunk_docs.append({
                    "file_path": path_str,
                    "chunk_id": idx,
                    "text_preview": ch[:400],
                    "timestamp": datetime.now().isoformat(),
                    "embedding": v.tolist(),
                })
            except Exception:
                continue
        if not vecs:
            # Fallback: single embedding of full text
            embedding = self.model.encode(text).tolist()
            agg = np.array(embedding)
        else:
            # Aggregate by mean vector
            agg = np.mean(np.stack(vecs, axis=0), axis=0)
            embedding = agg.tolist()

        # Store in database (file-level)
        from datetime import datetime as _dt
        now_iso = _dt.now().isoformat()
        self.collection.update_one(
            {"path": path_str},
            {
                "$set": {
                    "path": path_str,
                    "filename": path.name,
                    "parent": str(path.parent),
                    "content_hash": content_hash,
                    "embedding": embedding,
                    "text_preview": text[:500],  # Store preview
                    "timestamp": now_iso,
                    "model": self.model_name,
                    "num_chunks": len(chunk_docs),
                    "chunk_chars": self.chunk_chars,
                    "chunk_overlap": self.chunk_overlap,
                }
            },
            upsert=True
        )

        # Record an embedding change event if we have a previous embedding
        try:
            import math as _math
            import numpy as _np
            if existing and existing.get("embedding"):
                prev_emb = _np.array(existing.get("embedding"))
                new_emb = _np.array(embedding)
                # Safe cosine -> angle
                denom = (_np.linalg.norm(prev_emb) * _np.linalg.norm(new_emb))
                if denom > 0:
                    cosv = float(_np.dot(prev_emb, new_emb) / denom)
                    cosv = max(-1.0, min(1.0, cosv))
                    theta_rad = _math.acos(cosv)
                    degrees = float(theta_rad * 180.0 / _math.pi)
                else:
                    degrees = 0.0
                # Time delta between prev timestamp and now
                try:
                    prev_ts = existing.get("timestamp")
                    from datetime import datetime as _dt
                    t_prev = _dt.fromisoformat(prev_ts) if isinstance(prev_ts, str) else _dt.now()
                except Exception:
                    t_prev = _dt.now()
                t_new = _dt.now()
                seconds = max(1.0, (t_new - t_prev).total_seconds())
                self.changes.insert_one({
                    "file_path": path_str,
                    "t_prev": t_prev.isoformat(),
                    "t_new": t_new.isoformat(),
                    "t_new_epoch": int(t_new.timestamp()),
                    "seconds": float(seconds),
                    "degrees": degrees,
                })
        except Exception:
            pass

        # Upsert chunk-level documents (optional legacy; safe no-op if unused)
        try:
            self.chunks.delete_many({"file_path": path_str})
            if chunk_docs:
                try:
                    self.chunks.insert_many(chunk_docs, ordered=False)
                except Exception:
                    pass
        except Exception:
            pass

        self._last_add_result = {
            "updated": True,
            "path": path_str,
            "content_hash": content_hash,
            "text": text,
        }
        return True

    def get_last_add_result(self):
        """Return metadata for the last add_file call."""
        return self._last_add_result

    def find_similar(
        self,
        query_path: Optional[Path] = None,
        query_text: Optional[str] = None,
        limit: int = 10,
        min_similarity: float = 0.0,
        mode: str = "file",
    ) -> List[Tuple[str, float]]:
        """
        Find files similar to a query.

        Args:
            query_path: Path to file to find similar files to
            query_text: Text to find similar files to
            limit: Maximum number of results
            min_similarity: Minimum similarity score (0.0 to 1.0)

        Returns:
            List of (path, similarity_score) tuples, sorted by similarity
        """
        # Get query embedding
        if query_path:
            text = self._read_file_text(query_path)
            if not text:
                return []
            query_embedding = self.model.encode(text)
        elif query_text:
            query_embedding = self.model.encode(query_text)
        else:
            raise ValueError("Must provide either query_path or query_text")

        results: List[Tuple[str, float]] = []
        if mode == "chunk":
            # Compare to chunk-level embeddings, aggregate by file (max similarity)
            best: Dict[str, float] = {}
            for doc in self.chunks.find():
                if "embedding" not in doc:
                    continue
                sim = self._cosine_similarity(query_embedding, doc["embedding"])
                if sim < min_similarity:
                    continue
                fp = doc["file_path"]
                if sim > best.get(fp, -1):
                    best[fp] = sim
            results = list(best.items())
        else:
            # File-level comparisons (aggregated embedding)
            for doc in self.collection.find():
                if "embedding" not in doc:
                    continue
                sim = self._cosine_similarity(query_embedding, doc["embedding"])
                if sim >= min_similarity:
                    results.append((doc["path"], sim))
        # Sort and return
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def _cosine_similarity(self, a, b) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            a: First vector
            b: Second vector

        Returns:
            Similarity score (0.0 to 1.0)
        """
        import numpy as np
        a = np.array(a)
        b = np.array(b)

        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))

    def remove_file(self, path: Path):
        """Remove a file from the database."""
        path_str = str(path.resolve())
        self.collection.delete_one({"path": path_str})

    def rename_file(self, old_path: Path, new_path: Path):
        """
        Update the stored document when a file is moved/renamed.

        If the old record doesn't exist, falls back to add_file(new_path).
        """
        old_str = str(old_path.resolve())
        new_str = str(new_path.resolve())
        doc = self.collection.find_one({"path": old_str})
        if not doc:
            # No previous record; create a new one
            self.add_file(new_path)
            return

        self.collection.update_one(
            {"path": old_str},
            {
                "$set": {
                    "path": new_str,
                    "filename": new_path.name,
                    "parent": str(new_path.parent),
                    "timestamp": datetime.now().isoformat(),
                }
            }
        )

    def rename_folder(self, old_dir: Path, new_dir: Path) -> int:
        """Rename all documents under a moved/renamed folder.

        Updates path, filename, parent in file-level docs and file_path in chunk/change docs.
        Returns the number of updated file-level documents.
        """
        try:
            import re as _re
            oldp = str(old_dir.resolve()).rstrip('/')
            newp = str(new_dir.resolve()).rstrip('/')
            # Match paths starting with oldp + '/'
            pattern = f"^{_re.escape(oldp)}/"
            cursor = self.collection.find({"path": {"$regex": pattern}})
            updated = 0
            for doc in cursor:
                pold = doc.get('path') or ''
                pnew = pold.replace(oldp + '/', newp + '/', 1)
                np = Path(pnew)
                self.collection.update_one({"_id": doc["_id"]}, {"$set": {
                    "path": pnew,
                    "filename": np.name,
                    "parent": str(np.parent),
                    "timestamp": datetime.now().isoformat(),
                }})
                try:
                    self.chunks.update_many({"file_path": pold}, {"$set": {"file_path": pnew}})
                except Exception:
                    pass
                try:
                    self.changes.update_many({"file_path": pold}, {"$set": {"file_path": pnew}})
                except Exception:
                    pass
                updated += 1
            return updated
        except Exception:
            return 0

    def get_stats(self) -> dict:
        """Get database statistics."""
        return {
            "total_files": self.collection.count_documents({}),
            "database": self.db.name,
            "collection": self.collection.name
        }


if __name__ == "__main__":
    from rich.console import Console
    from rich.table import Table

    console = Console()

    # Example usage
    console.print("[cyan]Connecting to MongoDB...[/cyan]")
    db = SimilarityDB()

    stats = db.get_stats()
    console.print(f"[green]Connected! {stats['total_files']} files indexed[/green]")

    # Add some test files
    console.print("\n[cyan]Adding files...[/cyan]")
    test_files = [
        Path.home() / "2025-WKS" / "SPEC.md",
        Path.home() / "2025-WKS" / "README.md",
    ]

    for f in test_files:
        if f.exists():
            if db.add_file(f):
                console.print(f"  [green]✓[/green] {f.name}")
            else:
                console.print(f"  [yellow]→[/yellow] {f.name} (unchanged)")

    # Find similar files
    console.print("\n[cyan]Finding files similar to SPEC.md...[/cyan]")
    similar = db.find_similar(query_path=Path.home() / "2025-WKS" / "SPEC.md", limit=5)

    table = Table()
    table.add_column("File", style="cyan")
    table.add_column("Similarity", justify="right", style="green")

    for path, score in similar:
        table.add_row(Path(path).name, f"{score:.3f}")

    console.print(table)
