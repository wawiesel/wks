"""Unit tests for wks.api.transform._auto_engine module."""

import pytest

from wks.api.transform._auto_engine import select_auto_engine

pytestmark = pytest.mark.unit


class TestSelectAutoEngine:
    def test_code_extension_py(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("print('hello')")
        assert select_auto_engine(f) == "treesitter"

    def test_code_extension_js(self, tmp_path):
        f = tmp_path / "app.js"
        f.write_text("console.log('hi')")
        assert select_auto_engine(f) == "treesitter"

    def test_document_extension_pdf(self, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.4 fake")
        assert select_auto_engine(f) == "docling"

    def test_document_extension_docx(self, tmp_path):
        f = tmp_path / "doc.docx"
        f.write_bytes(b"PK\x03\x04 fake docx")
        assert select_auto_engine(f) == "docling"

    def test_plain_text_file(self, tmp_path):
        f = tmp_path / "readme.txt"
        f.write_text("Just some plain text content.")
        assert select_auto_engine(f) == "textpass"

    def test_binary_file_null_bytes(self, tmp_path):
        f = tmp_path / "data.dat"
        f.write_bytes(b"\x00\x01\x02\xff\xfe")
        assert select_auto_engine(f) == "binarypass"

    def test_non_utf8_text(self, tmp_path):
        f = tmp_path / "data.dat"
        # Latin-1 text with no null bytes but not valid UTF-8
        f.write_bytes(b"\xc0\xc1\xfe\xff" * 100)
        assert select_auto_engine(f) == "binarypass"

    def test_nonexistent_file(self, tmp_path):
        f = tmp_path / "nope.xyz"
        assert select_auto_engine(f) == "binarypass"

    def test_unknown_text_extension(self, tmp_path):
        f = tmp_path / "notes.log"
        f.write_text("log entry 1\nlog entry 2\n")
        assert select_auto_engine(f) == "textpass"
