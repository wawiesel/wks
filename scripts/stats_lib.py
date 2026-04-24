from dataclasses import dataclass


@dataclass(slots=True)
class SectionStats:
    files: int
    loc: int
    chars: int
    tokens: int

    def __add__(self, other: "SectionStats") -> "SectionStats":
        return SectionStats(
            files=self.files + other.files,
            loc=self.loc + other.loc,
            chars=self.chars + other.chars,
            tokens=self.tokens + other.tokens,
        )


def _badge_color(value: float, *, yellow_at: float, green_at: float) -> str:
    if value >= green_at:
        return "brightgreen"
    if value >= yellow_at:
        return "yellow"
    return "red"


def _generate_badges(coverage_pct: float, mutation_score: float, test_count: int, traceability_pct: float) -> str:
    coverage_color = _badge_color(coverage_pct, yellow_at=80.0, green_at=100.0)
    mutation_color = _badge_color(mutation_score, yellow_at=80.0, green_at=90.0)
    traceability_color = _badge_color(traceability_pct, yellow_at=80.0, green_at=100.0)
    return "\n".join(
        [
            f"![Coverage](https://img.shields.io/badge/coverage-{coverage_pct}%25-{coverage_color})",
            f"![Mutation Score](https://img.shields.io/badge/mutation-{mutation_score}%25-{mutation_color})",
            f"![Traceability](https://img.shields.io/badge/traceability-{traceability_pct}%25-{traceability_color})",
            f"![Tests](https://img.shields.io/badge/tests-{test_count}_passing-brightgreen)",
            "![Python](https://img.shields.io/badge/python-3.10+-blue)",
            "![Status](https://img.shields.io/badge/status-alpha-orange)",
            "![Docker Freshness](https://github.com/wawiesel/wks/actions/workflows/check-image-freshness.yml/badge.svg)",
        ]
    )


def generate_badges_md(stats: dict) -> str:
    return _generate_badges(
        stats.get("coverage_pct", 0.0),
        stats.get("mutation_score", 0.0),
        stats.get("test_count", 0),
        stats.get("traceability_pct", 0.0),
    )


def _sections_from_stats(stats: dict) -> dict[str, SectionStats]:
    raw_sections = stats.get("sections", {})
    return {name: SectionStats(**section) for name, section in raw_sections.items() if isinstance(section, dict)}


def _total(sections: dict[str, SectionStats], *names: str) -> SectionStats:
    total = SectionStats(0, 0, 0, 0)
    for name in names:
        total += sections.get(name, SectionStats(0, 0, 0, 0))
    return total


def generate_metrics_report(stats: dict) -> str:
    sections = _sections_from_stats(stats)
    code = _total(sections, "api", "cli", "mcp", "utils", "services", "rest")
    tests = _total(sections, "unit", "integration", "smoke")
    docs = _total(sections, "specs", "user_docs", "dev_docs")
    infra = _total(sections, "cicd", "build_config", "scripts")
    docker_freshness = stats.get("docker_freshness", "unknown")

    rows = [
        ("Coverage", f"{stats.get('coverage_pct', 0.0)}%"),
        ("Mutation kill", f"{stats.get('mutation_score', 0.0)}%"),
        ("Traceability", f"{stats.get('traceability_pct', 0.0)}%"),
        ("Tests", f"{stats.get('test_count', 0):,}"),
        ("Test files", f"{stats.get('test_files', 0):,}"),
        ("Docker freshness", docker_freshness),
        ("Code LOC", f"{code.loc:,}"),
        ("Test LOC", f"{tests.loc:,}"),
        ("Doc LOC", f"{docs.loc:,}"),
        ("Infra LOC", f"{infra.loc:,}"),
    ]
    lines = ["| Metric | Value |", "| --- | ---: |"]
    lines.extend(f"| {label} | {value} |" for label, value in rows)
    return "\n".join(lines)
