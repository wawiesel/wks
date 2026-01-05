# NEXT priorities for WKS: A Roadmap of Sorts


## Consolidate Utils into Config Domain [P1]

**Why**: Move all `wks/utils` and `wks/api/utils` code to `wks/api/config` to achieve strict `wks/api/<domain>` behavior and better structure. This ensures all API code follows the domain-based organization pattern and eliminates the top-level utils directory.

**Status**: In progress (PR #55). See PR description for detailed task list and migration plan.

- [ ] Audit all files in `wks/utils/` and `wks/api/utils/`
- [ ] Move utility functions to `wks/api/config/` (or appropriate domain if domain-specific)
- [ ] Update all imports across the codebase
- [ ] Remove `wks/utils/` and `wks/api/utils/` directories
- [ ] Update documentation to reflect new structure
- [ ] Verify all tests still pass after migration

## Implement Diff (bsdiff and Meyers) [P1]

**Why**: Diff capabilities are essential for tracking changes, comparing versions, and understanding file evolution. Binary diff (bsdiff) enables efficient storage and transfer of binary file changes, while text diff (Myers) provides human-readable change tracking for text files.

- [ ] Implement bsdiff algorithm for binary diff operations
- [ ] Implement Myers diff algorithm for text diff operations
- [ ] Create `wks/api/diff/` domain with proper API structure
- [ ] Add CLI commands for diff operations
- [ ] Add MCP support for diff operations
- [ ] Write comprehensive tests for diff algorithms
- [ ] Document diff capabilities and use cases

## Fully Implement Requirements Traceability for All Domains [P1]

**Why**: Requirements traceability ensures that every requirement is tested and verified, providing confidence that the system meets its specifications. It enables auditability, helps identify gaps in test coverage, and makes it clear which tests validate which requirements.

- [ ] Create requirement files (`qa/reqs/*.yml`) for all domains
- [ ] Add Requirements blocks to all test docstrings
- [ ] Ensure all requirements are linked to tests
- [ ] Update traceability audit to show 100% coverage for all domains
- [ ] Document traceability workflow in CONTRIBUTING.md
- [ ] Automate traceability validation in CI

## Increase Test and Mutation Coverage [P1]

**Why**: High test and mutation coverage ensures code quality, catches bugs early, and provides confidence when refactoring. Mutation testing validates that tests are actually testing the code, not just passing. Achieving 100% coverage and ≥90% mutation score demonstrates a robust, well-tested codebase.

- [ ] Achieve 100% test coverage for all domains
- [ ] Achieve ≥90% mutation score for all domains
- [ ] Implement Subprocess Tracing for coverage
    - Configure `.coveragerc` with `concurrency = multiprocessing`
    - Use `sitecustomize.py` to ensure all child processes are tracked
    - Merge coverage data files before reporting
- [ ] Handle System-Level Error Branches
    - Use FUSE or LD_PRELOAD to simulate IO failures (disk full, hardware errors)
    - Refactor system-heavy modules for dependency injection (FS/Process abstractions)
- [ ] Verify Signal Resilience
    - Send real SIGTERM/SIGINT in tests with proper synchronization
- [ ] Confirm `.coveragerc` has `fail_under = 100` once roadmap items are completed

## Tutorial Completion [P3]

**Why**: Complete tutorials help new users and contributors understand the system quickly. They serve as both documentation and examples of best practices, making the system more accessible and easier to adopt.

- [ ] Complete `docs/tutorials/01-walkthrough/walkthrough.md`
