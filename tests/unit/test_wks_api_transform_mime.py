import mimetypes
from pathlib import Path
from unittest.mock import patch

from wks.api.transform import mime


class TestNormalizeExtension:
    def test_empty_string(self):
        assert mime.normalize_extension("") == ""

    def test_whitespace_string(self):
        assert mime.normalize_extension("   ") == ""

    def test_extension_with_leading_dot(self):
        assert mime.normalize_extension(".py") == ".py"

    def test_extension_without_leading_dot(self):
        assert mime.normalize_extension("py") == ".py"

    def test_extension_with_mixed_case(self):
        assert mime.normalize_extension(".PY") == ".py"
        assert mime.normalize_extension("TxT") == ".txt"

    def test_extension_with_whitespace(self):
        assert mime.normalize_extension(" .md ") == ".md"
        assert mime.normalize_extension(" js") == ".js"


class TestGuessMimeType:
    def test_guess_type_from_mimetypes(self):
        with patch("mimetypes.guess_type", return_value=("application/pdf", None)):
            path = Path("document.pdf")
            assert mime.guess_mime_type(path) == "application/pdf"

    def test_guess_type_from_custom_extension_to_mime(self):
        # Ensure mimetypes.guess_type doesn't return anything for .yaml to test fallback
        with patch("mimetypes.guess_type", return_value=(None, None)):
            path = Path("config.yaml")
            assert mime.guess_mime_type(path) == "text/x-yaml"

    def test_guess_type_for_unknown_extension_falls_back_to_octet_stream(self):
        with patch("mimetypes.guess_type", return_value=(None, None)):
            path = Path("file.xyz")
            assert mime.guess_mime_type(path) == "application/octet-stream"

    def test_guess_type_for_file_without_extension(self):
        with patch("mimetypes.guess_type", return_value=(None, None)):
            path = Path("Dockerfile")
            assert mime.guess_mime_type(path) == "application/octet-stream"

    def test_guess_type_for_path_object(self):
        path = Path("/path/to/script.py")
        # Assuming mimetypes would guess .py, or our custom map
        assert mime.guess_mime_type(path) in ["text/x-python", "application/x-python-code"]


class TestExtensionForMime:
    def test_extension_from_custom_mime_to_extension(self):
        assert mime.extension_for_mime("text/x-python") == ".py"
        assert mime.extension_for_mime("application/typescript") == ".ts"

    def test_extension_from_mimetypes_guess_extension(self):
        # Assuming mimetypes can guess .pdf for application/pdf
        assert mime.extension_for_mime("application/pdf") == ".pdf"

    def test_extension_for_unknown_mime_type(self):
        assert mime.extension_for_mime("application/x-unknown") is None

    def test_extension_for_mime_with_case_and_whitespace(self):
        assert mime.extension_for_mime(" TEXT/X-PYTHON ") == ".py"


class TestMimeForExtension:
    def test_mime_from_custom_extension_to_mime(self):
        assert mime.mime_for_extension(".py") == "text/x-python"
        assert mime.mime_for_extension("ts") == "application/typescript"  # normalized

    def test_mime_from_mimetypes_types_map(self):
        # Assuming .pdf is in mimetypes.types_map but not our custom map for this test
        with patch.dict(mimetypes.types_map, {".pdf": "application/pdf"}, clear=True):
            assert mime.mime_for_extension(".pdf") == "application/pdf"
            assert mime.mime_for_extension("pdf") == "application/pdf"

    def test_mime_for_unknown_extension(self):
        assert mime.mime_for_extension(".xyz") in {None, "chemical/x-xyz"}

    def test_mime_for_extension_with_mixed_case_and_no_dot(self):
        assert mime.mime_for_extension("JSON") == "application/json"
        assert mime.mime_for_extension("html") == "text/html"

    def test_mime_for_extension_prefers_custom_map(self):
        # If both custom and mimetypes have an entry, custom should win
        # Example: custom map has .js as 'application/javascript', mimetypes might have 'text/javascript'
        with patch.dict(mimetypes.types_map, {".js": "text/javascript"}):
            assert mime.mime_for_extension(".js") == "application/javascript"
