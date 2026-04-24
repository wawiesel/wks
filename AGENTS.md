---
alwaysApply: true
---

# Directives for AI

Start by identifying the relevant `.cursor/rules/*`, verifying the change against them, and checking existing wrappers, handlers, and facades before adding new logic.

- Authentication: never authenticate as a human user; always use a bot account.

Follow all `.cursor/rules/*`.

For setup, coding standards, commit messages, and quality processes, use [CONTRIBUTING.md](CONTRIBUTING.md). This file only adds AI-specific directives.

- Use `venv`. Bootstrap immediately with `python3 -m venv venv && venv/bin/pip install -e .` if tools are missing.
- Run checks and tests from `venv`, including `scripts/check_format.py`, `scripts/check_types.py`, `scripts/check_complexity.py`, and full `pytest`.
- Use Conventional Commits.
- Keep the shared internal Python service/core API as the source of truth with thin CLI, MCP, and read-only REST layers. REST is mandatory.
- Remove dead code, hedging, silent defaults, redundant state, and backward-compatibility scaffolding.
- Use strict typed config models, fail fast, aggregate errors clearly, and favor deterministic behavior.
- Keep CLI stdout content-only; send status/progress/warnings/errors to stderr or logs as appropriate.
- Support `--live` for live-updating status-style commands, keep displays simple, and split files over `900` lines.

## Effective Workflow for PR Reviews

When asked to address PR comments or check a PR:
1.  **Do not rely on `gh pr view <id>` alone**: It often hides inline code comments, leading to missed feedback.
2.  **Use `gh pr view <id> --json reviews,comments`**: This fetches review summaries and top-level comments.
3.  **Use `gh api repos/{owner}/{repo}/pulls/{number}/reviews`**: This lists all review events and their states (COMMENTED/CHANGES_REQUESTED/APPROVED).
4.  **Use `gh api repos/{owner}/{repo}/pulls/{number}/comments`**: This is the most reliable way to get inline code comments, including resolved ones.
5.  **Check for "Files changed"**: Verify if files tagged for deletion are actually deleted in the git index (`git ls-files`).
