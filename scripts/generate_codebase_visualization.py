#!/usr/bin/env python3

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError:
    print("Error: matplotlib is required for visualization. Install with: pip install matplotlib", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "docs" / "codebase_stats.png"


@dataclass
class SectionData:
    name: str
    files: int
    loc: int
    chars: int
    tokens: int
    category: str  # 'code', 'infrastructure', 'docs', 'tests'


def _load_stats_from_readme() -> dict[str, SectionData]:
    readme_path = REPO_ROOT / "README.md"
    if not readme_path.exists():
        print(f"Error: {readme_path} not found", file=sys.stderr)
        sys.exit(1)

    content = readme_path.read_text()
    sections: dict[str, SectionData] = {}

    code_table_pattern = r"\*\*(api|cli|mcp|utils)\*\*\s*\|\s*(\d+)\s*\|\s*([\d,]+)\s*\|\s*([\d,]+)\s*\|\s*([\d,]+)"
    for match in re.finditer(code_table_pattern, content):
        name, files, loc, chars, tokens = match.groups()
        sections[name] = SectionData(
            name=name.upper(),
            files=int(files),
            loc=int(loc.replace(",", "")),
            chars=int(chars.replace(",", "")),
            tokens=int(tokens.replace(",", "")),
            category="code",
        )

    additional_pattern = (
        r"\*\*(Infrastructure|Specifications|User Documentation|Developer Documentation|Tests)\*\*\s*"
        r"\|\s*(\d+)\s*\|\s*([\d,]+)\s*\|\s*([\d,]+)\s*\|\s*([\d,]+)"
    )
    category_map = {
        "Infrastructure": ("infrastructure", "infrastructure"),
        "Specifications": ("specs", "docs"),
        "User Documentation": ("user_docs", "docs"),
        "Developer Documentation": ("dev_docs", "docs"),
        "Tests": ("tests", "tests"),
    }

    for match in re.finditer(additional_pattern, content):
        full_name, files, loc, chars, tokens = match.groups()
        key, category = category_map.get(full_name, (full_name.lower().replace(" ", "_"), "other"))
        sections[key] = SectionData(
            name=full_name,
            files=int(files),
            loc=int(loc.replace(",", "")),
            chars=int(chars.replace(",", "")),
            tokens=int(tokens.replace(",", "")),
            category=category,
        )

    return sections


def _get_category_colors() -> dict[str, str]:
    return {
        "code": "#4A90E2",  # Blue
        "infrastructure": "#7B68EE",  # Medium slate blue
        "docs": "#50C878",  # Emerald green
        "tests": "#FF6B6B",  # Coral red
    }


def _create_pie_chart(ax: Any, category_totals: dict[str, int], category_colors: dict[str, str]) -> None:
    cat_names = list(category_totals.keys())
    cat_values = list(category_totals.values())
    cat_colors_list = [category_colors.get(cat, "#808080") for cat in cat_names]

    _wedges, _texts, _autotexts = ax.pie(
        cat_values,
        labels=cat_names,
        colors=cat_colors_list,
        autopct="%1.1f%%",
        startangle=90,
        textprops={"color": "white", "fontsize": 12, "fontweight": "bold"},
    )
    ax.set_title("Distribution by Category", color="white", fontsize=14, fontweight="bold", pad=20)


def _create_bar_chart(
    ax: Any,
    names: tuple[str, ...],
    values: tuple[int, ...],
    sections: dict[str, SectionData],
    colors: list[str],
    metric: str,
    total: int,
) -> None:
    metric_labels = {"chars": "Characters", "loc": "Lines of Code", "tokens": "Tokens", "files": "Files"}

    y_pos = np.arange(len(names))
    bars = ax.barh(
        y_pos, values, color=[colors[i] for i in range(len(names))], alpha=0.8, edgecolor="white", linewidth=1.5
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels([sections[name].name for name in names], color="white", fontsize=10)
    ax.set_xlabel(f"{metric_labels.get(metric, metric.title())}", color="white", fontsize=12, fontweight="bold")
    ax.set_title("All Sections Comparison", color="white", fontsize=14, fontweight="bold", pad=20)
    ax.tick_params(colors="white")
    ax.spines["bottom"].set_color("white")
    ax.spines["top"].set_color("white")
    ax.spines["right"].set_color("white")
    ax.spines["left"].set_color("white")
    ax.xaxis.label.set_color("white")

    for _i, (bar, val) in enumerate(zip(bars, values, strict=True)):
        width = bar.get_width()
        percentage = (val / total) * 100
        ax.text(
            width,
            bar.get_y() + bar.get_height() / 2,
            f"{val:,} ({percentage:.1f}%)",
            ha="left",
            va="center",
            color="white",
            fontsize=9,
            fontweight="bold",
        )


def _create_stacked_bar_chart(
    ax: Any,
    category_sections: dict[str, list[tuple[str, int]]],
    category_colors: dict[str, str],
    metric: str,
    total: int,
) -> None:
    metric_labels = {"chars": "Characters", "loc": "Lines of Code", "tokens": "Tokens", "files": "Files"}
    width = 0.6

    for cat in category_sections:
        cat_data = category_sections[cat]
        cat_data.sort(key=lambda x: x[1], reverse=True)  # Sort by value
        section_values = [x[1] for x in cat_data]

        ax.bar(
            cat,
            sum(section_values),
            width,
            label=cat.title(),
            color=category_colors.get(cat, "#808080"),
            alpha=0.8,
            edgecolor="white",
            linewidth=1.5,
        )

        if sum(section_values) > total * 0.05:  # Only label if > 5% of total
            ax.text(
                cat,
                sum(section_values) / 2,
                f"{sum(section_values):,}",
                ha="center",
                va="center",
                color="white",
                fontsize=10,
                fontweight="bold",
            )

    ax.set_ylabel(f"{metric_labels.get(metric, metric.title())}", color="white", fontsize=12, fontweight="bold")
    ax.set_title("Total by Category", color="white", fontsize=14, fontweight="bold", pad=20)
    ax.tick_params(colors="white")
    ax.spines["bottom"].set_color("white")
    ax.spines["top"].set_color("white")
    ax.spines["right"].set_color("white")
    ax.spines["left"].set_color("white")
    ax.yaxis.label.set_color("white")


def _create_treemap(sections: dict[str, SectionData], metric: str = "chars") -> None:
    data = [(name, getattr(stats, metric)) for name, stats in sections.items() if getattr(stats, metric) > 0]
    data.sort(key=lambda x: x[1], reverse=True)

    if not data:
        print("No data to visualize", file=sys.stderr)
        return

    names, values = zip(*data, strict=True)
    total = sum(values)

    category_colors = _get_category_colors()

    colors = []
    for name in names:
        section = sections[name]
        base_color = category_colors.get(section.category, "#808080")
        colors.append(base_color)

    fig = plt.figure(figsize=(18, 12), facecolor="#1e1e1e")
    gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)

    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_facecolor("#1e1e1e")

    category_totals: dict[str, int] = {}
    for name in names:
        section = sections[name]
        cat = section.category
        category_totals[cat] = category_totals.get(cat, 0) + getattr(section, metric)

    _create_pie_chart(ax1, category_totals, category_colors)

    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_facecolor("#1e1e1e")
    _create_bar_chart(ax2, names, values, sections, colors, metric, total)

    ax3 = fig.add_subplot(gs[1, :])
    ax3.set_facecolor("#1e1e1e")

    category_sections: dict[str, list[tuple[str, int]]] = {}
    for name in names:
        section = sections[name]
        cat = section.category
        if cat not in category_sections:
            category_sections[cat] = []
        category_sections[cat].append((section.name, getattr(section, metric)))

    _create_stacked_bar_chart(ax3, category_sections, category_colors, metric, total)

    for ax in [ax1, ax2, ax3]:
        ax.tick_params(colors="white")

    metric_labels = {"chars": "Characters", "loc": "Lines of Code", "tokens": "Tokens", "files": "Files"}
    title = f"Codebase Statistics - {metric_labels.get(metric, metric.title())}"
    fig.suptitle(title, fontsize=22, fontweight="bold", color="white", y=0.98)

    plt.tight_layout(rect=(0, 0, 1, 0.96))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_PATH, dpi=300, facecolor="#1e1e1e", bbox_inches="tight")
    print(f"✅ Generated visualization: {OUTPUT_PATH}")


def main() -> None:
    sections = _load_stats_from_readme()

    if not sections:
        print("Error: Could not load statistics from README.md", file=sys.stderr)
        sys.exit(1)

    _create_treemap(sections, metric="chars")

    print(f"📊 Visualization saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
