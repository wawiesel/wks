"""Tests for TestEngine."""

from wks.api.transform.engines import TestEngine


class TestTestEngine:
    """Test TestEngine."""

    def test_get_extension(self):
        """TestEngine returns 'md' extension."""
        engine = TestEngine()

        ext = engine.get_extension({})

        assert ext == "md"

    def test_transform(self, tmp_path):
        """TestEngine transforms by copying with prefix."""
        engine = TestEngine()

        input_path = tmp_path / "input.txt"
        input_path.write_text("Hello World")

        output_path = tmp_path / "output.md"

        engine.transform(input_path, output_path, {})

        assert output_path.exists()
        content = output_path.read_text()
        assert content == "Transformed: Hello World"

    def test_transform_preserves_content(self, tmp_path):
        """TestEngine preserves original content with prefix."""
        engine = TestEngine()

        input_path = tmp_path / "input.txt"
        input_path.write_text("Original content\nWith multiple lines")

        output_path = tmp_path / "output.md"

        engine.transform(input_path, output_path, {})

        content = output_path.read_text()
        assert content.startswith("Transformed: ")
        assert "Original content" in content
        assert "With multiple lines" in content
