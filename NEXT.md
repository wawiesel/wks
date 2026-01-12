# NEXT priorities for WKS: A Roadmap of Sorts

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

- [/] Complete `docs/tutorials/01-walkthrough/walkthrough.md` (adding Transform and Diff sections)
