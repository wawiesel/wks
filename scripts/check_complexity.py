#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()


def main():
    args = sys.argv[1:]
    console.print("[bold blue]Running Lizard Complexity Analysis...[/bold blue]")

    bin_dir = Path(sys.executable).parent
    lizard_cmd = "lizard"
    if (bin_dir / "lizard").exists():
        lizard_cmd = str(bin_dir / "lizard")

    cmd = [lizard_cmd, "-l", "python", "-C", "10", "-L", "100"]
    if args:
        cmd.extend(args)
    else:
        cmd.append("wks")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        has_no_violations = "No thresholds exceeded" in result.stdout

        violation_lines = []
        file_nloc_violations = []

        if not has_no_violations:
            in_violations_section = False
            for line in result.stdout.splitlines():
                if "!!!! Warnings" in line:
                    in_violations_section = True
                    continue
                if in_violations_section and "====" in line:
                    break  # End of violations section
                if in_violations_section and line.strip() and not line.startswith(" "):
                    parts = line.split()
                    if len(parts) >= 5:
                        try:
                            int(parts[0])  # NLOC
                            int(parts[1])  # CCN
                            violation_lines.append(line)
                        except ValueError:
                            pass

        in_file_summary = False
        for line in result.stdout.splitlines():
            if "NLOC    Avg.NLOC  AvgCCN  Avg.token  function_cnt    file" in line:
                in_file_summary = True
                continue
            if in_file_summary:
                if line.strip().startswith("Total nloc") or line.strip().startswith("="):
                    break  # End of file summary section
                if line.strip() and not line.startswith("-") and not line.startswith("="):
                    parts = line.split()
                    if len(parts) >= 6:
                        try:
                            file_nloc = int(parts[0])  # First column is file NLOC
                            file_path = parts[-1]
                            if file_nloc > 500 and ("/" in file_path or file_path.endswith(".py")):
                                file_nloc_violations.append(f"File {file_path} has {file_nloc} lines (max 500)")
                        except (ValueError, IndexError):
                            pass

        if violation_lines or file_nloc_violations:
            console.print("[bold red]Complexity Violations Found:[/bold red]")
            if violation_lines:
                console.print("\nFunction-level violations:")
                for v in violation_lines:
                    console.print(f"  {v}")
            if file_nloc_violations:
                console.print("\nFile-level violations (NLOC > 500):")
                for v in file_nloc_violations:
                    console.print(f"  {v}")
            console.print("\nFull lizard output:")
            console.print(result.stdout)
            sys.exit(1)

        if result.returncode != 0 and result.stderr:
            console.print("[bold red]FAILED: Lizard execution error[/bold red]")
            console.print(result.stderr)
            sys.exit(result.returncode)

        _save_complexity_json(result.stdout)

        console.print("[bold green]PASSED: Lizard Complexity Analysis[/bold green]")

    except Exception as e:
        console.print(f"[bold red]Error running complexity check: {e}[/bold red]")
        sys.exit(1)


def _save_complexity_json(stdout: str) -> None:
    import json
    import re

    metrics = {"nloc": 0, "avg_nloc": 0.0, "avg_ccn": 0.0, "avg_token": 0.0, "function_count": 0}

    for line in stdout.splitlines():
        if line.strip().startswith("Total nloc"):
            m = re.search(r"Total nloc[:\s]+(\d+)", line, re.IGNORECASE)
            if m:
                metrics["nloc"] = int(m.group(1))

            m = re.search(r"Avg\.NLOC[:\s]+([\d\.]+)", line, re.IGNORECASE)
            if m:
                metrics["avg_nloc"] = float(m.group(1))

            m = re.search(r"AvgCCN[:\s]+([\d\.]+)", line, re.IGNORECASE)
            if m:
                metrics["avg_ccn"] = float(m.group(1))

            m = re.search(r"Avg\.token[:\s]+([\d\.]+)", line, re.IGNORECASE)
            if m:
                metrics["avg_token"] = float(m.group(1))

            m = re.search(r"fun(?:ction)?_cnt[:\s]+(\d+)", line, re.IGNORECASE)
            if m:
                metrics["function_count"] = int(m.group(1))

            break

    metrics_dir = Path(__file__).resolve().parents[1] / "qa" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "complexity.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
    console.print(f"[green]Saved complexity metrics to {metrics_dir}/complexity.json[/green]")


if __name__ == "__main__":
    main()
