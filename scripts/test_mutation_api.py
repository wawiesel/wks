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


def _log(msg: str) -> None:
    """Write message to stdout buffer to ensure ordering with mutmut output."""
    sys.stdout.buffer.write(f"{msg}\n".encode())
    sys.stdout.buffer.flush()


def _print_disk_usage(label: str) -> None:
    """Print disk usage for debugging CI space issues."""
    output = []
    output.append(f"\n=== Disk Usage ({label}) ===")

    # Root partition free space
    try:
        statvfs = os.statvfs("/")
        free_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
        output.append(f"  Root partition: {free_gb:.1f} GB free")
    except OSError:
        output.append("  Root partition: (unavailable)")

    # Key paths to check (files and directories)
    paths_to_check = [
        REPO_ROOT / "mutants",
        REPO_ROOT / ".pytest_cache",
        REPO_ROOT / "coverage.xml",
        Path("/tmp"),
        REPO_ROOT / "tmp",
    ]

    for p in paths_to_check:
        try:
            if not p.exists():
                output.append(f"  {p}: (not found)")
                continue
            result = subprocess.run(
                ["du", "-sh", str(p)],
                capture_output=True,
                text=True,
                check=False,
            )
            size = result.stdout.split()[0] if result.stdout else "?"
            output.append(f"  {p}: {size}")
        except Exception:
            output.append(f"  {p}: (error)")

    # Show breakdown of /tmp and workspace tmp contents
    for tdir in [Path("/tmp"), REPO_ROOT / "tmp"]:
        if tdir.exists():
            try:
                result = subprocess.run(
                    ["du", "-sh", "--max-depth=1", str(tdir)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.stdout:
                    lines = result.stdout.strip().split("\n")
                    output.append(f"  {tdir} breakdown:")
                    # Sort by size (largest first) and show top 5
                    for line in sorted(lines, key=lambda x: x.split()[0], reverse=True)[:5]:
                        output.append(f"    {line}")
            except Exception:
                pass

    _log("\n".join(output))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("domain", help="Domain to mutate")
    args = parser.parse_args()

    domain = args.domain
    domain_path = f"wks/api/{domain}"
    stats_file = REPO_ROOT / f"mutation_stats_{domain}.json"
    setup_cfg = REPO_ROOT / "setup.cfg"
    mutants_dir = REPO_ROOT / "mutants"

    _log(f">>> Mutating {domain_path}...")

    # Isolate TMPDIR to workspace
    ws_tmp = REPO_ROOT / "tmp"
    ws_tmp.mkdir(exist_ok=True)
    os.environ["TMPDIR"] = str(ws_tmp)

    # Stable pytest btemp to prevent accumulation (re-use same dir)
    pytest_btemp = ws_tmp / "pytest"
    pytest_btemp.mkdir(exist_ok=True)

    # Print disk usage at start
    _print_disk_usage(f"before {domain}")

    # Clear pytest temp directories once at start (clean slate)
    for tdir in [Path("/tmp"), ws_tmp]:
        if tdir.exists():
            for item in tdir.glob("pytest-of-*"):
                try:
                    shutil.rmtree(item)
                    _log(f"  Cleared {item}")
                except (PermissionError, OSError):
                    pass
    if pytest_btemp.exists():
        shutil.rmtree(pytest_btemp)
        pytest_btemp.mkdir()

    # Clear artifacts
    if mutants_dir.exists():
        shutil.rmtree(mutants_dir) if mutants_dir.is_dir() else mutants_dir.unlink()

    # Inline Config Patching
    if not setup_cfg.exists():
        _log("Error: setup.cfg not found")
        sys.exit(1)

    original_cfg = setup_cfg.read_text()

    if "[mutmut]" not in original_cfg:
        _log("Error: mutmut directive not found in setup.cfg")
        sys.exit(1)

    # Patch paths_to_mutate and runner
    # We force --basetemp to prevent the 63MB-per-mutant accumulation
    # Note: mutmut 3.0+ uses 'runner' config. Default is 'python3 -m pytest -x --nf'
    patched_cfg = re.sub(r"paths_to_mutate\s*=.*", f"paths_to_mutate={domain_path}", original_cfg, flags=re.MULTILINE)
    runner_line = f"runner = python3 -m pytest -x --nf --basetemp={pytest_btemp}"
    if "runner =" in patched_cfg:
        patched_cfg = re.sub(r"runner\s*=.*", runner_line, patched_cfg, flags=re.MULTILINE)
    else:
        patched_cfg = patched_cfg.replace("[mutmut]", f"[mutmut]\n{runner_line}")

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
            _log("Could not find mutmut. Did you activate the virtual environment?")
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
            _log(f"mutmut run failed with return code {p.returncode}!")

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
        _log(f"Stats: Killed={killed}, Survived={survived}")

        # Output per-domain stats file
        stats = {"domain": domain, "killed": killed, "survived": survived}
        stats_file.write_text(json.dumps(stats))
        setup_cfg.write_text(original_cfg)

    finally:
        setup_cfg.write_text(original_cfg)


if __name__ == "__main__":
    main()
