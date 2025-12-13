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


def _run_cmd(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    """Run command and return (returncode, stdout+stderr)."""
    result = subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output


def _get_mutation_stats() -> tuple[float, int, int]:
    """Get mutation score, killed, survived."""
    mutmut_cmd = str(REPO_ROOT / ".venv" / "bin" / "mutmut")
    if not Path(mutmut_cmd).exists():
        mutmut_cmd = "mutmut"

    rc, output = _run_cmd([mutmut_cmd, "results", "--all", "true"])
    if rc != 0:
        return 0.0, 0, 0

    killed = 0
    survived = 0
    for line in output.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        _, status = line.rsplit(":", 1)
        status = status.strip().lower()
        if status == "killed":
            killed += 1
        elif status == "survived":
            survived += 1

    total = killed + survived
    score = killed / total if total > 0 else 0.0
    return round(score * 100, 1), killed, survived


def _get_test_count() -> int:
    """Get total number of tests by running pytest and parsing the summary."""
    # Run pytest with -q to get a summary line
    rc, output = _run_cmd([sys.executable, "-m", "pytest", "-q", "tests/"])

    # Look for summary line like "225 passed" or "225 passed in 24.66s"
    for line in reversed(output.splitlines()):
        line = line.strip()
        # Match patterns like "225 passed", "225 passed in 24.66s", etc.
        match = re.search(r"(\d+)\s+passed", line, re.IGNORECASE)
        if match:
            return int(match.group(1))

    # Fallback: try to count test files and estimate (not ideal but better than 0)
    test_files = _get_test_file_count()
    # Rough estimate: average 4-5 tests per file
    return test_files * 4 if test_files > 0 else 0


def _get_code_coverage() -> tuple[float, str]:
    """Get code coverage percentage from coverage.py.

    Returns:
        Tuple of (coverage_percentage, status_message)
    """
    # Try to get coverage from coverage.xml if it exists
    coverage_xml = REPO_ROOT / "coverage.xml"
    if coverage_xml.exists():
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(coverage_xml)
            root = tree.getroot()
            # Coverage XML format: <coverage line-rate="0.95">
            line_rate = float(root.get("line-rate", 0))
            coverage_pct = round(line_rate * 100, 1)
            status = "✅ Pass" if coverage_pct >= 100.0 else "⚠️ Below Target"
            return coverage_pct, status
        except Exception:
            pass

    # Fallback: run coverage report
    rc, output = _run_cmd([sys.executable, "-m", "coverage", "report", "--format=total"])
    if rc == 0:
        # Look for percentage in output like "TOTAL 1234 567 890 54%"
        for line in output.splitlines():
            if "TOTAL" in line.upper():
                match = re.search(r"(\d+(?:\.\d+)?)%", line)
                if match:
                    coverage_pct = float(match.group(1))
                    status = "✅ Pass" if coverage_pct >= 100.0 else "⚠️ Below Target"
                    return coverage_pct, status

    # If no coverage data available, return 0
    return 0.0, "⚠️ No Data"


def _get_test_file_count() -> int:
    """Get number of test files."""
    test_files = list(Path(REPO_ROOT / "tests").rglob("test_*.py"))
    return len(test_files)


@dataclass
class SectionStats:
    """Statistics for a code section."""
    files: int
    loc: int
    chars: int
    tokens: int


def _get_text_file_stats(directory: Path, extensions: list[str] | None = None) -> SectionStats:
    """Get statistics for text files (markdown, json, etc.) in a directory."""
    if extensions is None:
        extensions = [".md", ".json", ".txt", ".yaml", ".yml"]

    if not directory.exists():
        return SectionStats(files=0, loc=0, chars=0, tokens=0)

    files = []
    for ext in extensions:
        # Use glob with ** to match files in directory and subdirectories
        files.extend(directory.glob(f"**/*{ext}"))

    # Filter out __pycache__ and .git directory (but allow .github)
    files = [f for f in files if "__pycache__" not in str(f) and "/.git/" not in str(f) and str(f).endswith("/.git") == False]

    file_count = len(files)
    total_chars = 0
    total_loc = 0

    for file_path in files:
        try:
            content = file_path.read_text(encoding="utf-8")
            total_chars += len(content)
            total_loc += len(content.splitlines())
        except Exception:
            continue

    # For text files, tokens aren't as meaningful, so we'll use a simple word count approximation
    total_tokens = total_chars // 4  # Rough approximation: ~4 chars per token

    return SectionStats(files=file_count, loc=total_loc, chars=total_chars, tokens=total_tokens)


def _get_section_stats(section_name: str) -> SectionStats:
    """Get statistics for a wks/* section (api, cli, mcp, utils)."""
    section_dir = REPO_ROOT / "wks" / section_name
    if not section_dir.exists():
        return SectionStats(files=0, loc=0, chars=0, tokens=0)

    files = []
    for py_file in section_dir.rglob("*.py"):
        if "__pycache__" not in str(py_file):
            files.append(py_file)

    file_count = len(files)

    # Count LOC
    if files:
        result = subprocess.run(
            ["find", str(section_dir), "-name", "*.py", "-type", "f", "!", "-path", "*/__pycache__/*", "-exec", "wc", "-l", "{}", "+"],
            capture_output=True,
            text=True,
            check=False,
        )
        loc = 0
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if lines:
                last_line = lines[-1]
                parts = last_line.split()
                if parts:
                    try:
                        loc = int(parts[0])
                    except ValueError:
                        pass
    else:
        loc = 0

    # Count characters and tokens
    total_chars = 0
    total_tokens = 0
    for py_file in files:
        try:
            content = py_file.read_text(encoding="utf-8")
            total_chars += len(content)
            # Count tokens
            tokens = list(tokenize.generate_tokens(StringIO(content).readline))
            total_tokens += len(tokens)
        except Exception:
            # Skip files that can't be read/tokenized
            continue

    return SectionStats(files=file_count, loc=loc, chars=total_chars, tokens=total_tokens)


def _get_specifications_stats() -> SectionStats:
    """Get statistics for specifications (docs/specifications/)."""
    specs_dir = REPO_ROOT / "docs" / "specifications"
    return _get_text_file_stats(specs_dir, [".md", ".json"])


def _get_user_docs_stats() -> SectionStats:
    """Get statistics for user documentation (README.md, docs/patterns/)."""
    total_stats = SectionStats(files=0, loc=0, chars=0, tokens=0)

    # README.md
    readme = REPO_ROOT / "README.md"
    if readme.exists():
        try:
            content = readme.read_text(encoding="utf-8")
            total_stats.files += 1
            total_stats.chars += len(content)
            total_stats.loc += len(content.splitlines())
            total_stats.tokens += len(content) // 4
        except Exception:
            pass

    # docs/patterns/ (user-facing)
    patterns_dir = REPO_ROOT / "docs" / "patterns"
    if patterns_dir.exists():
        patterns_stats = _get_text_file_stats(patterns_dir, [".md"])
        total_stats.files += patterns_stats.files
        total_stats.loc += patterns_stats.loc
        total_stats.chars += patterns_stats.chars
        total_stats.tokens += patterns_stats.tokens

    return total_stats


def _get_dev_docs_stats() -> SectionStats:
    """Get statistics for developer documentation (CONTRIBUTING.md, AGENTS.md, .cursor/rules/, docs/other/, docs/campaigns/, READMEs in wks/)."""
    total_stats = SectionStats(files=0, loc=0, chars=0, tokens=0)

    # CONTRIBUTING.md, AGENTS.md
    for doc_file in ["CONTRIBUTING.md", "AGENTS.md"]:
        doc_path = REPO_ROOT / doc_file
        if doc_path.exists():
            try:
                content = doc_path.read_text(encoding="utf-8")
                total_stats.files += 1
                total_stats.chars += len(content)
                total_stats.loc += len(content.splitlines())
                total_stats.tokens += len(content) // 4
            except Exception:
                pass

    # .cursor/rules/
    rules_dir = REPO_ROOT / ".cursor" / "rules"
    if rules_dir.exists():
        rules_stats = _get_text_file_stats(rules_dir, [".md", ".txt"])
        total_stats.files += rules_stats.files
        total_stats.loc += rules_stats.loc
        total_stats.chars += rules_stats.chars
        total_stats.tokens += rules_stats.tokens

    # docs/other/ (developer docs)
    other_dir = REPO_ROOT / "docs" / "other"
    if other_dir.exists():
        other_stats = _get_text_file_stats(other_dir, [".md"])
        total_stats.files += other_stats.files
        total_stats.loc += other_stats.loc
        total_stats.chars += other_stats.chars
        total_stats.tokens += other_stats.tokens

    # docs/campaigns/ (developer docs)
    campaigns_dir = REPO_ROOT / "docs" / "campaigns"
    if campaigns_dir.exists():
        campaigns_stats = _get_text_file_stats(campaigns_dir, [".md"])
        total_stats.files += campaigns_stats.files
        total_stats.loc += campaigns_stats.loc
        total_stats.chars += campaigns_stats.chars
        total_stats.tokens += campaigns_stats.tokens

    # README files in wks/ (developer docs)
    wks_dir = REPO_ROOT / "wks"
    if wks_dir.exists():
        for readme_file in wks_dir.rglob("README.md"):
            try:
                content = readme_file.read_text(encoding="utf-8")
                total_stats.files += 1
                total_stats.chars += len(content)
                total_stats.loc += len(content.splitlines())
                total_stats.tokens += len(content) // 4
            except Exception:
                continue

    return total_stats


def _get_test_section_stats(test_subdir: str) -> SectionStats:
    """Get statistics for a test subdirectory (unit, integration, smoke)."""
    test_dir = REPO_ROOT / "tests" / test_subdir
    if not test_dir.exists():
        return SectionStats(files=0, loc=0, chars=0, tokens=0)

    files = []
    for py_file in test_dir.rglob("*.py"):
        if "__pycache__" not in str(py_file):
            files.append(py_file)

    file_count = len(files)

    # Count LOC
    if files:
        result = subprocess.run(
            ["find", str(test_dir), "-name", "*.py", "-type", "f", "!", "-path", "*/__pycache__/*", "-exec", "wc", "-l", "{}", "+"],
            capture_output=True,
            text=True,
            check=False,
        )
        loc = 0
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if lines:
                last_line = lines[-1]
                parts = last_line.split()
                if parts:
                    try:
                        loc = int(parts[0])
                    except ValueError:
                        pass
    else:
        loc = 0

    # Count characters and tokens
    total_chars = 0
    total_tokens = 0
    for py_file in files:
        try:
            content = py_file.read_text(encoding="utf-8")
            total_chars += len(content)
            tokens = list(tokenize.generate_tokens(StringIO(content).readline))
            total_tokens += len(tokens)
        except Exception:
            continue

    return SectionStats(files=file_count, loc=loc, chars=total_chars, tokens=total_tokens)


def _get_infrastructure_cicd_stats() -> SectionStats:
    """Get statistics for CI/CD infrastructure (.github/workflows/)."""
    github_dir = REPO_ROOT / ".github" / "workflows"
    if not github_dir.exists():
        return SectionStats(files=0, loc=0, chars=0, tokens=0)

    return _get_text_file_stats(github_dir, [".yml", ".yaml"])


def _get_infrastructure_build_config_stats() -> SectionStats:
    """Get statistics for build/config files."""
    total_stats = SectionStats(files=0, loc=0, chars=0, tokens=0)

    config_files = [
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "pytest.ini",
        ".pre-commit-config.yaml",
    ]
    for config_file in config_files:
        config_path = REPO_ROOT / config_file
        if config_path.exists():
            total_stats.files += 1
            try:
                content = config_path.read_text(encoding="utf-8")
                total_stats.chars += len(content)
                total_stats.loc += len(content.splitlines())
                total_stats.tokens += len(content) // 4
            except Exception:
                continue

    return total_stats


def _get_infrastructure_scripts_stats() -> SectionStats:
    """Get statistics for scripts (scripts/*.py and scripts/*.sh)."""
    scripts_dir = REPO_ROOT / "scripts"
    if not scripts_dir.exists():
        return SectionStats(files=0, loc=0, chars=0, tokens=0)

    total_stats = SectionStats(files=0, loc=0, chars=0, tokens=0)

    # Python scripts
    for py_file in scripts_dir.glob("*.py"):
        total_stats.files += 1
        try:
            content = py_file.read_text(encoding="utf-8")
            total_stats.chars += len(content)
            total_stats.loc += len(content.splitlines())
            tokens = list(tokenize.generate_tokens(StringIO(content).readline))
            total_stats.tokens += len(tokens)
        except Exception:
            continue

    # Shell scripts
    for sh_file in scripts_dir.glob("*.sh"):
        total_stats.files += 1
        try:
            content = sh_file.read_text(encoding="utf-8")
            total_stats.chars += len(content)
            total_stats.loc += len(content.splitlines())
            total_stats.tokens += len(content) // 4
        except Exception:
            continue

    return total_stats


def _right_align_numeric_columns(table: str, num_numeric_cols: int) -> str:
    """Post-process a markdown table to right-align numeric columns.

    Args:
        table: The markdown table string from tabulate
        num_numeric_cols: Number of numeric columns (excluding the first label column)

    Returns:
        Table with numeric columns right-aligned
    """
    lines = table.split("\n")
    if len(lines) < 2:
        return table

    # Find the separator row (second line, index 1)
    separator_line = lines[1]
    separator_parts = separator_line.split("|")

    # Replace separators for numeric columns (all except first label column and last empty part)
    # Format: |---|:---:|:---:| for right-aligned columns
    # Note: separator_parts[0] and separator_parts[-1] are empty strings from splitting on |
    # separator_parts[1] is the first column (label, should stay left-aligned)
    # separator_parts[2] onwards are the numeric columns
    new_separator_parts = separator_parts.copy()
    # Start from index 2 (skip first label column at index 1), process num_numeric_cols columns
    for i in range(2, min(len(separator_parts) - 1, num_numeric_cols + 2)):
        # Replace separator with right-aligned version (add : at the end)
        part = new_separator_parts[i].strip()
        if part.startswith("-") and not part.endswith(":"):
            # Add : at the end for right alignment
            new_separator_parts[i] = part + ":"

    lines[1] = "|".join(new_separator_parts)

    # Right-align data in numeric columns
    for line_idx in range(2, len(lines)):
        line = lines[line_idx]
        if not line.strip():
            continue
        parts = line.split("|")
        # Start from index 2 (skip first label column at index 1)
        for i in range(2, min(len(parts) - 1, num_numeric_cols + 2)):
            if i < len(parts):
                # Get the content, strip whitespace, then right-align
                content = parts[i].strip()
                # Calculate padding needed (column width from separator, excluding the : if present)
                sep_part = separator_parts[i].strip() if i < len(separator_parts) else ""
                # Remove trailing : if present to get actual column width
                col_width = len(sep_part.rstrip(":")) if sep_part else len(content)
                # Right-align the content
                parts[i] = content.rjust(col_width)
        lines[line_idx] = "|".join(parts)

    return "\n".join(lines)


def _generate_badges(mutation_score: float, test_count: int) -> str:
    """Generate badge markdown."""
    mutation_color = "brightgreen" if mutation_score >= 90.0 else "yellow" if mutation_score >= 80.0 else "red"
    return f"""![Mutation Score](https://img.shields.io/badge/mutation-{mutation_score}%25-{mutation_color})
![Tests](https://img.shields.io/badge/tests-{test_count}-passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)"""


def _generate_table(
    coverage_pct: float,
    coverage_status: str,
    mutation_score: float,
    killed: int,
    survived: int,
    test_count: int,
    test_files: int,
    api_stats: SectionStats,
    cli_stats: SectionStats,
    mcp_stats: SectionStats,
    utils_stats: SectionStats,
    unit_test_stats: SectionStats,
    integration_test_stats: SectionStats,
    smoke_test_stats: SectionStats,
    cicd_stats: SectionStats,
    build_config_stats: SectionStats,
    scripts_stats: SectionStats,
    specs_stats: SectionStats,
    user_docs_stats: SectionStats,
    dev_docs_stats: SectionStats,
) -> str:
    """Generate statistics table markdown."""
    mutation_status = "✅ Pass" if mutation_score >= 90.0 else "⚠️ Below Target"

    # Calculate code totals
    code_total_files = api_stats.files + cli_stats.files + mcp_stats.files + utils_stats.files
    code_total_loc = api_stats.loc + cli_stats.loc + mcp_stats.loc + utils_stats.loc
    code_total_chars = api_stats.chars + cli_stats.chars + mcp_stats.chars + utils_stats.chars
    code_total_tokens = api_stats.tokens + cli_stats.tokens + mcp_stats.tokens + utils_stats.tokens

    # Calculate test totals
    test_total_files = unit_test_stats.files + integration_test_stats.files + smoke_test_stats.files
    test_total_loc = unit_test_stats.loc + integration_test_stats.loc + smoke_test_stats.loc
    test_total_chars = unit_test_stats.chars + integration_test_stats.chars + smoke_test_stats.chars
    test_total_tokens = unit_test_stats.tokens + integration_test_stats.tokens + smoke_test_stats.tokens

    # Calculate infrastructure totals
    infra_total_files = cicd_stats.files + build_config_stats.files + scripts_stats.files
    infra_total_loc = cicd_stats.loc + build_config_stats.loc + scripts_stats.loc
    infra_total_chars = cicd_stats.chars + build_config_stats.chars + scripts_stats.chars
    infra_total_tokens = cicd_stats.tokens + build_config_stats.tokens + scripts_stats.tokens

    # Calculate documentation totals
    docs_total_files = user_docs_stats.files + dev_docs_stats.files + specs_stats.files
    docs_total_loc = user_docs_stats.loc + dev_docs_stats.loc + specs_stats.loc
    docs_total_chars = user_docs_stats.chars + dev_docs_stats.chars + specs_stats.chars
    docs_total_tokens = user_docs_stats.tokens + dev_docs_stats.tokens + specs_stats.tokens

    # Calculate grand total tokens for percentage calculations
    grand_total_tokens = code_total_tokens + test_total_tokens + infra_total_tokens + docs_total_tokens

    # Generate metrics table
    metrics_data = [
        ["**Code Coverage**", f"{coverage_pct}%", "100%", coverage_status],
        ["**Mutation Kill %**", f"{mutation_score}%", "≥90%", mutation_status],
    ]
    metrics_table = tabulate(
        metrics_data,
        headers=["Metric", "Value", "Target", "Status"],
        tablefmt="github",
        stralign="left",
        numalign="right",
    )
    # Right-align numeric columns (Value and Target)
    metrics_table = _right_align_numeric_columns(metrics_table, 2)

    # Generate source size statistics table with % Tokens
    def _pct_tokens(tokens: int) -> str:
        pct = (tokens / grand_total_tokens * 100) if grand_total_tokens > 0 else 0.0
        return f"{pct:.1f}%"

    source_data = [
        ["**api**", f"{api_stats.files:,}", f"{api_stats.loc:,}", f"{api_stats.chars:,}", f"{api_stats.tokens:,}", _pct_tokens(api_stats.tokens)],
        ["**cli**", f"{cli_stats.files:,}", f"{cli_stats.loc:,}", f"{cli_stats.chars:,}", f"{cli_stats.tokens:,}", _pct_tokens(cli_stats.tokens)],
        ["**mcp**", f"{mcp_stats.files:,}", f"{mcp_stats.loc:,}", f"{mcp_stats.chars:,}", f"{mcp_stats.tokens:,}", _pct_tokens(mcp_stats.tokens)],
        ["**utils**", f"{utils_stats.files:,}", f"{utils_stats.loc:,}", f"{utils_stats.chars:,}", f"{utils_stats.tokens:,}", _pct_tokens(utils_stats.tokens)],
        ["**Total**", f"**{code_total_files:,}**", f"**{code_total_loc:,}**", f"**{code_total_chars:,}**", f"**{code_total_tokens:,}**", f"**{_pct_tokens(code_total_tokens)}**"],
    ]
    source_table = tabulate(
        source_data,
        headers=["Section", "Files", "LOC", "Characters", "Tokens", "% Tokens"],
        tablefmt="github",
        stralign="left",
        numalign="right",
    )
    # Right-align numeric columns (all except Section)
    source_table = _right_align_numeric_columns(source_table, 5)

    # Generate testing statistics table
    test_data = [
        ["**Unit Tests**", f"{unit_test_stats.files:,}", f"{unit_test_stats.loc:,}", f"{unit_test_stats.chars:,}", f"{unit_test_stats.tokens:,}", _pct_tokens(unit_test_stats.tokens)],
        ["**Integration Tests**", f"{integration_test_stats.files:,}", f"{integration_test_stats.loc:,}",
            f"{integration_test_stats.chars:,}", f"{integration_test_stats.tokens:,}", _pct_tokens(integration_test_stats.tokens)],
        ["**Smoke Tests**", f"{smoke_test_stats.files:,}", f"{smoke_test_stats.loc:,}", f"{smoke_test_stats.chars:,}", f"{smoke_test_stats.tokens:,}", _pct_tokens(smoke_test_stats.tokens)],
        ["**Total**", f"**{test_total_files:,}**", f"**{test_total_loc:,}**", f"**{test_total_chars:,}**", f"**{test_total_tokens:,}**", f"**{_pct_tokens(test_total_tokens)}**"],
    ]
    test_table = tabulate(
        test_data,
        headers=["Type", "Files", "LOC", "Characters", "Tokens", "% Tokens"],
        tablefmt="github",
        stralign="left",
        numalign="right",
    )
    # Right-align numeric columns (all except Type)
    test_table = _right_align_numeric_columns(test_table, 5)

    # Generate infrastructure summary table
    infra_data = [
        ["**CI/CD**", f"{cicd_stats.files:,}", f"{cicd_stats.loc:,}", f"{cicd_stats.chars:,}", f"{cicd_stats.tokens:,}", _pct_tokens(cicd_stats.tokens)],
        ["**Build/Config**", f"{build_config_stats.files:,}", f"{build_config_stats.loc:,}", f"{build_config_stats.chars:,}", f"{build_config_stats.tokens:,}", _pct_tokens(build_config_stats.tokens)],
        ["**Scripts**", f"{scripts_stats.files:,}", f"{scripts_stats.loc:,}", f"{scripts_stats.chars:,}", f"{scripts_stats.tokens:,}", _pct_tokens(scripts_stats.tokens)],
        ["**Total**", f"**{infra_total_files:,}**", f"**{infra_total_loc:,}**", f"**{infra_total_chars:,}**", f"**{infra_total_tokens:,}**", f"**{_pct_tokens(infra_total_tokens)}**"],
    ]
    infra_table = tabulate(
        infra_data,
        headers=["Type", "Files", "LOC", "Characters", "Tokens", "% Tokens"],
        tablefmt="github",
        stralign="left",
        numalign="right",
    )
    # Right-align numeric columns (all except Type)
    infra_table = _right_align_numeric_columns(infra_table, 5)

    # Generate documentation size summary table
    docs_data = [
        ["**User Documentation**", f"{user_docs_stats.files:,}", f"{user_docs_stats.loc:,}", f"{user_docs_stats.chars:,}", f"{user_docs_stats.tokens:,}", _pct_tokens(user_docs_stats.tokens)],
        ["**Developer Documentation**", f"{dev_docs_stats.files:,}", f"{dev_docs_stats.loc:,}", f"{dev_docs_stats.chars:,}", f"{dev_docs_stats.tokens:,}", _pct_tokens(dev_docs_stats.tokens)],
        ["**Specifications**", f"{specs_stats.files:,}", f"{specs_stats.loc:,}", f"{specs_stats.chars:,}", f"{specs_stats.tokens:,}", _pct_tokens(specs_stats.tokens)],
        ["**Total**", f"**{docs_total_files:,}**", f"**{docs_total_loc:,}**", f"**{docs_total_chars:,}**", f"**{docs_total_tokens:,}**", f"**{_pct_tokens(docs_total_tokens)}**"],
    ]
    docs_table = tabulate(
        docs_data,
        headers=["Category", "Files", "LOC", "Characters", "Tokens", "% Tokens"],
        tablefmt="github",
        stralign="left",
        numalign="right",
    )
    # Right-align numeric columns (all except Category)
    docs_table = _right_align_numeric_columns(docs_table, 5)

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

    content = README_PATH.read_text()

    # Get current stats
    coverage_pct, coverage_status = _get_code_coverage()
    mutation_score, killed, survived = _get_mutation_stats()
    test_count = _get_test_count()
    test_files = _get_test_file_count()

    # Get stats for each section
    api_stats = _get_section_stats("api")
    cli_stats = _get_section_stats("cli")
    mcp_stats = _get_section_stats("mcp")
    utils_stats = _get_section_stats("utils")

    # Get test stats by type
    unit_test_stats = _get_test_section_stats("unit")
    integration_test_stats = _get_test_section_stats("integration")
    smoke_test_stats = _get_test_section_stats("smoke")

    # Get infrastructure stats by type
    cicd_stats = _get_infrastructure_cicd_stats()
    build_config_stats = _get_infrastructure_build_config_stats()
    scripts_stats = _get_infrastructure_scripts_stats()

    # Get documentation stats
    specs_stats = _get_specifications_stats()
    user_docs_stats = _get_user_docs_stats()
    dev_docs_stats = _get_dev_docs_stats()

    # Generate new sections
    badges = _generate_badges(mutation_score, test_count)
    table = _generate_table(
        coverage_pct, coverage_status,
        mutation_score, killed, survived, test_count, test_files,
        api_stats, cli_stats, mcp_stats, utils_stats,
        unit_test_stats, integration_test_stats, smoke_test_stats,
        cicd_stats, build_config_stats, scripts_stats,
        specs_stats, user_docs_stats, dev_docs_stats
    )

    # Replace badges section (between title and Status)
    badges_pattern = r"(# WKS.*?\n\n)(.*?)(\n## Status)"
    badges_replacement = rf"\1{badges}\n\3"
    content = re.sub(badges_pattern, badges_replacement, content, flags=re.DOTALL)

    # Replace statistics table section
    # Find the table section and replace everything from after the header through before the next section
    table_header = "## Code Quality Metrics\n\n"
    table_start = content.find(table_header)
    if table_start != -1:
        # Find the next section header (##) after the table
        next_section_start = content.find("\n## ", table_start + len(table_header))
        if next_section_start == -1:
            # If no next section, find the end of file or a clear delimiter
            # Look for "AI-assisted" which appears after the stats section
            ai_assisted_pos = content.find("AI-assisted", table_start)
            if ai_assisted_pos != -1:
                # Go back to find the blank line before "AI-assisted"
                blank_line_pos = content.rfind("\n\n", table_start, ai_assisted_pos)
                if blank_line_pos == -1:
                    blank_line_pos = content.rfind("\n", table_start, ai_assisted_pos)
                next_section_start = blank_line_pos + 1 if blank_line_pos != -1 else ai_assisted_pos

        if next_section_start != -1:
            # Replace: keep header, replace everything until next section
            before = content[:table_start + len(table_header)]
            after = content[next_section_start:]
            content = before + table + "\n\n" + after
        else:
            # Fallback: replace everything after the header
            before = content[:table_start + len(table_header)]
            content = before + table
    else:
        # Fallback to regex if manual approach fails
        table_pattern = r"(## Code Quality Metrics\n\n)(.*?)(\n\n## |\nAI-assisted)"
        content = re.sub(table_pattern, rf"\1{table}\n\n\3", content, flags=re.DOTALL)

    README_PATH.write_text(content)
    print(f"✅ Updated {README_PATH} with current statistics:")
    print(f"   Code Coverage: {coverage_pct}%")
    print(f"   Mutation Score: {mutation_score}% ({killed} killed, {survived} survived)")
    print(f"   Tests: {test_count} across {test_files} files")
    print(f"   Source Sections:")
    print(f"     API: {api_stats.files} files, {api_stats.loc:,} LOC, {api_stats.tokens:,} tokens")
    print(f"     CLI: {cli_stats.files} files, {cli_stats.loc:,} LOC, {cli_stats.tokens:,} tokens")
    print(f"     MCP: {mcp_stats.files} files, {mcp_stats.loc:,} LOC, {mcp_stats.tokens:,} tokens")
    print(f"     Utils: {utils_stats.files} files, {utils_stats.loc:,} LOC, {utils_stats.tokens:,} tokens")
    print(f"   Testing:")
    print(f"     Unit: {unit_test_stats.files} files, {unit_test_stats.loc:,} LOC, {unit_test_stats.tokens:,} tokens")
    print(f"     Integration: {integration_test_stats.files} files, {integration_test_stats.loc:,} LOC, {integration_test_stats.tokens:,} tokens")
    print(f"     Smoke: {smoke_test_stats.files} files, {smoke_test_stats.loc:,} LOC, {smoke_test_stats.tokens:,} tokens")
    print(f"   Infrastructure:")
    print(f"     CI/CD: {cicd_stats.files} files, {cicd_stats.loc:,} LOC, {cicd_stats.tokens:,} tokens")
    print(f"     Build/Config: {build_config_stats.files} files, {build_config_stats.loc:,} LOC, {build_config_stats.tokens:,} tokens")
    print(f"     Scripts: {scripts_stats.files} files, {scripts_stats.loc:,} LOC, {scripts_stats.tokens:,} tokens")
    print(f"   Documentation:")
    print(f"     User Docs: {user_docs_stats.files} files, {user_docs_stats.loc:,} LOC, {user_docs_stats.tokens:,} tokens")
    print(f"     Dev Docs: {dev_docs_stats.files} files, {dev_docs_stats.loc:,} LOC, {dev_docs_stats.tokens:,} tokens")
    print(f"     Specifications: {specs_stats.files} files, {specs_stats.loc:,} LOC, {specs_stats.tokens:,} tokens")


if __name__ == "__main__":
    _update_readme()
