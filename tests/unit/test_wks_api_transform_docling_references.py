from __future__ import annotations

import re
from pathlib import Path

from tests.unit._transform_test_helpers import temporary_transform_config
from tests.unit.conftest import run_cmd
from wks.api.config.now_iso import now_iso
from wks.api.config.URI import URI
from wks.api.database.Database import Database
from wks.api.transform._EngineConfig import _EngineConfig
from wks.api.transform._get_controller import _get_controller
from wks.api.transform._resolve_engine_selection import resolve_engine_selection
from wks.api.transform._TransformRecord import _TransformRecord
from wks.api.transform.cmd_engine import cmd_engine
from wks.api.transform.get_content import get_content


def test_cmd_engine_docling_rewrites_nested_referenced_images_to_cache_artifacts(
    tracked_wks_config, tmp_path, monkeypatch
):
    """Docling referenced images should be rewritten out of temp space into cache-owned paths."""
    import wks.api.transform._docling._DoclingEngine as docling_module

    test_file = tmp_path / "COR-0017 Code of Record.pdf"
    test_file.write_bytes(b"%PDF-1.4\nfake\n")

    temp_roots: dict[str, Path] = {}
    with temporary_transform_config(
        engines={
            "dx": _EngineConfig(
                type="docling",
                data={
                    "ocr": False,
                    "ocr_languages": ["eng"],
                    "image_export_mode": "referenced",
                    "pipeline": "standard",
                    "timeout_secs": 30,
                    "to": "md",
                },
                supported_types=[".pdf"],
            )
        }
    ) as config:

        def fake_run_docling(self, input_path, output_path, temp_output, options):
            temp_roots["path"] = temp_output
            artifacts_dir = temp_output / f"{input_path.stem}_artifacts"
            artifacts_dir.mkdir()
            image_path = artifacts_dir / "image_000000_demo.png"
            image_path.write_bytes(b"png")
            expected_output = temp_output / f"{input_path.stem}.md"
            expected_output.write_text(
                f"{'System Physics Advanced Reactor Critical ' * 20}\n![Image]({image_path})\n",
                encoding="utf-8",
            )
            referenced_images = self._rewrite_referenced_images(
                expected_output,
                output_path,
                temp_output,
                options["image_export_mode"],
            )
            if False:
                yield ""
            return expected_output, referenced_images

        monkeypatch.setattr(docling_module._DoclingEngine, "_run_docling", fake_run_docling)

        result = run_cmd(
            cmd_engine,
            engine="dx",
            uri=URI.from_path(test_file),
            overrides={},
        )

        assert result.success is True
        content = get_content(result.output["checksum"])
        image_path = _extract_image_path(content)

        assert str(temp_roots["path"]) not in content
        assert "COR-0017 Code of Record_artifacts" not in content
        assert image_path.exists()
        assert image_path.parent.name == f"{result.output['checksum']}_artifacts"
        assert image_path.parent.parent == Path(config.transform.cache.base_dir)
        assert " " not in str(image_path)


def test_cmd_engine_rebuilds_stale_cached_docling_output_with_missing_image_refs(
    tracked_wks_config, tmp_path, monkeypatch
):
    """A cached docling markdown file with missing local image refs should be re-transformed."""
    import wks.api.transform._docling._DoclingEngine as docling_module

    test_file = tmp_path / "stale.pdf"
    test_file.write_bytes(b"%PDF-1.4\nfake\n")

    with temporary_transform_config(
        engines={
            "dx": _EngineConfig(
                type="docling",
                data={
                    "ocr": False,
                    "ocr_languages": ["eng"],
                    "image_export_mode": "referenced",
                    "pipeline": "standard",
                    "timeout_secs": 30,
                    "to": "md",
                },
                supported_types=[".pdf"],
            )
        }
    ) as config:
        with _get_controller(config) as controller:
            selection = resolve_engine_selection(config.transform.engines, "dx", test_file, {})
            file_checksum = controller._compute_file_checksum(test_file)
            options_hash = selection.engine.compute_options_hash(selection.options)
            cache_key = controller._compute_cache_key(file_checksum, selection.cache_engine_name, options_hash)

        stale_cache_file = Path(config.transform.cache.base_dir) / f"{cache_key}.md"
        stale_cache_file.parent.mkdir(parents=True, exist_ok=True)
        stale_cache_file.write_text(
            "![Image](/var/folders/fake/stale_artifacts/image_000000_demo.png)\n", encoding="utf-8"
        )

        with Database(config.database, "transform") as database:
            database.insert_one(
                _TransformRecord(
                    file_uri=URI.from_path(test_file),
                    cache_uri=URI.from_path(stale_cache_file),
                    checksum=file_checksum,
                    size_bytes=stale_cache_file.stat().st_size,
                    last_accessed=now_iso(),
                    created_at=now_iso(),
                    engine="dx",
                    options_hash=options_hash,
                    referenced_uris=[],
                ).to_dict()
            )

        def fake_run_docling(self, input_path, output_path, temp_output, options):
            artifacts_dir = temp_output / f"{input_path.stem}_artifacts"
            artifacts_dir.mkdir()
            image_path = artifacts_dir / "image_000000_demo.png"
            image_path.write_bytes(b"png")
            expected_output = temp_output / f"{input_path.stem}.md"
            expected_output.write_text(
                f"{'System Physics Advanced Reactor Critical ' * 20}\n![Image]({image_path})\n",
                encoding="utf-8",
            )
            referenced_images = self._rewrite_referenced_images(
                expected_output,
                output_path,
                temp_output,
                options["image_export_mode"],
            )
            if False:
                yield ""
            return expected_output, referenced_images

        monkeypatch.setattr(docling_module._DoclingEngine, "_run_docling", fake_run_docling)

        result = run_cmd(
            cmd_engine,
            engine="dx",
            uri=URI.from_path(test_file),
            overrides={},
        )

        assert result.success is True
        assert result.output["cached"] is False

        content = get_content(result.output["checksum"])
        image_path = _extract_image_path(content)

        assert "/var/folders/fake/" not in content
        assert image_path.exists()

        with Database(config.database, "transform") as database:
            assert database.get_database()["transform"].count_documents({}) == 1


def _extract_image_path(content: str) -> Path:
    match = re.search(r"!\[Image\]\(([^)]+)\)", content)
    assert match is not None
    return Path(match.group(1))
