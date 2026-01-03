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
import time
from pathlib import Path

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
    """
    Read PTY output and optionally throttle progress updates using TTY emulation.

    TTY Emulation Model
    -------------------
    Internally maintain a "current line" buffer like a real terminal:

    - `\\r` (carriage return): "Replace" the current line with new content.
      Increment a replacement counter RR.
    - `\\n` (newline): "Commit" the current line to output. Reset RR to 0.

    Throttled Output
    ----------------
    When log_interval is set (not None):

    - Don't output on every `\\r`. Silently accumulate replacements.
    - Every N seconds (or on `\\n`), output the current line.
    - If RR > 0, prepend `[RR]` to show how many replacements were suppressed.

    Example
    -------
    Raw input::

        ⠋ Running stats\\r⠙ Running stats\\r⠹ Running stats\\r⠸ Running stats\\n

    TTY buffer progression::

        1. "⠋ Running stats" (RR=0)
        2. "⠙ Running stats" (RR=1)
        3. "⠹ Running stats" (RR=2)
        4. "⠸ Running stats" (RR=3)
        5. \\n → commit

    Output (if throttle interval elapsed before \\n)::

        [3]⠸ Running stats

    Or if no throttling, outputs every update as-is.
    """
    # No throttling: pass through everything directly
    if log_interval is None:
        while True:
            try:
                chunk = os.read(master_fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
        return

    # Throttled mode: TTY emulation
    current_line = b""  # The "screen" buffer for the current line
    replacement_count = 0  # How many times current_line was replaced via \r
    last_output_time = 0.0  # When we last emitted output
    raw_buffer = b""  # Accumulator for incoming bytes

    while True:
        try:
            chunk = os.read(master_fd, 4096)
        except OSError:
            break
        if not chunk:
            break

        raw_buffer += chunk

        # Process the buffer character by character (conceptually)
        while raw_buffer:
            # Find the next control character
            idx_r = raw_buffer.find(b"\r")
            idx_n = raw_buffer.find(b"\n")

            # No control characters: accumulate into current_line
            if idx_r == -1 and idx_n == -1:
                current_line = raw_buffer
                raw_buffer = b""
                break

            # Determine which comes first
            if idx_n != -1 and (idx_r == -1 or idx_n < idx_r):
                # Newline comes first: commit the line
                content_before_newline = raw_buffer[:idx_n]
                raw_buffer = raw_buffer[idx_n + 1 :]

                # Build final line
                final_line = content_before_newline if content_before_newline else current_line
                prefix = f"[{replacement_count}]".encode() if replacement_count > 0 else b""

                sys.stdout.buffer.write(prefix + final_line + b"\n")
                sys.stdout.buffer.flush()

                # Reset state
                current_line = b""
                replacement_count = 0
                last_output_time = time.time()

            elif idx_r != -1:
                # Carriage return comes first: replace current line
                content_before_cr = raw_buffer[:idx_r]
                raw_buffer = raw_buffer[idx_r + 1 :]

                # Check for \r\n (treat as plain newline)
                if raw_buffer.startswith(b"\n"):
                    raw_buffer = raw_buffer[1:]
                    final_line = content_before_cr if content_before_cr else current_line
                    prefix = f"[{replacement_count}]".encode() if replacement_count > 0 else b""
                    sys.stdout.buffer.write(prefix + final_line + b"\n")
                    sys.stdout.buffer.flush()
                    current_line = b""
                    replacement_count = 0
                    last_output_time = time.time()
                    continue

                # Pure \r: replace the current line
                if content_before_cr:
                    current_line = content_before_cr
                replacement_count += 1

                # Check if we should emit a throttled update
                now = time.time()
                if now - last_output_time >= log_interval:
                    prefix = f"[{replacement_count}]".encode() if replacement_count > 0 else b""
                    sys.stdout.buffer.write(prefix + current_line + b"\n")
                    sys.stdout.buffer.flush()
                    last_output_time = now
                    replacement_count = 0

    # Flush any remaining content
    if current_line:
        prefix = f"[{replacement_count}]".encode() if replacement_count > 0 else b""
        sys.stdout.buffer.write(prefix + current_line + b"\n")
        sys.stdout.buffer.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("domain", help="Domain to mutate")
    parser.add_argument("--log-interval", type=int, default=None, help="Throttle progress logs to every N seconds")
    args = parser.parse_args()

    domain = args.domain
    domain_path = f"wks/api/{domain}"
    stats_file = REPO_ROOT / f"mutation_stats_{domain}.json"
    mutants_dir = REPO_ROOT / "mutants"
    setup_cfg = REPO_ROOT / "setup.cfg"

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
