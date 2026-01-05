# NEXT priorities for WKS: A Roadmap of Sorts

## Use URI Consistently Everywhere [P1]

**Why**: Consistent use of the `URI` type throughout the codebase ensures type safety, prevents URI format errors, and makes the codebase more maintainable. It eliminates the risk of string-based URI handling bugs and provides a single source of truth for URI validation and manipulation.

- [ ] Audit all `wks/` source code for string-based path/URI handling
- [ ] Replace all `str` path parameters with `URI` type in API functions
- [ ] Update internal functions to use `URI` instead of `Path` or `str` where appropriate
- [ ] Ensure all database operations use `URI` type for URI fields
- [ ] Update utility functions (`convert_to_uri`, `uri_to_path`, etc.) to work with `URI` type
- [ ] Remove any remaining inline URI string formatting (`f"file://..."`)
- [ ] Add type hints and validation to enforce `URI` usage throughout the codebase

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
