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
    args = parser.parse_args()

    domain = args.domain
    domain_path = f"wks/api/{domain}"
    stats_file = REPO_ROOT / f"mutation_stats_{domain}.json"
    setup_cfg = REPO_ROOT / "setup.cfg"
    mutants_dir = REPO_ROOT / "mutants"

    print(f">>> Mutating {domain_path}...")

    # Print disk usage at start
    _print_disk_usage(f"before {domain}")

    # Clear pytest temp directories to prevent accumulation (grows ~1GB per domain)
    tmp_dir = Path("/tmp")
    if tmp_dir.exists():
        for item in tmp_dir.glob("pytest-of-*"):
            try:
                shutil.rmtree(item)
                print(f"  Cleared {item}")
            except (PermissionError, OSError):
                pass

    # Clear artifacts
    if mutants_dir.exists():
        shutil.rmtree(mutants_dir) if mutants_dir.is_dir() else mutants_dir.unlink()

    # Inline Config Patching
    if not setup_cfg.exists():
        print("Error: setup.cfg not found")
        sys.exit(1)

    original_cfg = setup_cfg.read_text()

    if "[mutmut]" not in original_cfg:
        print("Error: mutmut directive not found in setup.cfg")
        sys.exit(1)

    # regex replace the paths_to_mutate line
    patched_cfg = re.sub(r"paths_to_mutate\s*=.*", f"paths_to_mutate={domain_path}", original_cfg, flags=re.MULTILINE)

    try:
        with setup_cfg.open("w") as f:
            f.write(patched_cfg)

        # Find mutmut executable
        mutmut_bin = shutil.which("mutmut")
        if not mutmut_bin:
            candidate = Path(sys.executable).parent / "mutmut"
            if candidate.exists():
                mutmut_bin = str(candidate)

        if not mutmut_bin:
            print("Could not find mutmut. Did you activate the virtual environment?", file=sys.stderr)
            sys.exit(1)

        # Run mutmut with PTY (preserves progress bars locally, shows as lines in CI)
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

        try:
            while True:
                try:
                    chunk = os.read(master_fd, 1024)
                except OSError:
                    break
                if not chunk:
                    break
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
        finally:
            p.wait()
            os.close(master_fd)

        if p.returncode != 0:
            print(f"mutmut run failed with return code {p.returncode}!")

        # Parse stats from 'mutmut results --all true' (reliable)
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

        # Print disk usage after domain completes, then stats
        _print_disk_usage(f"after {domain}")
        print(f"Stats: Killed={killed}, Survived={survived}")

        # Output per-domain stats file
        stats = {"domain": domain, "killed": killed, "survived": survived}
        stats_file.write_text(json.dumps(stats))
        setup_cfg.write_text(original_cfg)

    finally:
        setup_cfg.write_text(original_cfg)


if __name__ == "__main__":
    main()
