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

    # CCN <= 10, NLOC <= 100
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
        if not has_no_violations:
            # Look for violation lines (they have numbers in specific columns after the header)
            violation_lines = []
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

            if violation_lines:
                console.print("[bold red]Complexity Violations Found:[/bold red]")
                console.print(result.stdout)
                sys.exit(1)
        elif result.returncode != 0:
            console.print("[bold red]FAILED: Lizard execution error[/bold red]")
            console.print(result.stderr)
            sys.exit(result.returncode)
        else:
            console.print("[bold green]PASSED: Lizard Complexity Analysis[/bold green]")

    except Exception as e:
        console.print(f"[bold red]Error running complexity check: {e}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
