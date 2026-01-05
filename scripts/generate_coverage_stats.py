#!/usr/bin/env python3
"""Generate Code Coverage statistics (coverage.json)."""

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def _get_code_coverage() -> float:
    """Get code coverage percentage."""
    coverage_xml = REPO_ROOT / "coverage.xml"
    if coverage_xml.exists():
        try:
            import xml.etree.ElementTree as ET

            # Root element has line-rate attribute
            line_rate = float(ET.parse(coverage_xml).getroot().get("line-rate", 0))
            return round(line_rate * 100, 1)
        except Exception:
            pass

    # Fallback to coverage command if no XML (but usually XML is what we parse)
    rc, output = _run_cmd([sys.executable, "-m", "coverage", "report", "--format=total"])
    if rc == 0:
        for line in output.splitlines():
            if "TOTAL" in line.upper():
                match = re.search(r"(\d+(?:\.\d+)?)%", line)
                if match:
                    return float(match.group(1))
    return 0.0


def main():
    pct = _get_code_coverage()
    domains = _get_domain_coverage()

    stats = {"coverage_pct": pct, "domains": domains}

    metrics_dir = REPO_ROOT / "qa" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    (metrics_dir / "coverage.json").write_text(json.dumps(stats, indent=2, sort_keys=True) + "\n")
    print(f"✅ Generated {metrics_dir}/coverage.json")


if __name__ == "__main__":
    main()
