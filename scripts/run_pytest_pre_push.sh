#!/usr/bin/env bash
# Wrapper script for pytest in pre-push hook
# Excludes linux_service tests (they require Docker with systemd)

.venv/bin/pytest tests/ -m "not linux_service" "$@"
