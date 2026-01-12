# NEXT priorities for WKS: A Roadmap of Sorts

## Tutorial Completion [P0]

**Why**: Complete tutorials help new users and contributors understand the system quickly. They serve as both documentation and examples of best practices, making the system more accessible and easier to adopt.

- [/] Complete `docs/tutorials/01-walkthrough/walkthrough.md`
  - [x] Added Transform section (section 4)
  - [x] Added Diff section (section 5)
  - [x] Updated section numbers (Link→6, Database→7, Config→8, Log→9)
  - [x] Updated command reference table
  - [x] Fixed bug: `cmd_info.py` missing output on error path (caused "must set result.output" error)
  - [x] Fixed bug: `transform.py` CLI printer crashed when engine not found
  - [x] Tested all walkthrough commands - all sections work

### Known Issues Found During Testing

1. **Transform dx engine** - Document conversion has issues with certain file types:
   - Markdown files fail with "Is a directory" error when Docling creates artifact directories
   - Need to investigate `wks/api/transform/_docling/_DoclingEngine.py`

### PR #60 Status

Branch: `docs/complete-walkthrough`
Status: Ready for review - documentation complete, bugs fixed

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

