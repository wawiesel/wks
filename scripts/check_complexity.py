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

        # Check for violations in output since lizard return code might be 0
        violations = [line for line in result.stdout.splitlines() if "!!!!" in line]

        if violations:
            console.print("[bold red]Complexity Violations Found:[/bold red]")
            for v in violations:
                console.print(v)
            # Also print the summary table which is usually at the end
            console.print(
                result.stdout.split("================================================")[1]
                if "=" in result.stdout
                else ""
            )
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
