"""
Orchestrator for mutation testing with strict resource management.

This script prevents temporary directory accumulation from exceeding disk
limits during large mutation testing runs.

    1.  DO NOT remove PYTEST_ADDOPTS enforcement. Environment variables are
        required to ensure --basetemp is respected across all testing phases.
    2.  DO NOT move runner configuration to config files; mutmut discovery
        logic requires these arguments to be passed at the runner level.
    3.  DO NOT use print() for logic logs. Use _log() to ensure binary-level
        synchronization with terminal-aware progress bars.
    4.  DO NOT enable parallel execution (-j) until concurrency hazards in
        shared test fixtures (e.g. database port collisions) are resolved.

Usage:
    python scripts/test_mutation_api.py <domain>
"""
import argparse
import json
import os
import pty
import re
import shutil
import subprocess
import sys
from pathlib import Path
import time

REPO_ROOT = Path(__file__).resolve().parents[1]


def _log(msg: str) -> None:
    """Write message to stdout buffer to ensure ordering with mutmut output."""
    sys.stdout.buffer.write(f"{msg}\n".encode())
    sys.stdout.buffer.flush()


def _get_disk_space() -> str:
    """Return available disk space as string (e.g. '5.4 GB') or 'unavailable'."""
    try:
        statvfs = os.statvfs("/")
        free_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
        return f"{free_gb:.1f} GB"
    except OSError:
        return "unavailable"


def _get_mutation_stats(mutmut_bin: str) -> tuple[int, int]:
    """Parse stats from 'mutmut results --all true'."""
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

    return killed, survived


def _process_pty_output(master_fd: int, log_interval: int | None) -> None:
    """Read PTY output line-by-line and throttle progress updates."""
    buf = b""
    last_log_time = 0.0
    skipped_count = 0
    suppress_next_newline = False
    last_skipped_line = None

    while True:
        try:
            chunk = os.read(master_fd, 4096)
        except OSError:
            break

        if not chunk:
            break

        buf += chunk

        while True:
            # Detect delimiters
            idx_n = buf.find(b"\n")
            idx_r = buf.find(b"\r")

            # Case: No throttling (print everything immediately)
            if log_interval is None:
                if buf:
                    sys.stdout.buffer.write(buf)
                    sys.stdout.buffer.flush()
                    buf = b""
                break

            # No delimiters found, wait for more data
            if idx_n == -1 and idx_r == -1:
                break

            # Case 1: Newline found first (Standard Log)
            if idx_n != -1 and (idx_r == -1 or idx_n < idx_r):
                # Check for "orphaned" newline from previous \r
                if suppress_next_newline and idx_n == 0:
                    buf = buf[1:]  # Consume \n
                    suppress_next_newline = False
                    continue

                line = buf[: idx_n + 1]
                buf = buf[idx_n + 1 :]
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
                
                # Reset counter on regular newlines as requested
                skipped_count = 0
                suppress_next_newline = False
                last_skipped_line = None

            # Case 2: Carriage Return found first (Progress Log)
            elif idx_r != -1:
                line = buf[: idx_r + 1]
                buf = buf[idx_r + 1 :]
                
                # Check if it's actually \r\n (Standard Log disguised)
                consumed_newline = False
                if buf.startswith(b"\n"):
                    # It's \r\n, treat as standard newline
                    line += b"\n"
                    buf = buf[1:]
                    sys.stdout.buffer.write(line)
                    sys.stdout.buffer.flush()
                    skipped_count = 0
                    suppress_next_newline = False
                    last_skipped_line = None
                    continue

                # It is a pure \r (Progress update)
                skipped_count += 1
                last_skipped_line = line
                suppress_next_newline = True # Expect a newline eventually that matches this partial line

                now = time.time()
                if now - last_log_time >= log_interval:
                    prefix = f"[{skipped_count}]".encode() if skipped_count > 1 else b""
                    # Replace \r with \n to commit this line to the log
                    printed_line = line.replace(b"\r", b"\n")
                    sys.stdout.buffer.write(prefix + printed_line)
                    sys.stdout.buffer.flush()
                    
                    last_log_time = now
                    # Reset skipped_count since we output the state that superseded previous ones
                    skipped_count = 0
                else:
                    # Do not reset skipped_count, keep accumulating
                    pass

    # Flush remaining buffer
    if buf:
        sys.stdout.buffer.write(buf)
        sys.stdout.buffer.flush()

    # Flush last skipped progress line if it wasn't printed
    if skipped_count > 0 and last_skipped_line:
        prefix = f"[{skipped_count}]".encode()
        printed_line = last_skipped_line.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        sys.stdout.buffer.write(prefix + printed_line)
        sys.stdout.buffer.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("domain", help="Domain to mutate")
    parser.add_argument("--log-interval", type=int, default=None, help="Throttle progress logs to every N seconds")
    args = parser.parse_args()

    domain = args.domain
    domain_path = f"wks/api/{domain}"
    stats_file = REPO_ROOT / f"mutation_stats_{domain}.json"
    setup_cfg = REPO_ROOT / "setup.cfg"
    mutants_dir = REPO_ROOT / "mutants"

    disk_msg = _get_disk_space()

    _log(f">>> Mutating {domain_path} (available disk: {disk_msg})...")

    # Isolate TMPDIR to workspace
    ws_tmp = REPO_ROOT / "tmp"
    ws_tmp.mkdir(exist_ok=True)
    os.environ["TMPDIR"] = str(ws_tmp)

    # Stable pytest btemp to prevent accumulation (re-use same dir)
    pytest_btemp = ws_tmp / "pytest"

    # Start with a clean slate
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

    # Patch paths_to_mutate.
    patched_cfg = re.sub(r"paths_to_mutate\s*=.*", f"paths_to_mutate={domain_path}", original_cfg, flags=re.MULTILINE)
    if not patched_cfg:
        _log("Error: failed to patch paths_to_mutate in setup.cfg")
        sys.exit(1)

    # Enforce --basetemp via environment variable.
    # This is the most robust way to ensure directory reuse across all pytest calls
    # (including stats collection and mutation runs) without complex setup.cfg patching.
    os.environ["PYTEST_ADDOPTS"] = f"--basetemp={pytest_btemp}"

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
            _process_pty_output(master_fd, args.log_interval)
        finally:
            p.wait()
            os.close(master_fd)

        if p.returncode != 0:
            _log(f"mutmut run failed with return code {p.returncode}!")
            sys.exit(1)

        # Parse stats from 'mutmut results --all true' (reliable)
        killed, survived = _get_mutation_stats(mutmut_bin)

        # Print disk usage after domain completes, then stats
        _log(f">>> Finished {domain_path} (available disk: {_get_disk_space()})")
        _log(f"{domain_path} mutants: Killed={killed}, Survived={survived}")

        # Output per-domain stats file
        stats = {"domain": domain, "killed": killed, "survived": survived}
        stats_file.write_text(json.dumps(stats))
        setup_cfg.write_text(original_cfg)

    finally:
        setup_cfg.write_text(original_cfg)


if __name__ == "__main__":
    main()
