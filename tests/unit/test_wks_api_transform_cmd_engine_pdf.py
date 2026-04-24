import subprocess

from tests.unit._transform_test_helpers import temporary_transform_config
from tests.unit.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.transform._EngineConfig import _EngineConfig
from wks.api.transform.cmd_engine import cmd_engine
from wks.api.transform.get_content import get_content


def dx_engine_config() -> dict[str, _EngineConfig]:
    return {
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


def run_dx_case(tmp_path, monkeypatch, *, stem, patch_docling, patch_pdftext=None, patch_ocr=None):
    import wks.api.transform._docling._DoclingEngine as docling_module

    test_file = tmp_path / f"{stem}.pdf"
    test_file.write_bytes(b"%PDF-1.4\nfake\n")

    monkeypatch.setattr(docling_module._DoclingEngine, "_run_docling", patch_docling)
    if patch_pdftext is not None:
        monkeypatch.setattr(docling_module._DoclingEngine, "_run_pdftext_fallback", patch_pdftext)
    if patch_ocr is not None:
        monkeypatch.setattr(docling_module._DoclingEngine, "_run_ocr_fallback", patch_ocr)

    with temporary_transform_config(engines=dx_engine_config()):
        result = run_cmd(cmd_engine, engine="dx", uri=URI.from_path(test_file), overrides={})
    assert result.success is True
    return get_content(result.output["checksum"])


def test_cmd_engine_docling_engine_type(tracked_wks_config, tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("test", encoding="utf-8")

    with temporary_transform_config(engines={"docling": _EngineConfig(type="docling", data={})}):
        result = run_cmd(cmd_engine, engine="docling", uri=URI.from_path(test_file), overrides={})
        assert result.success is False
        assert "docling" in result.result.lower() or "Unknown engine type" not in result.result


def test_cmd_engine_pdftext_engine_type(tracked_wks_config, tmp_path, monkeypatch):
    import wks.api.transform._pdftext._PdfTextEngine as pdftext_module

    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"%PDF-1.4\nfake\n")

    with temporary_transform_config(engines={"pdftext": _EngineConfig(type="pdftext", data={})}):
        monkeypatch.setattr(
            pdftext_module.subprocess,
            "run",
            lambda *args, **kwargs: subprocess.CompletedProcess(
                args=args[0], returncode=0, stdout="Extracted PDF text", stderr=""
            ),
        )
        result = run_cmd(cmd_engine, engine="pdftext", uri=URI.from_path(test_file), overrides={})

    assert result.success is True
    assert result.output["cached"] is False
    assert get_content(result.output["checksum"]) == "Extracted PDF text"


def test_cmd_engine_pdftext_rejects_non_pdf(tracked_wks_config, tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("not a pdf", encoding="utf-8")

    with temporary_transform_config(engines={"pdftext": _EngineConfig(type="pdftext", data={})}):
        result = run_cmd(cmd_engine, engine="pdftext", uri=URI.from_path(test_file), overrides={})

    assert result.success is False
    assert "unsupported file type" in result.result.lower()


def test_cmd_engine_docling_pdf_falls_back_to_pdftext_for_low_quality_output(tracked_wks_config, tmp_path, monkeypatch):
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

    content = run_dx_case(
        tmp_path,
        monkeypatch,
        stem="cor",
        patch_docling=fake_run_docling,
        patch_pdftext=fake_run_pdftext,
    )
    assert "COR-0017" in content


def test_cmd_engine_docling_pdf_falls_back_to_pdftext_after_docling_error(tracked_wks_config, tmp_path, monkeypatch):
    def fake_run_docling(self, input_path, output_path, temp_output, options):
        if False:
            yield ""
        raise RuntimeError("Docling failed with exit code 1")

    def fake_run_pdftext(self, input_path, options):
        if False:
            yield ""
        return "Recovered text from pdftotext fallback.\n"

    content = run_dx_case(
        tmp_path,
        monkeypatch,
        stem="fallback",
        patch_docling=fake_run_docling,
        patch_pdftext=fake_run_pdftext,
    )
    assert "Recovered text from pdftotext fallback." in content


def test_cmd_engine_docling_pdf_falls_back_to_ocr_after_pdftext_garble(tracked_wks_config, tmp_path, monkeypatch):
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

    content = run_dx_case(
        tmp_path,
        monkeypatch,
        stem="nsda",
        patch_docling=fake_run_docling,
        patch_pdftext=fake_run_pdftext,
        patch_ocr=fake_run_ocr,
    )
    assert "Nuclear Safety Design Agreement" in content
    assert "Project No. 52501" in content
