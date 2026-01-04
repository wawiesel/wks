"""Library for generating stats tables and markdown."""

import sys
from dataclasses import dataclass

try:
    from tabulate import tabulate  # type: ignore[import-untyped]
except ImportError:
    print("Error: tabulate is required. Install with: pip install tabulate", file=sys.stderr)
    sys.exit(1)


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


def _create_table(headers: list[str], rows: list[list[str]], num_numeric_cols: int) -> str:
    """Create a markdown table with proper alignment."""
    # Build colalign: first column left, rest right
    colalign = ["left"] + ["right"] * num_numeric_cols
    table = tabulate(rows, headers=headers, tablefmt="github", colalign=colalign)
    return _fix_separator_alignment(table, num_numeric_cols)


def _format_row(label: str, stats: "SectionStats", pct: str) -> list[str]:
    """Format a statistics row."""
    return [f"**{label}**", f"{stats.files:,}", f"{stats.loc:,}", f"{stats.chars:,}", f"{stats.tokens:,}", pct]


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


def generate_domain_table(domain_stats: dict) -> str:
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


def generate_badges_md(stats: dict) -> str:
    """Generate badges markdown from stats dict."""
    return _generate_badges(
        stats.get("coverage_pct", 0.0), stats.get("mutation_score", 0.0), stats.get("test_count", 0)
    )


def generate_full_report(stats: dict) -> str:
    """Generate statistics table markdown from stats dict."""
    # Extract values
    coverage_pct = stats.get("coverage_pct", 0.0)
    coverage_status = stats.get("coverage_status", "")
    docker_freshness = stats.get("docker_freshness", "fresh")
    mutation_score = stats.get("mutation_score", 0.0)
    test_count = stats.get("test_count", 0)
    test_files = stats.get("test_files", 0)

    sections = {k: SectionStats(**v) if isinstance(v, dict) else v for k, v in stats.get("sections", {}).items()}

    mutation_status = "✅ Pass" if mutation_score >= 90.0 else "⚠️ Below Target"
    freshness_status = "✅ Pass" if docker_freshness == "fresh" else "⚠️ Updates Available"

    # Helper for token calculation
    def get_stats(key: str) -> SectionStats:
        return sections.get(key, SectionStats(0, 0, 0, 0))

    api_stats = get_stats("api")
    cli_stats = get_stats("cli")
    mcp_stats = get_stats("mcp")
    utils_stats = get_stats("utils")

    unit_test_stats = get_stats("unit")
    integration_test_stats = get_stats("integration")
    smoke_test_stats = get_stats("smoke")

    cicd_stats = get_stats("cicd")
    build_config_stats = get_stats("build_config")
    scripts_stats = get_stats("scripts")

    specs_stats = get_stats("specs")
    user_docs_stats = get_stats("user_docs")
    dev_docs_stats = get_stats("dev_docs")

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
                freshness_status,
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
