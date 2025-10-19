"""
Semantic similarity using MongoDB and sentence-transformers.
Replaces A_GIS dependency with direct MongoDB integration.
"""

import hashlib
from pathlib import Path
from typing import List, Tuple, Optional
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
        mongo_uri: str = "mongodb://localhost:27017/"
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

        # Load sentence transformer model
        # Using a small, fast model suitable for semantic search
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

        # Create indexes
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create necessary indexes."""
        self.collection.create_index("path", unique=True)
        self.collection.create_index("content_hash")
        self.collection.create_index("timestamp")

    def _compute_hash(self, text: str) -> str:
        """Compute SHA256 hash of text."""
        return hashlib.sha256(text.encode()).hexdigest()

    def _read_file_text(self, path: Path, max_chars: int = 5000) -> Optional[str]:
        """
        Read text content from a file.

        Args:
            path: Path to file
            max_chars: Maximum characters to read

        Returns:
            Text content or None if can't read
        """
        try:
            # Try to read as text
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read(max_chars)
            return text
        except Exception:
            return None

    def add_file(self, path: Path) -> bool:
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
        if existing and existing.get("content_hash") == content_hash:
            # Content hasn't changed, skip
            return False

        # Generate embedding
        embedding = self.model.encode(text).tolist()

        # Store in database
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
                    "timestamp": datetime.now().isoformat(),
                }
            },
            upsert=True
        )

        return True

    def find_similar(
        self,
        query_path: Optional[Path] = None,
        query_text: Optional[str] = None,
        limit: int = 10,
        min_similarity: float = 0.0
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

        # Get all embeddings from database
        results = []
        for doc in self.collection.find():
            if "embedding" not in doc:
                continue

            # Compute cosine similarity
            doc_embedding = doc["embedding"]
            similarity = self._cosine_similarity(query_embedding, doc_embedding)

            if similarity >= min_similarity:
                results.append((doc["path"], similarity))

        # Sort by similarity descending
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
