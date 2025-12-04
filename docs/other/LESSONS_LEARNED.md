# Lessons Learned

Lessons grounded in work completed to date (alpha builds and the test refactor campaign).

## Testing & Coverage
- Separating smoke, unit, and integration suites keeps feedback fast; apply markers automatically in `tests/conftest.py` to enforce tiers.
- Mock external systems (MongoDB, filesystem) in unit tests and reserve live dependencies for integration runs.
- Coverage improves fastest by deleting dead code and removing hedging paths instead of over-mocking improbable branches.

## Architecture & Interfaces
- Enforcing the CLI → MCP → API flow keeps business logic in controllers and prevents drift between user interfaces.
- Dataclasses with strict validation reduced config bugs; fail-fast behavior is safer than fallback logic.
- Sharing controller outputs between CLI displays and MCP responses avoids format divergence.

## Tooling & Operations
- `pre-commit` plus `./scripts/check_quality.py` catches formatting, typing, and complexity issues before CI.
- Git worktrees make multi-branch campaign work safer without disturbing the main workspace.

## Vault and Transform
- URI-first handling and deterministic IDs simplify vault link reconciliation and re-runs.
- Caching transformed content by checksum avoids re-processing and produces stable inputs for diffing.
