"""Image-to-text transform engine."""

from collections.abc import Generator
from functools import lru_cache
from pathlib import Path
from typing import Any

from .._TransformEngine import _TransformEngine


class _ImageTextEngine(_TransformEngine):
    """Transform image files into descriptive text."""

    @staticmethod
    @lru_cache(maxsize=2)
    def _load_image_caption_pipeline(model_name: str):
        try:
            from transformers import pipeline
        except Exception as exc:  # pragma: no cover - exercised in integration/runtime
            raise RuntimeError("transformers is required for imagetext engine") from exc
        return pipeline("image-to-text", model=model_name)

    def _caption_image(self, image_path: Path, model_name: str, max_new_tokens: int) -> str:
        pipe = self._load_image_caption_pipeline(model_name)
        result = pipe(str(image_path), max_new_tokens=max_new_tokens)
        if not isinstance(result, list) or len(result) == 0:
            raise RuntimeError(f"Image captioning returned no results for {image_path}")
        first = result[0]
        if not isinstance(first, dict) or "generated_text" not in first:
            raise RuntimeError(f"Image captioning returned invalid result for {image_path}: {first!r}")
        caption = str(first["generated_text"]).strip()
        if not caption:
            raise RuntimeError(f"Image captioning returned empty caption for {image_path}")
        return caption

    def transform(
        self,
        input_path: Path,
        output_path: Path,
        options: dict[str, Any],
    ) -> Generator[str, None, list[str]]:
        """Generate text description from an image file."""
        if "model" not in options:
            raise RuntimeError("imagetext engine requires option 'model'")
        if "max_new_tokens" not in options:
            raise RuntimeError("imagetext engine requires option 'max_new_tokens'")

        model_name = options["model"]
        max_new_tokens = options["max_new_tokens"]
        if not isinstance(model_name, str) or not model_name.strip():
            raise RuntimeError("imagetext option 'model' must be a non-empty string")
        if not isinstance(max_new_tokens, int) or max_new_tokens <= 0:
            raise RuntimeError("imagetext option 'max_new_tokens' must be a positive integer")

        yield "Generating image description..."
        caption = self._caption_image(
            image_path=input_path,
            model_name=model_name,
            max_new_tokens=max_new_tokens,
        )

        yield "Writing image description..."
        output_path.write_text(caption + "\n", encoding="utf-8")
        yield "Image text transform complete"
        return []

    def get_extension(self, options: dict[str, Any]) -> str:  # noqa: ARG002
        """Get output extension for image text transform."""
        return "txt"
