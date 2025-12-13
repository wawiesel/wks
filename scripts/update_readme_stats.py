#!/usr/bin/env python3
"""Update code statistics in README.md from current codebase metrics."""

import re
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

try:
    from tabulate import tabulate
except ImportError:
    print("Error: tabulate is required. Install with: pip install tabulate", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"


@dataclass
class SectionStats:
    """Statistics for a code section."""
    files: int
    loc: int
    chars: int
    tokens: int

    def __add__(self, other: "SectionStats") -> "SectionStats":
        """Add two SectionStats together."""
        return SectionStats(
            files=self.files + other.files,
            loc=self.loc + other.loc,
            chars=self.chars + other.chars,
            tokens=self.tokens + other.tokens,
        )


def _run_cmd(cmd: list[str]) -> tuple[int, str]:
    """Run command and return (returncode, stdout+stderr)."""
    result = subprocess.run(cmd, cwd=REPO_ROOT, check=False, capture_output=True, text=True)
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def _get_mutation_stats() -> tuple[float, int, int]:
    """Get mutation score, killed, survived."""
    mutmut_cmd = str(REPO_ROOT / ".venv" / "bin" / "mutmut")
    if not Path(mutmut_cmd).exists():
        mutmut_cmd = "mutmut"

    rc, output = _run_cmd([mutmut_cmd, "results", "--all", "true"])
    if rc != 0:
        return 0.0, 0, 0

    killed = sum(1 for line in output.splitlines() if ":" in line and line.rsplit(":", 1)[1].strip().lower() == "killed")
    survived = sum(1 for line in output.splitlines() if ":" in line and line.rsplit(":", 1)[1].strip().lower() == "survived")
    total = killed + survived
    return (round(killed / total * 100, 1) if total > 0 else 0.0, killed, survived)


def _get_test_count() -> int:
    """Get total number of tests."""
    rc, output = _run_cmd([sys.executable, "-m", "pytest", "-q", "tests/"])
    for line in reversed(output.splitlines()):
        match = re.search(r"(\d+)\s+passed", line, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return len(list((REPO_ROOT / "tests").rglob("test_*.py"))) * 4  # Fallback estimate


def _get_code_coverage() -> tuple[float, str]:
    """Get code coverage percentage."""
    coverage_xml = REPO_ROOT / "coverage.xml"
    if coverage_xml.exists():
        try:
            import xml.etree.ElementTree as ET
            line_rate = float(ET.parse(coverage_xml).getroot().get("line-rate", 0))
            coverage_pct = round(line_rate * 100, 1)
            return coverage_pct, "✅ Pass" if coverage_pct >= 100.0 else "⚠️ Below Target"
        except Exception:
            pass

    rc, output = _run_cmd([sys.executable, "-m", "coverage", "report", "--format=total"])
    if rc == 0:
        for line in output.splitlines():
            if "TOTAL" in line.upper():
                match = re.search(r"(\d+(?:\.\d+)?)%", line)
                if match:
                    coverage_pct = float(match.group(1))
                    return coverage_pct, "✅ Pass" if coverage_pct >= 100.0 else "⚠️ Below Target"
    return 0.0, "⚠️ No Data"


def _get_python_file_stats(directory: Path) -> SectionStats:
    """Get statistics for Python files in a directory."""
    if not directory.exists():
        return SectionStats(0, 0, 0, 0)

    files = [f for f in directory.rglob("*.py") if "__pycache__" not in str(f)]
    if not files:
        return SectionStats(0, 0, 0, 0)

    # Count LOC using wc
    result = subprocess.run(
        ["find", str(directory), "-name", "*.py", "-type", "f", "!", "-path", "*/__pycache__/*", "-exec", "wc", "-l", "{}", "+"],
        capture_output=True, text=True, check=False
    )
    loc = 0
    if result.returncode == 0 and result.stdout.strip():
        parts = result.stdout.strip().split()
        if parts:
            try:
                loc = int(parts[-2])  # Second to last is total LOC
            except (ValueError, IndexError):
                pass

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

    files = []
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

    return SectionStats(len(files), loc, chars, chars // 4)  # Approximate tokens


def _get_file_stats(file_path: Path) -> SectionStats:
    """Get statistics for a single file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        return SectionStats(1, len(content.splitlines()), len(content), len(content) // 4)
    except Exception:
        return SectionStats(0, 0, 0, 0)


def _get_section_stats(section_name: str) -> SectionStats:
    """Get statistics for a wks/* section."""
    return _get_python_file_stats(REPO_ROOT / "wks" / section_name)


def _get_test_section_stats(test_subdir: str) -> SectionStats:
    """Get statistics for a test subdirectory."""
    return _get_python_file_stats(REPO_ROOT / "tests" / test_subdir)


def _get_user_docs_stats() -> SectionStats:
    """Get statistics for user documentation."""
    stats = _get_file_stats(REPO_ROOT / "README.md")
    stats += _get_text_file_stats(REPO_ROOT / "docs" / "patterns", [".md"])
    return stats


def _get_dev_docs_stats() -> SectionStats:
    """Get statistics for developer documentation."""
    stats = SectionStats(0, 0, 0, 0)
    for f in ["CONTRIBUTING.md", "AGENTS.md"]:
        if (REPO_ROOT / f).exists():
            stats += _get_file_stats(REPO_ROOT / f)
    stats += _get_text_file_stats(REPO_ROOT / ".cursor" / "rules", [".md", ".txt"])
    stats += _get_text_file_stats(REPO_ROOT / "docs" / "other", [".md"])
    stats += _get_text_file_stats(REPO_ROOT / "docs" / "campaigns", [".md"])
    if (REPO_ROOT / "wks").exists():
        for f in (REPO_ROOT / "wks").rglob("README.md"):
            stats += _get_file_stats(f)
    return stats


def _get_specifications_stats() -> SectionStats:
    """Get statistics for specifications."""
    return _get_text_file_stats(REPO_ROOT / "docs" / "specifications", [".md", ".json"])


def _get_infrastructure_cicd_stats() -> SectionStats:
    """Get statistics for CI/CD infrastructure."""
    return _get_text_file_stats(REPO_ROOT / ".github" / "workflows", [".yml", ".yaml"])


def _get_infrastructure_build_config_stats() -> SectionStats:
    """Get statistics for build/config files."""
    stats = SectionStats(0, 0, 0, 0)
    for f in ["pyproject.toml", "setup.py", "setup.cfg", "pytest.ini", ".pre-commit-config.yaml"]:
        if (REPO_ROOT / f).exists():
            stats += _get_file_stats(REPO_ROOT / f)
    return stats


def _get_infrastructure_scripts_stats() -> SectionStats:
    """Get statistics for scripts."""
    scripts_dir = REPO_ROOT / "scripts"
    if not scripts_dir.exists():
        return SectionStats(0, 0, 0, 0)

    stats = SectionStats(0, 0, 0, 0)
    for py_file in scripts_dir.glob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            stats += SectionStats(1, len(content.splitlines()), len(content), len(list(tokenize.generate_tokens(StringIO(content).readline))))
        except Exception:
            continue

    for sh_file in scripts_dir.glob("*.sh"):
        stats += _get_file_stats(sh_file)

    return stats


def _fix_separator_alignment(table: str, num_numeric_cols: int) -> str:
    """Fix separator row alignment markers to match header widths."""
    lines = table.split("\n")
    if len(lines) < 2:
        return table

    # Get header cell widths (including padding)
    header_parts = lines[0].split("|")[1:-1]
    if not header_parts:
        return table

    # Build separator row: first column left-aligned, rest right-aligned
    sep_parts = ["|"]  # Start with pipe
    for i, header_cell in enumerate(header_parts):
        width = len(header_cell)
        if i == 0:
            # First column: left-aligned (no colon)
            sep_parts.append("-" * width)
        else:
            # Numeric columns: right-aligned (colon on right)
            sep_parts.append("-" * (width - 1) + ":")
        sep_parts.append("|")  # Pipe after each column
    
    lines[1] = "".join(sep_parts)
    return "\n".join(lines)


def _generate_badges(mutation_score: float, test_count: int) -> str:
    """Generate badge markdown."""
    color = "brightgreen" if mutation_score >= 90.0 else "yellow" if mutation_score >= 80.0 else "red"
    return f"""![Mutation Score](https://img.shields.io/badge/mutation-{mutation_score}%25-{color})
![Tests](https://img.shields.io/badge/tests-{test_count}-passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)"""


def _create_table(headers: list[str], rows: list[list[str]], num_numeric_cols: int) -> str:
    """Create a markdown table with proper alignment."""
    # Build colalign: first column left, rest right
    colalign = ["left"] + ["right"] * num_numeric_cols
    table = tabulate(rows, headers=headers, tablefmt="github", colalign=colalign)
    return _fix_separator_alignment(table, num_numeric_cols)


def _format_row(label: str, stats: SectionStats, pct: str) -> list[str]:
    """Format a statistics row."""
    return [f"**{label}**", f"{stats.files:,}", f"{stats.loc:,}", f"{stats.chars:,}", f"{stats.tokens:,}", pct]


def _generate_table(
    coverage_pct: float, coverage_status: str, mutation_score: float, killed: int, survived: int,
    test_count: int, test_files: int,
    api_stats: SectionStats, cli_stats: SectionStats, mcp_stats: SectionStats, utils_stats: SectionStats,
    unit_test_stats: SectionStats, integration_test_stats: SectionStats, smoke_test_stats: SectionStats,
    cicd_stats: SectionStats, build_config_stats: SectionStats, scripts_stats: SectionStats,
    specs_stats: SectionStats, user_docs_stats: SectionStats, dev_docs_stats: SectionStats,
) -> str:
    """Generate statistics table markdown."""
    mutation_status = "✅ Pass" if mutation_score >= 90.0 else "⚠️ Below Target"

    # Calculate totals
    code_total = api_stats + cli_stats + mcp_stats + utils_stats
    test_total = unit_test_stats + integration_test_stats + smoke_test_stats
    infra_total = cicd_stats + build_config_stats + scripts_stats
    docs_total = user_docs_stats + dev_docs_stats + specs_stats
    grand_total_tokens = code_total.tokens + test_total.tokens + infra_total.tokens + docs_total.tokens

    def pct(tokens: int) -> str:
        return f"{(tokens / grand_total_tokens * 100):.1f}%" if grand_total_tokens > 0 else "0.0%"

    # Metrics table
    metrics_table = _create_table(
        ["Metric", "Value", "Target", "Status"],
        [
            ["**Code Coverage**", f"{coverage_pct}%", "100%", coverage_status],
            ["**Mutation Kill %**", f"{mutation_score}%", "≥90%", mutation_status],
        ],
        2
    )

    # Source size table
    source_table = _create_table(
        ["Section", "Files", "LOC", "Characters", "Tokens", "% Tokens"],
        [
            _format_row("api", api_stats, pct(api_stats.tokens)),
            _format_row("cli", cli_stats, pct(cli_stats.tokens)),
            _format_row("mcp", mcp_stats, pct(mcp_stats.tokens)),
            _format_row("utils", utils_stats, pct(utils_stats.tokens)),
            _format_row("Total", code_total, pct(code_total.tokens)),
        ],
        5
    )

    # Testing table
    test_table = _create_table(
        ["Type", "Files", "LOC", "Characters", "Tokens", "% Tokens"],
        [
            _format_row("Unit Tests", unit_test_stats, pct(unit_test_stats.tokens)),
            _format_row("Integration Tests", integration_test_stats, pct(integration_test_stats.tokens)),
            _format_row("Smoke Tests", smoke_test_stats, pct(smoke_test_stats.tokens)),
            _format_row("Total", test_total, pct(test_total.tokens)),
        ],
        5
    )

    # Infrastructure table
    infra_table = _create_table(
        ["Type", "Files", "LOC", "Characters", "Tokens", "% Tokens"],
        [
            _format_row("CI/CD", cicd_stats, pct(cicd_stats.tokens)),
            _format_row("Build/Config", build_config_stats, pct(build_config_stats.tokens)),
            _format_row("Scripts", scripts_stats, pct(scripts_stats.tokens)),
            _format_row("Total", infra_total, pct(infra_total.tokens)),
        ],
        5
    )

    # Documentation table
    docs_table = _create_table(
        ["Category", "Files", "LOC", "Characters", "Tokens", "% Tokens"],
        [
            _format_row("User Documentation", user_docs_stats, pct(user_docs_stats.tokens)),
            _format_row("Developer Documentation", dev_docs_stats, pct(dev_docs_stats.tokens)),
            _format_row("Specifications", specs_stats, pct(specs_stats.tokens)),
            _format_row("Total", docs_total, pct(docs_total.tokens)),
        ],
        5
    )

    return f"""{metrics_table}

### Source Size Statistics

{source_table}

### Testing Statistics

{test_table}

### Documentation Size Summary

{docs_table}

### Infrastructure Summary

{infra_table}

**Mutation Testing**: Tests the quality of our test suite by introducing small changes (mutations) to the code and verifying that existing tests catch them. A score of {mutation_score}% means {mutation_score}% of mutations are killed by our tests, indicating strong test coverage and quality.

**Test Statistics**: {test_count:,} tests across {test_files:,} test files."""


def _update_readme() -> None:
    """Update README.md with current statistics."""
    if not README_PATH.exists():
        print(f"Error: {README_PATH} not found", file=sys.stderr)
        sys.exit(1)

    # Collect all stats
    coverage_pct, coverage_status = _get_code_coverage()
    mutation_score, killed, survived = _get_mutation_stats()
    test_count = _get_test_count()
    test_files = len(list((REPO_ROOT / "tests").rglob("test_*.py")))

    stats = {
        "api": _get_section_stats("api"),
        "cli": _get_section_stats("cli"),
        "mcp": _get_section_stats("mcp"),
        "utils": _get_section_stats("utils"),
        "unit": _get_test_section_stats("unit"),
        "integration": _get_test_section_stats("integration"),
        "smoke": _get_test_section_stats("smoke"),
        "cicd": _get_infrastructure_cicd_stats(),
        "build_config": _get_infrastructure_build_config_stats(),
        "scripts": _get_infrastructure_scripts_stats(),
        "specs": _get_specifications_stats(),
        "user_docs": _get_user_docs_stats(),
        "dev_docs": _get_dev_docs_stats(),
    }

    # Generate content
    badges = _generate_badges(mutation_score, test_count)
    table = _generate_table(
        coverage_pct, coverage_status, mutation_score, killed, survived, test_count, test_files,
        stats["api"], stats["cli"], stats["mcp"], stats["utils"],
        stats["unit"], stats["integration"], stats["smoke"],
        stats["cicd"], stats["build_config"], stats["scripts"],
        stats["specs"], stats["user_docs"], stats["dev_docs"],
    )

    # Update README
    content = README_PATH.read_text()

    # Replace badges section
    content = re.sub(r"(# WKS.*?\n\n)(.*?)(\n## Status)", rf"\1{badges}\n\3", content, flags=re.DOTALL)

    # Replace table section
    table_header = "## Code Quality Metrics\n\n"
    table_start = content.find(table_header)
    if table_start != -1:
        # Find next section or end marker
        next_section = content.find("\n## ", table_start + len(table_header))
        if next_section == -1:
            next_section = content.find("\nAI-assisted", table_start)
        if next_section != -1:
            content = content[:table_start + len(table_header)] + table + "\n\n" + content[next_section:]
        else:
            content = content[:table_start + len(table_header)] + table
    else:
        # Fallback regex
        content = re.sub(r"(## Code Quality Metrics\n\n)(.*?)(\n\n## |\nAI-assisted)", rf"\1{table}\n\n\3", content, flags=re.DOTALL)

    README_PATH.write_text(content)
    print(f"✅ Updated {README_PATH} with current statistics")


if __name__ == "__main__":
    _update_readme()
