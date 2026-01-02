import argparse
import json
import os
import pty
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _print_disk_usage(label: str) -> None:
    """Print disk usage for debugging CI space issues."""
    print(f"\n=== Disk Usage ({label}) ===")

    # Root partition free space
    try:
        statvfs = os.statvfs("/")
        free_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
        print(f"  Root partition: {free_gb:.1f} GB free")
    except OSError:
        print("  Root partition: (unavailable)")

    # Key paths to check (files and directories)
    paths_to_check = [
        REPO_ROOT / "mutants",
        REPO_ROOT / ".pytest_cache",
        REPO_ROOT / "coverage.xml",
        Path("/tmp"),
    ]

    for p in paths_to_check:
        try:
            if not p.exists():
                print(f"  {p}: (not found)")
                continue
            result = subprocess.run(
                ["du", "-sh", str(p)],
                capture_output=True,
                text=True,
                check=False,
            )
            size = result.stdout.split()[0] if result.stdout else "?"
            print(f"  {p}: {size}")
        except Exception:
            print(f"  {p}: (error)")
    print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("domain", help="Domain to mutate")
    parser.add_argument("--progress", action="store_true", help="Print verbose output")
    args = parser.parse_args()

    domain = args.domain
    domain_path = f"wks/api/{domain}"
    stats_file = REPO_ROOT / f"mutation_stats_{domain}.json"
    setup_cfg = REPO_ROOT / "setup.cfg"

    print(f">>> Mutating {domain_path}...")

    # Print disk usage at start
    _print_disk_usage(f"before {domain}")

    # Clear artifacts
    mutants_dir = REPO_ROOT / "mutants"
    if mutants_dir.exists():
        shutil.rmtree(mutants_dir) if mutants_dir.is_dir() else mutants_dir.unlink()

    # 4. Inline Config Patching
    if not setup_cfg.exists():
        print("Error: setup.cfg not found")
        sys.exit(1)

    original_cfg = setup_cfg.read_text()

    # Construct modified config content
    if "[mutmut]" not in original_cfg:
        print("Error: mutmut directive not found in setup.cfg")
        sys.exit(1)

    # regex replace the paths_to_mutate line
    patched_cfg = re.sub(r"paths_to_mutate\s*=.*", f"paths_to_mutate={domain_path}", original_cfg, flags=re.MULTILINE)

    try:
        with setup_cfg.open("w") as f:
            f.write(patched_cfg)

        # Run mutmut
        # Helper to find mutmut
        mutmut_bin = shutil.which("mutmut")
        if not mutmut_bin:
            # Check next to the python executable (if running from venv)
            candidate = Path(sys.executable).parent / "mutmut"
            if candidate.exists():
                mutmut_bin = str(candidate)

        if not mutmut_bin:
            print(
                "Could not find mutmut. Did you activate the virtual environment? . .venv/bin/activate", file=sys.stderr
            )
            sys.exit(1)

        if args.progress:
            # Use pty to trick mutmut into thinking it's running in a real terminal
            # This ensures it outputs \r for progress bars instead of newlines or buffering
            master_fd, slave_fd = pty.openpty()

            p = subprocess.Popen(
                [mutmut_bin, "run"],
                cwd=str(REPO_ROOT),
                stdout=slave_fd,
                stderr=slave_fd,
                text=False,
                bufsize=0,
            )
            os.close(slave_fd)

            captured_bytes = bytearray()
            try:
                while True:
                    try:
                        chunk = os.read(master_fd, 1024)
                    except OSError:
                        break
                    if not chunk:
                        break
                    captured_bytes.extend(chunk)
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
            finally:
                p.wait()
                os.close(master_fd)
            output = captured_bytes.decode("utf-8", errors="replace")
        else:
            # CI/Standard mode: Stream output directly for visibility
            # We still capture it to a file on failure
            mutants_dir.mkdir(exist_ok=True)
            mutmut_log = mutants_dir / "mutmut.stdout"
            with mutmut_log.open("wb") as f_log:
                p = subprocess.Popen(
                    [mutmut_bin, "run"],
                    cwd=str(REPO_ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )

                if p.stdout:
                    for b_line in p.stdout:
                        f_log.write(b_line)
                        sys.stdout.buffer.write(b_line)
                        sys.stdout.buffer.flush()
                p.wait()

            output = mutmut_log.read_text(errors="replace")

        if p.returncode != 0:
            print(f"mutmut run failed with return code {p.returncode}!")
            # Print last 20 lines if not already printed
            if not args.progress:
                print("... (see above for full logs)")
            else:
                print("\n".join(output.splitlines()[-20:]))

            # Write stderr note
            (mutants_dir / "mutmut.stderr").write_text("See mutmut.stdout (stderr merged)")
            print(f"Full output written to {mutants_dir}/mutmut.stdout")

        # Parse stats from 'mutmut results --all true' (reliable)
        # Usage verified by user: mutmut results --all true
        p_results = subprocess.run(
            [mutmut_bin, "results", "--all", "true"], cwd=str(REPO_ROOT), text=True, capture_output=True, check=False
        )

        killed = 0
        survived = 0

        for line in (p_results.stdout or "").splitlines():
            line = line.strip()
            if line.endswith(": killed"):
                killed += 1
            elif line.endswith(": survived"):
                survived += 1

        print(f"Stats: Killed={killed}, Survived={survived}")

        # Output per-domain stats file
        stats = {"domain": domain, "killed": killed, "survived": survived}
        stats_file.write_text(json.dumps(stats))
        setup_cfg.write_text(original_cfg)

        # Print disk usage after domain completes
        _print_disk_usage(f"after {domain}")

    finally:
        setup_cfg.write_text(original_cfg)


if __name__ == "__main__":
    main()
