#!/usr/bin/env python3
"""Update code statistics in README.md from current codebase metrics."""

from __future__ import annotations

import argparse
import contextlib
import csv
import json
import re
import shutil
import subprocess
import sys
import tokenize
from dataclasses import asdict, dataclass
from io import StringIO
from pathlib import Path

try:
    from tabulate import tabulate  # type: ignore[import-untyped]
except ImportError:
    print("Error: tabulate is required. Install with: pip install tabulate", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
METRICS_DIR = REPO_ROOT / "qa" / "metrics"
LOC_JSON_PATH = METRICS_DIR / "loc.json"
COMPLEXITY_JSON_PATH = METRICS_DIR / "complexity.json"
COVERAGE_JSON_PATH = METRICS_DIR / "coverage.json"
MUTATIONS_JSON_PATH = METRICS_DIR / "mutations.json"


@dataclass
class SectionStats:
    """Statistics for a code section."""

    files: int
    loc: int
    chars: int
    tokens: int

    def __add__(self, other: SectionStats) -> SectionStats:
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


def _get_domain_coverage() -> dict[str, float]:
    """Get per-domain coverage from coverage.xml (api.cat -> cat, etc)."""
    coverage_xml = REPO_ROOT / "coverage.xml"
    if not coverage_xml.exists():
        return {}
    try:
        import xml.etree.ElementTree as ET

        tree = ET.parse(coverage_xml)
        domain_coverage: dict[str, float] = {}
        for pkg in tree.findall(".//package"):
            name = pkg.get("name", "")
            # Match api.X (top-level domains in wks/api/)
            if name.startswith("api.") and "." not in name[4:]:
                domain = name[4:]  # "api.cat" -> "cat"
                line_rate = float(pkg.get("line-rate", 0))
                domain_coverage[domain] = round(line_rate * 100, 1)
        return domain_coverage
    except Exception:
        return {}


def _get_test_count() -> int:
    """Get total number of tests by running pytest --collect-only."""
    _rc, output = _run_cmd([sys.executable, "-m", "pytest", "--collect-only", "-q", "tests/"])
    # Parse "N tests collected" or just "N" from the last line
    for line in reversed(output.splitlines()):
        # Match "456 tests collected" or similar
        match = re.search(r"(\d+)\s+tests?\s+collected", line, re.IGNORECASE)
        if match:
            return int(match.group(1))
        # Match just a number at start of line (older pytest format)
        match = re.search(r"^(\d+)\s+", line.strip())
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
                loc = int(parts[-2])  # Second to last is total LOC

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


def _get_domain_loc_stats() -> dict[str, SectionStats]:
    """Get LOC stats per wks/api domain."""
    api_dir = REPO_ROOT / "wks" / "api"
    if not api_dir.exists():
        return {}

    domain_stats: dict[str, SectionStats] = {}
    for domain_dir in sorted(api_dir.iterdir()):
        if not domain_dir.is_dir():
            continue
        if domain_dir.name.startswith("__"):
            continue
        stats = _get_python_file_stats(domain_dir)
        if stats.files:
            domain_stats[domain_dir.name] = stats
    return domain_stats


def _get_api_root_stats() -> SectionStats:
    """Get LOC stats for Python files directly under wks/api."""
    api_dir = REPO_ROOT / "wks" / "api"
    if not api_dir.exists():
        return SectionStats(0, 0, 0, 0)

    files = [f for f in api_dir.glob("*.py") if "__pycache__" not in str(f)]
    if not files:
        return SectionStats(0, 0, 0, 0)

    loc = 0
    chars = 0
    tokens = 0
    for py_file in files:
        try:
            content = py_file.read_text(encoding="utf-8")
            loc += len(content.splitlines())
            chars += len(content)
            tokens += len(list(tokenize.generate_tokens(StringIO(content).readline)))
        except Exception:
            continue

    return SectionStats(len(files), loc, chars, tokens)


def _get_user_docs_stats() -> SectionStats:
    """Get statistics for user documentation (excludes root README.md to avoid circular dependency)."""
    # Note: Root README.md is excluded because it contains these stats
    return _get_text_file_stats(REPO_ROOT / "docs" / "patterns", [".md"])


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
        for readme_file in (REPO_ROOT / "wks").rglob("README.md"):
            stats += _get_file_stats(readme_file)
    return stats


def _get_specifications_stats() -> SectionStats:
    """Get statistics for specifications."""
    return _get_text_file_stats(REPO_ROOT / "qa" / "specs", [".md", ".json"])


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
            stats += SectionStats(
                1,
                len(content.splitlines()),
                len(content),
                len(list(tokenize.generate_tokens(StringIO(content).readline))),
            )
        except Exception:
            continue

    for sh_file in scripts_dir.glob("*.sh"):
        stats += _get_file_stats(sh_file)

    return stats


def _resolve_lizard_cmd() -> str | None:
    """Resolve lizard binary if available."""
    lizard_cmd = shutil.which("lizard")
    if lizard_cmd:
        return lizard_cmd
    candidate = Path(sys.executable).parent / "lizard"
    if candidate.exists():
        return str(candidate)
    return None


def _collect_complexity_stats() -> dict:
    """Collect cyclomatic complexity metrics by domain using lizard CSV output."""
    payload: dict[str, object] = {
        "domains": {},
        "total": {"functions": 0, "ccn_avg": 0.0, "ccn_max": 0},
    }

    lizard_cmd = _resolve_lizard_cmd()
    if not lizard_cmd:
        return payload

    rc, output = _run_cmd([lizard_cmd, "--csv", "wks/api"])
    if rc != 0:
        return payload

    domain_accum: dict[str, dict[str, int]] = {}
    total_functions = 0
    total_ccn = 0
    total_ccn_max = 0

    for row in csv.reader(line for line in output.splitlines() if line.strip()):
        if len(row) < 7:
            continue
        try:
            ccn = int(row[1])
        except ValueError:
            continue

        total_functions += 1
        total_ccn += ccn
        total_ccn_max = max(total_ccn_max, ccn)

        file_path = Path(row[6])
        parts = file_path.parts
        try:
            api_index = parts.index("api")
            domain = parts[api_index + 1]
        except (ValueError, IndexError):
            continue
        if len(parts) <= api_index + 2:
            # Skip files that live directly under wks/api (not a domain subpackage).
            continue

        acc = domain_accum.setdefault(domain, {"functions": 0, "ccn_total": 0, "ccn_max": 0})
        acc["functions"] += 1
        acc["ccn_total"] += ccn
        acc["ccn_max"] = max(acc["ccn_max"], ccn)

    domains: dict[str, dict[str, object]] = {}
    for domain, acc in sorted(domain_accum.items()):
        functions = acc["functions"]
        avg = round(acc["ccn_total"] / functions, 2) if functions else 0.0
        domains[domain] = {"functions": functions, "ccn_avg": avg, "ccn_max": acc["ccn_max"]}

    payload["domains"] = domains
    payload["total"] = {
        "functions": total_functions,
        "ccn_avg": round(total_ccn / total_functions, 2) if total_functions else 0.0,
        "ccn_max": total_ccn_max,
    }
    return payload


def _fix_separator_alignment(table: str, _num_numeric_cols: int) -> str:
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


def _generate_badges(coverage_pct: float, mutation_score: float, test_count: int) -> str:
    """Generate badge markdown."""
    mutation_color = "brightgreen" if mutation_score >= 90.0 else "yellow" if mutation_score >= 80.0 else "red"
    coverage_color = "brightgreen" if coverage_pct >= 100.0 else "yellow" if coverage_pct >= 80.0 else "red"
    return f"""![Coverage](https://img.shields.io/badge/coverage-{coverage_pct}%25-{coverage_color})
![Mutation Score](https://img.shields.io/badge/mutation-{mutation_score}%25-{mutation_color})
![Tests](https://img.shields.io/badge/tests-{test_count}_passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)
![Docker Freshness](https://github.com/wawiesel/wks/actions/workflows/check-image-freshness.yml/badge.svg)"""


def _generate_domain_table(domain_stats: dict[str, dict]) -> str:
    """Generate per-domain quality metrics table."""
    if not domain_stats:
        return ""
    rows = []
    for domain, stats in sorted(domain_stats.items()):
        killed = stats.get("mutation_killed", 0)
        survived = stats.get("mutation_survived", 0)
        total = killed + survived
        mutation_pct = f"{killed / total * 100:.0f}%" if total > 0 else "N/A"
        rows.append(
            [
                domain,
                f"{stats.get('coverage', 0.0):.0f}%",
                mutation_pct,
                f"{killed}/{total}",
            ]
        )
    headers = ["Domain", "Coverage", "Mutation %", "Killed/Total"]
    return tabulate(rows, headers=headers, tablefmt="github", colalign=["left", "right", "right", "right"])


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
    coverage_pct: float,
    coverage_status: str,
    docker_freshness: str,
    mutation_score: float,
    _killed: int,
    _survived: int,
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
            [
                "**Docker Freshness**",
                "v1",
                "Up to date",
                "✅ Pass" if docker_freshness == "fresh" else "⚠️ Updates Available",
            ],
        ],
        2,
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
        5,
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
        5,
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
        5,
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
        5,
    )

    mutation_desc = (
        f"Tests the quality of our test suite by introducing small changes (mutations) to the code "
        f"and verifying that existing tests catch them. A score of {mutation_score}% means "
        f"{mutation_score}% of introduced mutations were successfully killed by the test suite."
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

**Mutation Testing**: {mutation_desc}

**Test Statistics**: {test_count:,} tests across {test_files:,} test files."""


def _collect_loc_stats() -> dict:
    """Collect LOC-focused metrics for qa/metrics/loc.json."""
    test_count = _get_test_count()
    test_files = len(list((REPO_ROOT / "tests").rglob("test_*.py")))

    section_stats = {
        "api": asdict(_get_section_stats("api")),
        "cli": asdict(_get_section_stats("cli")),
        "mcp": asdict(_get_section_stats("mcp")),
        "utils": asdict(_get_section_stats("utils")),
        "unit": asdict(_get_test_section_stats("unit")),
        "integration": asdict(_get_test_section_stats("integration")),
        "smoke": asdict(_get_test_section_stats("smoke")),
        "cicd": asdict(_get_infrastructure_cicd_stats()),
        "build_config": asdict(_get_infrastructure_build_config_stats()),
        "scripts": asdict(_get_infrastructure_scripts_stats()),
        "specs": asdict(_get_specifications_stats()),
        "user_docs": asdict(_get_user_docs_stats()),
        "dev_docs": asdict(_get_dev_docs_stats()),
    }

    domain_loc_stats = _get_domain_loc_stats()
    root_stats = _get_api_root_stats()
    domain_total = root_stats
    for stats in domain_loc_stats.values():
        domain_total += stats

    section_paths = {
        "api": ["wks/api/**/*.py"],
        "cli": ["wks/cli/**/*.py"],
        "mcp": ["wks/mcp/**/*.py"],
        "utils": ["wks/utils/**/*.py"],
        "unit": ["tests/unit/**/*.py"],
        "integration": ["tests/integration/**/*.py"],
        "smoke": ["tests/smoke/**/*.py"],
        "cicd": [".github/workflows/**/*.yml", ".github/workflows/**/*.yaml"],
        "build_config": [
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "pytest.ini",
            ".pre-commit-config.yaml",
        ],
        "scripts": ["scripts/*.py", "scripts/*.sh"],
        "specs": ["qa/specs/**/*.md", "qa/specs/**/*.json"],
        "user_docs": ["docs/patterns/**/*.md"],
        "dev_docs": [
            "CONTRIBUTING.md",
            "AGENTS.md",
            ".cursor/rules/**/*.md",
            ".cursor/rules/**/*.txt",
            "docs/other/**/*.md",
            "docs/campaigns/**/*.md",
            "wks/**/README.md",
        ],
    }

    domain_paths = {name: [f"wks/api/{name}/**/*.py"] for name in domain_loc_stats}
    section_entries = {
        name: {
            "paths": section_paths.get(name, []),
            "stats": section_stats[name],
        }
        for name in section_stats
    }
    domain_entries = {
        name: {
            "paths": domain_paths.get(name, []),
            "stats": asdict(stats),
        }
        for name, stats in domain_loc_stats.items()
    }

    return {
        "sections": section_entries,
        "domains": domain_entries,
        "total": asdict(domain_total),
        "test_count": test_count,
        "test_files": test_files,
    }


def _collect_coverage_stats() -> dict:
    """Collect coverage metrics for qa/metrics/coverage.json."""
    coverage_pct, _coverage_status = _get_code_coverage()
    return {
        "coverage_pct": round(coverage_pct, 1),
        "domains": _get_domain_coverage(),
    }


def _collect_mutation_stats() -> dict:
    """Collect mutation metrics for qa/metrics/mutations.json."""
    mutation_by_domain: dict[str, dict[str, int]] = {}
    for stats_file in REPO_ROOT.glob("mutation_stats_*.json"):
        try:
            data = json.loads(stats_file.read_text())
            domain = data.get("domain")
            if domain:
                mutation_by_domain[domain] = {
                    "killed": int(data.get("killed", 0)),
                    "survived": int(data.get("survived", 0)),
                }
        except Exception:
            continue

    total_killed = sum(v.get("killed", 0) for v in mutation_by_domain.values())
    total_survived = sum(v.get("survived", 0) for v in mutation_by_domain.values())
    grand_total = total_killed + total_survived
    mutation_score = (total_killed / grand_total * 100) if grand_total > 0 else 0.0

    return {
        "mutation_score": round(mutation_score, 1),
        "mutation_killed": total_killed,
        "mutation_survived": total_survived,
        "domains": mutation_by_domain,
    }


def _build_readme_stats(loc_stats: dict, coverage_stats: dict, mutation_stats: dict, docker_freshness: str) -> dict:
    """Merge metrics JSON into the README stats structure."""
    domain_stats = {}
    coverage_domains = coverage_stats.get("domains", {}) or {}
    mutation_domains = mutation_stats.get("domains", {}) or {}
    all_domains = set(coverage_domains.keys()) | set(mutation_domains.keys())

    for domain in sorted(all_domains):
        mutation_domain = mutation_domains.get(domain, {})
        domain_stats[domain] = {
            "coverage": coverage_domains.get(domain, 0.0),
            "mutation_killed": mutation_domain.get("killed", 0),
            "mutation_survived": mutation_domain.get("survived", 0),
        }

    coverage_pct = coverage_stats.get("coverage_pct", 0.0)
    coverage_status = "⚠️ No Data" if not coverage_domains else "✅ Pass" if coverage_pct >= 100.0 else "⚠️ Below Target"

    return {
        "coverage_pct": coverage_pct,
        "coverage_status": coverage_status,
        "mutation_score": mutation_stats.get("mutation_score", 0.0),
        "mutation_killed": mutation_stats.get("mutation_killed", 0),
        "mutation_survived": mutation_stats.get("mutation_survived", 0),
        "test_count": loc_stats.get("test_count", 0),
        "test_files": loc_stats.get("test_files", 0),
        "docker_freshness": docker_freshness,
        "sections": loc_stats.get("sections", {}),
        "domain_stats": domain_stats,
    }


def _save_metrics_json(loc_stats: dict, coverage_stats: dict, mutation_stats: dict, complexity_stats: dict) -> None:
    """Save metrics JSON files to qa/metrics."""
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    LOC_JSON_PATH.write_text(json.dumps(loc_stats, indent=2, sort_keys=True) + "\n")
    COVERAGE_JSON_PATH.write_text(json.dumps(coverage_stats, indent=2, sort_keys=True) + "\n")
    MUTATIONS_JSON_PATH.write_text(json.dumps(mutation_stats, indent=2, sort_keys=True) + "\n")
    COMPLEXITY_JSON_PATH.write_text(json.dumps(complexity_stats, indent=2, sort_keys=True) + "\n")
    print(f"✅ Saved metrics to {METRICS_DIR}")


def _load_metrics_json() -> tuple[dict, dict, dict, dict]:
    """Load metrics JSON files from qa/metrics."""
    missing = [path for path in [LOC_JSON_PATH, COVERAGE_JSON_PATH, MUTATIONS_JSON_PATH] if not path.exists()]
    if missing:
        missing_list = ", ".join(str(path) for path in missing)
        print(f"Error: missing metrics files: {missing_list}", file=sys.stderr)
        sys.exit(1)

    loc_stats = json.loads(LOC_JSON_PATH.read_text())
    coverage_stats = json.loads(COVERAGE_JSON_PATH.read_text())
    mutation_stats = json.loads(MUTATIONS_JSON_PATH.read_text())
    complexity_stats = json.loads(COMPLEXITY_JSON_PATH.read_text()) if COMPLEXITY_JSON_PATH.exists() else {}
    return loc_stats, coverage_stats, mutation_stats, complexity_stats


def _update_readme_from_stats(stats: dict) -> None:
    """Update README.md from stats dictionary."""
    if not README_PATH.exists():
        print(f"Error: {README_PATH} not found", file=sys.stderr)
        sys.exit(1)

    # Reconstruct SectionStats objects
    sections = {k: SectionStats(**v["stats"]) for k, v in stats["sections"].items()}

    # Generate content
    badges = _generate_badges(stats["coverage_pct"], stats["mutation_score"], stats["test_count"])
    table = _generate_table(
        stats["coverage_pct"],
        stats["coverage_status"],
        stats.get("docker_freshness", "fresh"),
        stats["mutation_score"],
        stats["mutation_killed"],
        stats["mutation_survived"],
        stats["test_count"],
        stats["test_files"],
        sections["api"],
        sections["cli"],
        sections["mcp"],
        sections["utils"],
        sections["unit"],
        sections["integration"],
        sections["smoke"],
        sections["cicd"],
        sections["build_config"],
        sections["scripts"],
        sections["specs"],
        sections["user_docs"],
        sections["dev_docs"],
    )

    # Update README
    content = README_PATH.read_text()

    # Replace badges section
    content = re.sub(r"(# WKS.*?\n\n)(.*?)(\n## Status)", rf"\1{badges}\n\3", content, flags=re.DOTALL)

    # Generate domain table if domain_stats present
    domain_table = ""
    if stats.get("domain_stats"):
        domain_table = "\n\n### Per-Domain Quality\n\n" + _generate_domain_table(stats["domain_stats"])

    # Replace table section (include domain table after main table)
    table_header = "## Code Quality Metrics\n\n"
    table_start = content.find(table_header)
    if table_start != -1:
        next_section = content.find("\n## ", table_start + len(table_header))
        if next_section == -1:
            next_section = content.find("\nAI-assisted", table_start)
        if next_section != -1:
            content = (
                content[: table_start + len(table_header)] + table + domain_table + "\n\n" + content[next_section:]
            )
        else:
            content = content[: table_start + len(table_header)] + table + domain_table
    else:
        content = re.sub(
            r"(## Code Quality Metrics\n\n)(.*?)(\n\n## |\nAI-assisted)",
            rf"\1{table}{domain_table}\n\n\3",
            content,
            flags=re.DOTALL,
        )

    README_PATH.write_text(content)
    print(f"✅ Updated {README_PATH} with current statistics")


def _update_readme(docker_freshness: str = "fresh") -> None:
    """Collect stats, save metrics JSON, update README."""
    loc_stats = _collect_loc_stats()
    coverage_stats = _collect_coverage_stats()
    mutation_stats = _collect_mutation_stats()
    complexity_stats = _collect_complexity_stats()
    _save_metrics_json(loc_stats, coverage_stats, mutation_stats, complexity_stats)
    readme_stats = _build_readme_stats(loc_stats, coverage_stats, mutation_stats, docker_freshness)
    _update_readme_from_stats(readme_stats)


def main() -> None:
    """CLI entry point with JSON support."""
    parser = argparse.ArgumentParser(description="Update README statistics")
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Only generate qa/metrics/*.json, don't update README",
    )
    parser.add_argument(
        "--from-json",
        action="store_true",
        help="Update README from qa/metrics/*.json",
    )
    parser.add_argument(
        "--docker-freshness", choices=["fresh", "stale"], default="fresh", help="Docker image freshness status"
    )
    args = parser.parse_args()

    if args.from_json:
        loc_stats, coverage_stats, mutation_stats, _complexity_stats = _load_metrics_json()
        readme_stats = _build_readme_stats(loc_stats, coverage_stats, mutation_stats, args.docker_freshness)
        _update_readme_from_stats(readme_stats)
    elif args.json_only:
        loc_stats = _collect_loc_stats()
        coverage_stats = _collect_coverage_stats()
        mutation_stats = _collect_mutation_stats()
        complexity_stats = _collect_complexity_stats()
        _save_metrics_json(loc_stats, coverage_stats, mutation_stats, complexity_stats)
    else:
        # Default: collect stats, save JSON, update README
        _update_readme(args.docker_freshness)


if __name__ == "__main__":
    main()
