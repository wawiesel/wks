import subprocess

from tests.unit._transform_test_helpers import temporary_transform_config
from tests.unit.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.transform._EngineConfig import _EngineConfig
from wks.api.transform.cmd_engine import cmd_engine
from wks.api.transform.get_content import get_content


def test_cmd_engine_docling_engine_type(tracked_wks_config, tmp_path):
    """Configured docling engines should fail as docling, not as unknown engines."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test", encoding="utf-8")

    with temporary_transform_config(engines={"docling": _EngineConfig(type="docling", data={})}):
        result = run_cmd(
            cmd_engine,
            engine="docling",
            uri=URI.from_path(test_file),
            overrides={},
        )
        assert result.success is False
        assert "docling" in result.result.lower() or "Unknown engine type" not in result.result


def test_cmd_engine_pdftext_engine_type(tracked_wks_config, tmp_path, monkeypatch):
    """cmd_engine should support the lightweight pdftext engine."""
    import wks.api.transform._pdftext._PdfTextEngine as pdftext_module

    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"%PDF-1.4\nfake\n")

    with temporary_transform_config(engines={"pdftext": _EngineConfig(type="pdftext", data={})}):

        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="Extracted PDF text", stderr="")

        monkeypatch.setattr(pdftext_module.subprocess, "run", fake_run)

        result = run_cmd(
            cmd_engine,
            engine="pdftext",
            uri=URI.from_path(test_file),
            overrides={},
        )

        assert result.success is True
        assert result.output["cached"] is False
        assert get_content(result.output["checksum"]) == "Extracted PDF text"


def test_cmd_engine_pdftext_rejects_non_pdf(tracked_wks_config, tmp_path):
    """pdftext should fail fast for non-PDF inputs."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("not a pdf", encoding="utf-8")

    with temporary_transform_config(engines={"pdftext": _EngineConfig(type="pdftext", data={})}):
        result = run_cmd(
            cmd_engine,
            engine="pdftext",
            uri=URI.from_path(test_file),
            overrides={},
        )

        assert result.success is False
        assert "unsupported file type" in result.result.lower()


def test_cmd_engine_docling_pdf_falls_back_to_pdftext_for_low_quality_output(tracked_wks_config, tmp_path, monkeypatch):
    """Low-quality docling PDF output should be recovered by pdftext."""
    import wks.api.transform._docling._DoclingEngine as docling_module

    test_file = tmp_path / "cor.pdf"
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
    ):

        def fake_run_docling(self, input_path, output_path, temp_output, options):
            expected_output = temp_output / f"{input_path.stem}.md"
            expected_output.write_text("![Image](cor_page_1.png)\n", encoding="utf-8")
            if False:
                yield ""
            return expected_output, []

        def fake_run_pdftext(self, input_path, options):
            if False:
                yield ""
            return "Document ID: COR-0017\nCode of Record\nSystem Physics Advanced Reactor Critical (SPARC)\n"

        monkeypatch.setattr(docling_module._DoclingEngine, "_run_docling", fake_run_docling)
        monkeypatch.setattr(docling_module._DoclingEngine, "_run_pdftext_fallback", fake_run_pdftext)

        result = run_cmd(
            cmd_engine,
            engine="dx",
            uri=URI.from_path(test_file),
            overrides={},
        )

        assert result.success is True
        assert "COR-0017" in get_content(result.output["checksum"])


def test_cmd_engine_docling_pdf_falls_back_to_pdftext_after_docling_error(tracked_wks_config, tmp_path, monkeypatch):
    """A docling PDF failure should fall back to pdftext when available."""
    import wks.api.transform._docling._DoclingEngine as docling_module

    test_file = tmp_path / "fallback.pdf"
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
    ):

        def fake_run_docling(self, input_path, output_path, temp_output, options):
            if False:
                yield ""
            raise RuntimeError("Docling failed with exit code 1")

        def fake_run_pdftext(self, input_path, options):
            if False:
                yield ""
            return "Recovered text from pdftotext fallback.\n"

        monkeypatch.setattr(docling_module._DoclingEngine, "_run_docling", fake_run_docling)
        monkeypatch.setattr(docling_module._DoclingEngine, "_run_pdftext_fallback", fake_run_pdftext)

        result = run_cmd(
            cmd_engine,
            engine="dx",
            uri=URI.from_path(test_file),
            overrides={},
        )

        assert result.success is True
        assert "Recovered text from pdftotext fallback." in get_content(result.output["checksum"])


def test_cmd_engine_docling_pdf_falls_back_to_ocr_after_pdftext_garble(tracked_wks_config, tmp_path, monkeypatch):
    """OCR should recover PDFs when both docling and pdftotext are low-quality."""
    import wks.api.transform._docling._DoclingEngine as docling_module

    test_file = tmp_path / "nsda.pdf"
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
    ):

        def fake_run_docling(self, input_path, output_path, temp_output, options):
            expected_output = temp_output / f"{input_path.stem}.md"
            expected_output.write_text("012345678ÿÿ\n![Image](nsda_page_1.png)\n", encoding="utf-8")
            if False:
                yield ""
            return expected_output, []

        def fake_run_pdftext(self, input_path, options):
            if False:
                yield ""
            return "012345678ÿÿ\na/b/c/d/e\n"

        def fake_run_ocr(self, input_path, options):
            if False:
                yield ""
            return "Nuclear Safety Design Agreement for the SPARC Facility\nProject No. 52501\n"

        monkeypatch.setattr(docling_module._DoclingEngine, "_run_docling", fake_run_docling)
        monkeypatch.setattr(docling_module._DoclingEngine, "_run_pdftext_fallback", fake_run_pdftext)
        monkeypatch.setattr(docling_module._DoclingEngine, "_run_ocr_fallback", fake_run_ocr)

        result = run_cmd(
            cmd_engine,
            engine="dx",
            uri=URI.from_path(test_file),
            overrides={},
        )

        assert result.success is True
        content = get_content(result.output["checksum"])
        assert "Nuclear Safety Design Agreement" in content
        assert "Project No. 52501" in content
