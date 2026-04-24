from pathlib import Path

from wks.api.log.append_log import append_log


def test_append_log_success(tmp_path):
    log_path = tmp_path / "test.log"
    append_log(log_path, "test", "INFO", "Hello")

    content = log_path.read_text(encoding="utf-8")
    assert "[test] INFO: Hello" in content


def test_append_log_io_error(tmp_path, monkeypatch):
    log_path = tmp_path / "error.log"

    def mock_open(*args, **kwargs):
        raise OSError("fail")

    monkeypatch.setattr(Path, "open", mock_open)

    append_log(log_path, "test", "ERROR", "Fail")
