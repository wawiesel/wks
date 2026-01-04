#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()


def main():
    args = sys.argv[1:]
    console.print("[bold blue]Running Lizard Complexity Analysis...[/bold blue]")

    # Resolve tool path
    bin_dir = Path(sys.executable).parent
    lizard_cmd = "lizard"
    if (bin_dir / "lizard").exists():
        lizard_cmd = str(bin_dir / "lizard")

    # CCN <= 10, NLOC <= 100 per function
    # Max file NLOC <= 500 (checked separately)
    cmd = [lizard_cmd, "-l", "python", "-C", "10", "-L", "100"]
    if args:
        cmd.extend(args)
    else:
        cmd.append("wks")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Check for actual violations - look for "No thresholds exceeded" message
        # If that message is present, there are no violations
        has_no_violations = "No thresholds exceeded" in result.stdout

        # Check for violations in output since lizard return code might be 0
        # The "!!!! Warnings" header is always present, so we need to check for actual violations
        violation_lines = []
        file_nloc_violations = []

        if not has_no_violations:
            # Look for violation lines (they have numbers in specific columns after the header)
            in_violations_section = False
            for line in result.stdout.splitlines():
                if "!!!! Warnings" in line:
                    in_violations_section = True
                    continue
                if in_violations_section and "====" in line:
                    break  # End of violations section
                if in_violations_section and line.strip() and not line.startswith(" "):
                    # Check if line looks like a violation (has numbers in columns)
                    parts = line.split()
                    if len(parts) >= 5:
                        try:
                            # Try to parse numbers - if successful, it's a violation line
                            int(parts[0])  # NLOC
                            int(parts[1])  # CCN
                            violation_lines.append(line)
                        except ValueError:
                            pass

        # Check for file-level NLOC violations (max 500 lines per file)
        # Lizard outputs file summaries after "NLOC    Avg.NLOC  AvgCCN  Avg.token  function_cnt    file"
        # Format: "    NLOC    Avg.NLOC  AvgCCN  Avg.token  function_cnt    file_path"
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
                    # File summary lines have 6 columns: NLOC, Avg.NLOC, AvgCCN, Avg.token, function_cnt, file_path
                    if len(parts) >= 6:
                        try:
                            file_nloc = int(parts[0])  # First column is file NLOC
                            # Check if last part looks like a file path (contains '/' or ends with '.py')
                            file_path = parts[-1]
                            if file_nloc > 500 and ("/" in file_path or file_path.endswith(".py")):
                                file_nloc_violations.append(f"File {file_path} has {file_nloc} lines (max 500)")
                        except (ValueError, IndexError):
                            pass

        # Lizard returns exit code 1 when violations are found, which is expected
        # Only treat non-zero exit codes as errors if we didn't find violations in output
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

        # If no violations found but exit code is non-zero, it might be an error
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
    """Parse lizard output and save complexity.json."""
    import json
    import re

    # Parse Total line: "Total nloc   Avg.NLOC  AvgCCN  Avg.token   function_cnt"
    # Example format: "Total nloc: 11661   Avg.NLOC: 9.6   AvgCCN: 2.3   Avg.token: 62.9   function_cnt: 1209"
    metrics = {"nloc": 0, "avg_nloc": 0.0, "avg_ccn": 0.0, "avg_token": 0.0, "function_count": 0}

    for line in stdout.splitlines():
        if line.strip().startswith("Total nloc"):
            # Clean up the line: remove labels, keep numbers
            # "Total nloc: 123  Avg.NLOC: 4.5 ..." -> ["123", "4.5", ...]
            # Using regex to find key-value pairs

            # nloc
            m = re.search(r"Total nloc[:\s]+(\d+)", line, re.IGNORECASE)
            if m:
                metrics["nloc"] = int(m.group(1))

            # Avg NLOC
            m = re.search(r"Avg\.NLOC[:\s]+([\d\.]+)", line, re.IGNORECASE)
            if m:
                metrics["avg_nloc"] = float(m.group(1))

            # Avg CCN
            m = re.search(r"AvgCCN[:\s]+([\d\.]+)", line, re.IGNORECASE)
            if m:
                metrics["avg_ccn"] = float(m.group(1))

            # Avg token
            m = re.search(r"Avg\.token[:\s]+([\d\.]+)", line, re.IGNORECASE)
            if m:
                metrics["avg_token"] = float(m.group(1))

            # Function count
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
