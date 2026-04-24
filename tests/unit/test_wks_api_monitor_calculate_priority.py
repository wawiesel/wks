from pathlib import Path

import pytest

from wks.api.monitor.calculate_priority import calculate_priority

pytestmark = pytest.mark.monitor


def build_weights(*, extension_weights: dict[str, float] | None = None) -> dict[str, float | dict[str, float]]:
    return {
        "depth_multiplier": 0.9,
        "underscore_multiplier": 0.5,
        "only_underscore_multiplier": 0.1,
        "extension_weights": extension_weights or {},
    }


def build_priority_dirs(tmp_path: Path, relative_dirs: dict[str, float]) -> dict[str, float]:
    return {str((tmp_path / relative_dir).resolve()): value for relative_dir, value in relative_dirs.items()}


@pytest.mark.parametrize(
    ("relative_dirs", "relative_file", "weights", "expected"),
    [
        ({"other": 100.0}, "file.txt", build_weights(), 0.0),
        ({".": 100.0}, "file.txt", build_weights(), 100.0),
        ({".": 100.0}, "subdir/file.txt", build_weights(), 90.0),
        ({".": 100.0}, "level1/level2/file.txt", build_weights(), 81.0),
        ({".": 100.0}, "_private/file.txt", build_weights(), 45.0),
        ({".": 100.0}, "__private/file.txt", build_weights(), 22.5),
        ({".": 100.0}, "_/file.txt", build_weights(), 9.0),
        ({".": 100.0}, "file.py", build_weights(extension_weights={".py": 2.0, ".txt": 0.5}), 200.0),
        ({".": 100.0}, "file.txt", build_weights(extension_weights={".py": 2.0}), 100.0),
        ({".": 100.0}, "_file.txt", build_weights(), 45.0),
        ({".": 100.0}, "_.txt", build_weights(), 9.0),
        ({".": 100.0, "subdir": 200.0}, "subdir/file.txt", build_weights(), 200.0),
        (
            {".": 100.0},
            "level1/_private/__file.py",
            build_weights(extension_weights={".py": 2.0}),
            100.0 * 0.9 * 0.9 * 0.5 * 0.9 * 0.5 * 0.5 * 2.0,
        ),
        ({".": 100.0}, "file", build_weights(), 100.0),
    ],
)
def test_calculate_priority_cases(
    tmp_path: Path,
    relative_dirs: dict[str, float],
    relative_file: str,
    weights: dict[str, float | dict[str, float]],
    expected: float,
):
    test_file = tmp_path / relative_file
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("test")

    priority = calculate_priority(test_file, build_priority_dirs(tmp_path, relative_dirs), weights)
    assert priority == pytest.approx(expected)


def test_calculate_priority_valueerror_different_drives(monkeypatch, tmp_path: Path):
    test_file = tmp_path / "file.txt"
    test_file.write_text("test")
    original_relative_to = Path.relative_to

    def mock_relative_to(self: Path, other: Path):
        if other == tmp_path.resolve():
            raise ValueError("Paths are on different drives")
        return original_relative_to(self, other)

    monkeypatch.setattr("pathlib.Path.relative_to", mock_relative_to)

    priority = calculate_priority(test_file, build_priority_dirs(tmp_path, {".": 100.0}), build_weights())
    assert priority > 0.0
