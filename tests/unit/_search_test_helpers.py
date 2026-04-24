"""Shared search test helpers."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from tests.conftest import minimal_config_dict, run_cmd
from wks.api.index.cmd import cmd as index_cmd

SEARCH_DOCS = {
    "fission.txt": (
        "Nuclear fission products are generated during reactor operation.\n"
        "The fission yield depends on the fissile isotope and neutron energy.\n"
    ),
    "python.txt": (
        "Python programming language is used for scientific computing.\n"
        "Libraries like numpy and scipy provide numerical methods.\n"
    ),
    "coolant.txt": (
        "Reactor coolant systems maintain safe operating temperatures.\n"
        "The primary loop transfers heat from the reactor core.\n"
    ),
}


def write_and_index_search_docs(tmp_path: Path) -> list[Path]:
    """Write the canonical search test documents and index them into `main`."""
    docs: list[Path] = []
    for name, content in SEARCH_DOCS.items():
        doc = tmp_path / name
        doc.write_text(content)
        result = run_cmd(index_cmd, "main", str(doc))
        assert result.success is True
        docs.append(doc)
    return docs


def setup_search_config(tmp_path: Path, monkeypatch, *, index_config: dict) -> dict:
    """Write a WKS config with the provided index section for search tests."""
    config_dict = minimal_config_dict()
    cache_dir = tmp_path / "transform_cache"
    cache_dir.mkdir()
    config_dict["transform"]["cache"]["base_dir"] = str(cache_dir)
    config_dict["monitor"]["filter"]["include_paths"].append(str(cache_dir))
    config_dict["index"] = index_config

    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(config_dict))
    return config_dict


def fake_embed_texts(texts: list[str], model_name: str, batch_size: int) -> np.ndarray:
    """Return deterministic low-dimensional embeddings for search tests."""
    del model_name, batch_size
    rows: list[list[float]] = []
    for text in texts:
        lower = text.lower()
        vec = np.array(
            [
                float(lower.count("fission")),
                float(lower.count("python")),
                float(lower.count("reactor")),
            ],
            dtype=np.float32,
        )
        norm = np.linalg.norm(vec)
        rows.append((vec / norm if norm > 0 else vec).tolist())
    return np.asarray(rows, dtype=np.float32)
