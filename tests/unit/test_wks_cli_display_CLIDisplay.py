from rich.text import Text

from wks.cli.display.CLIDisplay import CLIDisplay


def test_status_segments_render_full_spaced_path_as_one_styled_segment(monkeypatch):
    """Segmented status lines should style the full path, including spaces, as one segment."""
    display = CLIDisplay()
    calls: list[tuple[object, dict]] = []

    def capture_print(renderable, **kwargs):
        calls.append((renderable, kwargs))

    monkeypatch.setattr(display.stderr_console, "print", capture_print)

    path = "/Users/ww5/Documents/Programs/DNCSH/2026-DNCSH_Documents/2026_04-HST_Package/COR-0017 Code of Record.pdf"
    display.status(
        f"Retrieving content for {path}...",
        segments=(
            ("Retrieving content for ", None),
            (path, "magenta"),
            ("...", None),
        ),
    )

    renderable, kwargs = calls[0]

    assert isinstance(renderable, Text)
    assert kwargs["highlight"] is False
    assert kwargs["soft_wrap"] is True
    assert path in renderable.plain

    path_start = renderable.plain.index(path)
    path_end = path_start + len(path)
    assert any(
        span.start == path_start and span.end == path_end and str(span.style) == "magenta" for span in renderable.spans
    )
