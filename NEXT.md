# Next Development Priorities

## Coverage Improvement (Current: 46.20%)

### P0: Core Functionality (Target: 80%+)

- [ ] **daemon.py** (36.20% → 80%)
  - Event handling loops
  - Lock management (`_acquire_lock`, `_release_lock`)
  - Health monitoring
  - Vault sync integration

- [ ] **vault/controller.py** (30.67% → 80%)
  - Vault sync operations
  - Symlink management
  - Link extraction and indexing

- [ ] **vault/obsidian.py** (31.55% → 80%)
  - Markdown parsing
  - Link resolution
  - File move handling

- [ ] **cli/commands/service.py** (25.21% → 80%)
  - Service lifecycle commands
  - Status reporting
  - Launchd integration

### P1: Supporting Features (Target: 60%+)

- [ ] **status.py** (21.43% → 60%)
- [ ] **cli/commands/vault.py** (17.16% → 60%)
- [ ] **mongoctl.py** (44.57% → 60%)

### P2: Unused/Deprecated Modules

Review zero-coverage modules for removal:
- [ ] `links.py` - Assess if still needed
- [ ] `logging_config.py` - Integrate or remove
- [ ] `transform/config.py` - Consolidate with main config
- [ ] `vault/git_hooks/` - Assess integration
- [ ] `vault/git_watcher.py` - Assess integration

## Feature Completion

### Diff Layer
- [ ] Implement unified diff engine
- [ ] Add diff result format standardization
- [ ] Enable skipped smoke tests

### Transform Layer
- [ ] Complete engine registration system
- [ ] Add transform progress callbacks
- [ ] Enable skipped smoke tests

### Cat Command
- [ ] Complete cat command implementation
- [ ] Add cache-only mode
- [ ] Enable skipped smoke tests

## Technical Debt

### Configuration
- [ ] Phase out deprecated `load_config()` function
- [ ] Remove all remaining dict-based config access
- [ ] Ensure all modules use `WKSConfig` dataclass

### Logging
- [ ] Replace remaining `print()` statements with logger
- [ ] Implement CLI output protocol (4-step process):
  1. STDERR: "Doing X..."
  2. STDERR: Progress bar
  3. STDERR: "Done. Problems: Y"
  4. STDOUT: Result only

### Code Quality
- [ ] Verify all functions CCN ≤ 10
- [ ] Verify all files ≤ 900 lines
- [ ] Add lizard to CI pipeline

## Agent Integration (Future)

### Fileserver Agent Concept
- [ ] Design agent memory/state storage
- [ ] Define agent-config integration
- [ ] Move PATTERNS into agent execution framework
- [ ] Integrate CLAUDE.md patterns into agent behavior

**Vision**: AI assistant maintains knowledge base organization by executing PATTERNS to:
- Organize files automatically
- Maintain link consistency
- Suggest file routing
- Assemble related knowledge

## Documentation

- [ ] Merge coverage details from artifact into CONTRIBUTING.md
- [ ] Update SPEC.md with current implementation status
- [ ] Document agent integration design (when ready)
