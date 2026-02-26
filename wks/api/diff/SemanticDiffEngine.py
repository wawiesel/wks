"""Semantic diff engine for text and image files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
from PIL import Image

from .DiffEngine import DiffEngine


class SemanticDiffEngine(DiffEngine):
    """Semantic diff engine using vector similarity for text and images."""

    IMAGE_SUFFIXES: ClassVar[set[str]] = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"}

    def diff(self, file1: Path, file2: Path, options: dict) -> str:
        """Compute semantic diff and return JSON report string."""
        modified_threshold = float(options["modified_threshold"])
        unchanged_threshold = float(options["unchanged_threshold"])
        text_model = str(options["text_model"])
        image_model = str(options["image_model"])
        pixel_threshold = int(options["pixel_threshold"])
        max_examples = int(options["max_examples"])

        if file1.suffix.lower() in self.IMAGE_SUFFIXES and file2.suffix.lower() in self.IMAGE_SUFFIXES:
            report = self._diff_image(
                file1=file1,
                file2=file2,
                modified_threshold=modified_threshold,
                unchanged_threshold=unchanged_threshold,
                image_model=image_model,
                pixel_threshold=pixel_threshold,
            )
            return json.dumps(report, ensure_ascii=True, sort_keys=True)

        report = self._diff_text(
            file1=file1,
            file2=file2,
            modified_threshold=modified_threshold,
            unchanged_threshold=unchanged_threshold,
            text_model=text_model,
            max_examples=max_examples,
        )
        return json.dumps(report, ensure_ascii=True, sort_keys=True)

    def _diff_text(
        self,
        file1: Path,
        file2: Path,
        modified_threshold: float,
        unchanged_threshold: float,
        text_model: str,
        max_examples: int,
    ) -> dict[str, Any]:
        text_a = file1.read_text(encoding="utf-8")
        text_b = file2.read_text(encoding="utf-8")
        units_a = self._extract_text_units(text_a)
        units_b = self._extract_text_units(text_b)

        if len(units_a) == 0 and len(units_b) == 0:
            return {
                "engine": "semantic",
                "file_type": "text",
                "semantic_similarity": 1.0,
                "status": "unchanged",
                "counts": {"added": 0, "removed": 0, "modified": 0, "unchanged": 0},
                "examples": {"added": [], "removed": [], "modified": []},
            }

        if len(units_a) == 0 or len(units_b) == 0:
            return {
                "engine": "semantic",
                "file_type": "text",
                "semantic_similarity": 0.0,
                "status": "changed",
                "counts": {
                    "added": len(units_b) if len(units_a) == 0 else 0,
                    "removed": len(units_a) if len(units_b) == 0 else 0,
                    "modified": 0,
                    "unchanged": 0,
                },
                "examples": {
                    "added": units_b[:max_examples] if len(units_a) == 0 else [],
                    "removed": units_a[:max_examples] if len(units_b) == 0 else [],
                    "modified": [],
                },
            }

        emb_a = self._embed_text_units(units_a, text_model)
        emb_b = self._embed_text_units(units_b, text_model)
        similarity = emb_a @ emb_b.T
        matches = self._greedy_match(similarity, modified_threshold=modified_threshold)

        matched_a = {i for i, _, _ in matches}
        matched_b = {j for _, j, _ in matches}
        removed = [units_a[i] for i in range(len(units_a)) if i not in matched_a]
        added = [units_b[j] for j in range(len(units_b)) if j not in matched_b]

        unchanged_count = sum(1 for _, _, s in matches if s >= unchanged_threshold)
        modified_pairs = [
            {"from": units_a[i], "to": units_b[j], "similarity": round(float(s), 4)}
            for i, j, s in matches
            if s < unchanged_threshold
        ]
        semantic_similarity = float(np.mean([s for _, _, s in matches])) if len(matches) > 0 else 0.0

        status = "changed"
        if len(added) == 0 and len(removed) == 0 and len(modified_pairs) == 0:
            status = "unchanged"
        elif semantic_similarity >= unchanged_threshold and len(added) + len(removed) <= 1:
            status = "near-unchanged"
        elif semantic_similarity >= modified_threshold:
            status = "modified"

        return {
            "engine": "semantic",
            "file_type": "text",
            "semantic_similarity": round(semantic_similarity, 4),
            "status": status,
            "counts": {
                "added": len(added),
                "removed": len(removed),
                "modified": len(modified_pairs),
                "unchanged": unchanged_count,
            },
            "examples": {
                "added": added[:max_examples],
                "removed": removed[:max_examples],
                "modified": modified_pairs[:max_examples],
            },
        }

    def _diff_image(
        self,
        file1: Path,
        file2: Path,
        modified_threshold: float,
        unchanged_threshold: float,
        image_model: str,
        pixel_threshold: int,
    ) -> dict[str, Any]:
        img_a = Image.open(file1).convert("RGB")
        img_b = Image.open(file2).convert("RGB")
        semantic_similarity = self._semantic_similarity_image(file1, file2, image_model)
        pixel_metrics = self._pixel_metrics(img_a, img_b, pixel_threshold)

        status = "changed"
        if semantic_similarity >= unchanged_threshold and pixel_metrics["mae"] <= 0.01:
            status = "unchanged"
        elif semantic_similarity >= modified_threshold:
            status = "modified"

        return {
            "engine": "semantic",
            "file_type": "image",
            "semantic_similarity": round(float(semantic_similarity), 4),
            "status": status,
            "metrics": pixel_metrics,
            "dimensions": {
                "a": [img_a.width, img_a.height],
                "b": [img_b.width, img_b.height],
            },
            "image_model": image_model,
        }

    def _extract_text_units(self, text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _embed_text_units(self, units: list[str], model_name: str) -> np.ndarray:
        if len(units) == 0:
            return np.zeros((0, 1), dtype=np.float32)
        from wks.api.index._embedding_utils import embed_texts

        return embed_texts(texts=units, model_name=model_name, batch_size=64)

    def _greedy_match(self, similarity: np.ndarray, modified_threshold: float) -> list[tuple[int, int, float]]:
        if similarity.ndim != 2:
            raise ValueError(f"similarity matrix must be 2D (found ndim={similarity.ndim})")
        pairs: list[tuple[float, int, int]] = []
        rows, cols = similarity.shape
        for i in range(rows):
            for j in range(cols):
                score = float(similarity[i, j])
                if score >= modified_threshold:
                    pairs.append((score, i, j))
        pairs.sort(key=lambda item: item[0], reverse=True)

        used_i: set[int] = set()
        used_j: set[int] = set()
        matches: list[tuple[int, int, float]] = []
        for score, i, j in pairs:
            if i in used_i or j in used_j:
                continue
            used_i.add(i)
            used_j.add(j)
            matches.append((i, j, score))
        return matches

    def _semantic_similarity_image(self, file_a: Path, file_b: Path, model_name: str) -> float:
        from wks.api.index._embedding_utils import embed_clip_images

        embeddings = embed_clip_images(
            image_paths=[file_a, file_b],
            model_name=model_name,
            batch_size=2,
        )
        return float(embeddings[0] @ embeddings[1])

    def _pixel_metrics(self, img_a: Image.Image, img_b: Image.Image, pixel_threshold: int) -> dict[str, float]:
        width = max(img_a.width, img_b.width)
        height = max(img_a.height, img_b.height)
        arr_a = np.asarray(img_a.resize((width, height)), dtype=np.float32) / 255.0
        arr_b = np.asarray(img_b.resize((width, height)), dtype=np.float32) / 255.0
        delta = arr_a - arr_b
        abs_delta = np.abs(delta)
        mae = float(abs_delta.mean())
        rmse = float(np.sqrt((delta * delta).mean()))
        threshold = float(pixel_threshold) / 255.0
        changed_ratio = float((abs_delta.max(axis=2) > threshold).mean())
        return {
            "mae": round(mae, 6),
            "rmse": round(rmse, 6),
            "changed_pixel_ratio": round(changed_ratio, 6),
        }
