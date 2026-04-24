#!/usr/bin/env python3
import sys

from _run_pytest_suite import run_pytest_suite


def main() -> int:
    return run_pytest_suite("Integration", "tests/integration", sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
