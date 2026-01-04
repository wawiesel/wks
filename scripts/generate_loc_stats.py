#!/usr/bin/env python3
"""Generate Lines of Code statistics (loc.json)."""

import json
import sys
from dataclasses import asdict
from pathlib import Path

# Fix path to allow importing from same directory
sys.path.append(str(Path(__file__).resolve().parent))

try:
    from stats_lib import SectionStats
except ImportError as e:
    print(f"Error importing stats_lib: {e}", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _get_python_file_stats(directory: Path) -> SectionStats:
    """Get statistics for Python files in a directory."""
    # Logic similar to original but focused on LOC/files per section
    # Reuse logic from update_readme_stats.py but implementation here for independence
    # or import from lib if moved there?
    # I'll re-implement using stats_lib structures if possible, but stats_lib is just classes.
    # Actually, stats_lib currently has NO collection logic, just data classes and formatting.
    # To avoid duplication, I should move collection logic to stats_lib or keep it here.
    # I'll keep it here for now to satisfy task: independent generation scripts.
    import contextlib
    import subprocess
    import tokenize
    from io import StringIO

    if not directory.exists():
        return SectionStats(0, 0, 0, 0)

    files = [f for f in directory.rglob("*.py") if "__pycache__" not in str(f)]
    if not files:
        return SectionStats(0, 0, 0, 0)

    # Count LOC using wc
    result = subprocess.run(
        [
            "find",
            str(directory),
            "-name",
            "*.py",
            "-type",
            "f",
            "!",
            "-path",
            "*/__pycache__/*",
            "-exec",
            "wc",
            "-l",
            "{}",
            "+",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    loc = 0
    if result.returncode == 0 and result.stdout.strip():
        parts = result.stdout.strip().split()
        if parts:
            with contextlib.suppress(ValueError, IndexError):
                loc = int(parts[-2])

    # Count chars and tokens
    chars = 0
    tokens = 0
    for py_file in files:
        try:
            content = py_file.read_text(encoding="utf-8")
            chars += len(content)
            tokens += len(list(tokenize.generate_tokens(StringIO(content).readline)))
        except Exception:
            continue

    return SectionStats(len(files), loc, chars, tokens)


def _get_text_file_stats(directory: Path, extensions: list[str]) -> SectionStats:
    """Get statistics for text files in a directory."""
    if not directory.exists():
        return SectionStats(0, 0, 0, 0)

    files: list[Path] = []
    for ext in extensions:
        files.extend(directory.glob(f"**/*{ext}"))
    files = [f for f in files if "__pycache__" not in str(f) and "/.git/" not in str(f)]

    chars = 0
    loc = 0
    for file_path in files:
        try:
            content = file_path.read_text(encoding="utf-8")
            chars += len(content)
            loc += len(content.splitlines())
        except Exception:
            continue

    return SectionStats(len(files), loc, chars, chars // 4)


def _get_file_stats(file_path: Path) -> SectionStats:
    try:
        content = file_path.read_text(encoding="utf-8")
        return SectionStats(1, len(content.splitlines()), len(content), len(content) // 4)
    except Exception:
        return SectionStats(0, 0, 0, 0)


def _collect_loc_stats() -> dict:
    """Collect LOC stats for all sections."""

    # Helpers for specific sections
    def get_py(path_parts):
        return _get_python_file_stats(REPO_ROOT.joinpath(*path_parts))

    # Infrastructure Scripts
    scripts_dir = REPO_ROOT / "scripts"
    scripts_stats = SectionStats(0, 0, 0, 0)
    if scripts_dir.exists():
        # count .py using _get_python_file_stats logic for dir?
        # Actually _get_python_file_stats is recursive.
        # But scripts dir has .sh too.
        # I'll reuse the logic from original update_readme_stats.py
        import tokenize
        from io import StringIO

        for py_file in scripts_dir.glob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
                scripts_stats += SectionStats(
                    1,
                    len(content.splitlines()),
                    len(content),
                    len(list(tokenize.generate_tokens(StringIO(content).readline))),
                )
            except Exception:
                continue
        for sh_file in scripts_dir.glob("*.sh"):
            scripts_stats += _get_file_stats(sh_file)

    # Dev Docs
    dev_docs = SectionStats(0, 0, 0, 0)
    for f in ["CONTRIBUTING.md", "AGENTS.md"]:
        if (REPO_ROOT / f).exists():
            dev_docs += _get_file_stats(REPO_ROOT / f)
    dev_docs += _get_text_file_stats(REPO_ROOT / ".cursor" / "rules", [".md", ".txt"])
    dev_docs += _get_text_file_stats(REPO_ROOT / "docs" / "other", [".md"])
    dev_docs += _get_text_file_stats(REPO_ROOT / "docs" / "campaigns", [".md"])
    if (REPO_ROOT / "wks").exists():
        for readme_file in (REPO_ROOT / "wks").rglob("README.md"):
            dev_docs += _get_file_stats(readme_file)

    # Build Config
    build_config = SectionStats(0, 0, 0, 0)
    for f in ["pyproject.toml", "setup.py", "setup.cfg", "pytest.ini", ".pre-commit-config.yaml"]:
        if (REPO_ROOT / f).exists():
            build_config += _get_file_stats(REPO_ROOT / f)

    return {
        "sections": {
            "api": asdict(get_py(["wks", "api"])),
            "cli": asdict(get_py(["wks", "cli"])),
            "mcp": asdict(get_py(["wks", "mcp"])),
            "utils": asdict(get_py(["wks", "utils"])),
            "unit": asdict(get_py(["tests", "unit"])),
            "integration": asdict(get_py(["tests", "integration"])),
            "smoke": asdict(get_py(["tests", "smoke"])),
            "cicd": asdict(_get_text_file_stats(REPO_ROOT / ".github" / "workflows", [".yml", ".yaml"])),
            "build_config": asdict(build_config),
            "scripts": asdict(scripts_stats),
            "specs": asdict(_get_text_file_stats(REPO_ROOT / "docs" / "specifications", [".md", ".json"])),
            "user_docs": asdict(_get_text_file_stats(REPO_ROOT / "docs" / "patterns", [".md"])),
            "dev_docs": asdict(dev_docs),
        }
    }


def main():
    stats = _collect_loc_stats()

    metrics_dir = REPO_ROOT / "qa" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    (metrics_dir / "loc.json").write_text(json.dumps(stats, indent=2, sort_keys=True) + "\n")
    print(f"✅ Generated {metrics_dir}/loc.json")


if __name__ == "__main__":
    main()
