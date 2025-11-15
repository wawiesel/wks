import hashlib
from pathlib import Path

import pytest

from wks.constants import WKS_EXTRACT_EXT
from wks.extractor import Extractor


def test_docling_fallback_to_builtin_text(tmp_path, monkeypatch):
    sample = tmp_path / "script.py"
    content = "print('hello world')\n"
    sample.write_text(content, encoding="utf-8")

    extractor = Extractor(engine="docling")

    def _fail_docling(self, source: Path):
        raise RuntimeError("docling failed")

    monkeypatch.setattr(Extractor, "_docling_convert", _fail_docling, raising=False)

    result = extractor.extract(sample)

    assert result.text.strip() == content.strip()
    assert result.content_path is not None
    assert result.content_path.suffix == ".py"
    assert result.content_path.parent == sample.parent / WKS_EXTRACT_EXT
    assert result.content_path.exists()

    checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert result.content_path.name.startswith(checksum)


def test_extractor_uses_repo_root_wks0(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    subdir = repo / "src"
    subdir.mkdir()
    target = subdir / "example.txt"
    target.write_text("hello world", encoding="utf-8")

    extractor = Extractor(engine="builtin")
    result = extractor.extract(target)

    assert result.content_path is not None
    assert result.content_path.parent == tmp_path / WKS_EXTRACT_EXT
    assert (tmp_path / WKS_EXTRACT_EXT).exists()
    # Ensure no nested .wkso under repo or subdir
    assert not (repo / WKS_EXTRACT_EXT).exists()
    assert not (subdir / WKS_EXTRACT_EXT).exists()
