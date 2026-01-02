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

    # 3. Clear artifacts
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

        # Use pty to trick mutmut into thinking it's running in a real terminal
        # This ensures it outputs \r for progress bars instead of newlines or buffering
        master_fd, slave_fd = pty.openpty()

        p = subprocess.Popen(
            [mutmut_bin, "run"],
            cwd=str(REPO_ROOT),
            stdout=slave_fd,
            stderr=slave_fd,  # Merge stderr into stdout
            text=False,  # pty works with bytes
            bufsize=0,
        )
        # Close slave fd in parent so we get EOF when child closes it
        os.close(slave_fd)

        captured_bytes = bytearray()

        # Stream output from master_fd
        try:
            while True:
                # Read chunks (1024 bytes) - blocking read
                # OSError is raised when the slave process closes the pty
                try:
                    chunk = os.read(master_fd, 1024)
                except OSError:
                    break

                if not chunk:
                    break

                captured_bytes.extend(chunk)
                if args.progress:
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
        finally:
            # Ensure process is cleaned up
            p.wait()
            os.close(master_fd)

        # Decode for stats parsing and logging
        output = captured_bytes.decode("utf-8", errors="replace")

        if p.returncode != 0:
            print("mutmut run failed!")
            # Print last 20 lines of output for debugging
            print("\n".join(output.splitlines()[-20:]))

            # Write stdout/stderr to mutants dir
            # Note: stderr is merged into stdout
            (mutants_dir / "mutmut.stdout").write_text(output)
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

    finally:
        setup_cfg.write_text(original_cfg)


if __name__ == "__main__":
    main()
