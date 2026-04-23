# WKS Migration Strategy

## Purpose

This document defines a migration strategy for WKS from its current `CLI + MCP + cmd_*` shape to a multi-surface architecture that can support:

- a strong internal Python API
- a thin CLI
- a thin MCP server
- an optional REST surface

without losing the traceability and command-level test mapping that already exists in WKS.

This is not a speculative architecture note. It is intended to drive implementation, test planning, documentation updates, and rollout sequencing.

## Executive Summary

WKS is already partway to the desired architecture, but it is not there yet.

What WKS has today:

- a substantial internal execution layer under `wks/api/`
- command-shaped public execution entry points (`cmd_*`)
- thin-ish CLI wrappers
- a thin-ish MCP server that discovers and executes `cmd_*`
- strong emphasis on traceability and per-command tests

What WKS does not yet have:

- a stable service layer below `cmd_*`
- a clean Python facade analogous to `scaleman.services`
- a REST transport
- a test matrix that cleanly separates:
  - deep internal correctness
  - per-command contract verification
  - limited cross-transport smoke coverage

The central recommendation is:

1. Do not replace the `cmd_*` layer.
2. Introduce a reusable service/core layer underneath it.
3. Keep command wrappers as first-class traceable artifacts.
4. Add Python and REST surfaces on top of the same service/core layer.
5. Keep CLI and MCP smoke-thin.
6. Preserve one-command-to-one-test-family mapping.

That preserves what matters most in WKS:

- command traceability
- requirement-to-test mapping
- deterministic behavior
- DRY business logic

## Why This Migration Exists

The motivating goal is not merely "support more interfaces."

The goal is to support multiple interfaces while keeping confidence structured in a disciplined way:

- deep API/service tests prove the internals are correct
- command tests prove each user-facing command contract is correct
- limited smoke tests prove CLI, MCP, and REST all work

The intended confidence model is:

- internals are trusted because the deep tests are exhaustive
- commands are trusted because each command still has explicit tests
- transports are trusted because each transport has a small but real end-to-end smoke suite

This is materially different from a design where CLI, MCP, REST, and Python each evolve their own business logic or own test trees.

## Non-Negotiable Constraints

The migration must preserve these constraints.

### 1. Command Traceability Must Survive

WKS already has a testing and traceability culture centered on command files and requirement IDs.

The migration must preserve:

- the existence of explicit `cmd_*` entry points
- the ability to map tests to individual commands
- the ability to scan tests for requirement IDs
- the ability to reason about command contracts independently of transport

This means:

- no collapsing the system into only generic services plus thin HTTP/CLI endpoints
- no deleting command-level tests in favor of only shared service tests
- no hiding command behavior in generic routers

### 2. Deep Tests Must Target Shared Internals

The migration is not allowed to turn the repo into mostly end-to-end tests.

The deep confidence should come from:

- services
- controllers
- core algorithms
- parsers
- index/search logic
- transform logic

This implies:

- service/core tests should be the deepest and broadest test layer
- transport tests should stay intentionally narrow

### 3. CLI, MCP, and REST Must Stay Thin

The transport layers should be thin enough that a small smoke suite is sufficient.

This means:

- no duplicated business logic in CLI
- no duplicated business logic in MCP
- no duplicated business logic in REST
- transport layers should mostly do:
  - argument parsing
  - schema validation
  - adaptation to service inputs
  - formatting/serialization of outputs

### 4. NoHedging Still Applies

Adding more surfaces must not create fallback-heavy ambiguity.

The migration should prefer:

- explicit typed inputs
- explicit typed outputs
- explicit errors
- explicit unsupported operations

The migration should avoid:

- best-effort defaults hiding missing data
- silent transport-specific behavior drift
- hidden local-vs-remote switching logic that cannot be observed or tested

### 5. DRY Must Stay True

Each business rule should still have one authoritative implementation.

The migration must not create:

- one implementation for CLI
- another for MCP
- another for REST
- another for Python import users

## Current State

### Current Reality in Code

WKS currently has these important layers:

- `wks/api/`
- `wks/cli/`
- `wks/mcp/`

Important observed facts:

- `wks/mcp/discover_commands.py` auto-discovers `cmd_*` functions in `wks/api/`
- `wks/mcp/server.py` generates MCP tool metadata from discovered command functions
- CLI modules directly import and execute `cmd_*` functions via wrappers
- many `cmd_*` modules contain both business work and command/result orchestration
- `StageResult` is the core command output shape used across the current design

Representative files:

- `wks/api/search/cmd.py`
- `wks/api/cat/cmd.py`
- `wks/api/index/cmd.py`
- `wks/mcp/server.py`
- `wks/mcp/discover_commands.py`
- `wks/cli/status.py`

### Current Reality in Tests

WKS already has a useful testing split described in `tests/README.md`:

- `tests/unit/`
- `tests/integration/`
- `tests/smoke/`

Important observed facts:

- unit tests are centered on `wks/api/*`
- test naming already maps well to commands
- test docstrings already carry `Requirements:` blocks
- traceability tooling already expects that pattern

This is an asset and should be preserved.

### Current Reality in Documentation

Some current documentation is directionally correct but not fully aligned with the code as it exists now.

For example, some docs describe:

- `CLI -> MCP -> API`

but the actual code path in the current repo is closer to:

- `CLI -> cmd_*`
- `MCP -> cmd_*`

with both using the same command layer rather than CLI routing through MCP.

This matters because the migration document must reflect reality, not stale prose.

## Comparison to SCALEMAN

SCALEMAN demonstrates a useful multi-surface strategy:

- CLI
- MCP
- REST
- Python API

all sharing a common service/core implementation.

That part is good and worth copying.

However, WKS should not copy SCALEMAN mechanically.

### What WKS Should Copy

- a shared service/core layer under all transports
- a real Python-facing facade
- an optional REST layer for non-MCP remote use
- transport-thin architecture
- consistent typed data models across surfaces

### What WKS Should Not Copy Blindly

- module-level global connection state as the main access pattern
- transport-specific behavior drift hidden behind convenience wrappers
- any design that demotes command wrappers to an unimportant compatibility layer

For WKS, the better fit is:

- explicit service objects or explicit service functions
- command wrappers preserved as durable traceable artifacts
- transport-specific adapters on top

## The Core Design Decision

The most important design rule is:

**Service under command, not command under service transport wrappers.**

That means:

- service/core layer contains shared behavior
- `cmd_*` wraps service/core behavior into command semantics
- CLI/MCP/REST adapt requests into either:
  - service calls
  - or command calls where command semantics are the public contract

The command layer remains a real architectural boundary.

## Target Architecture

### Overview

Target shape:

```text
             +-------------------+
             |   Python Client   |
             |  (wks.services)   |
             +---------+---------+
                       |
             +---------v---------+
             |   Service/Core    |
             |   typed models    |
             |   no StageResult  |
             +---------+---------+
                       |
             +---------v---------+
             |    cmd_* layer    |
             | command contract  |
             |   StageResult     |
             +----+---------+----+
                  |         |
         +--------v-+   +---v--------+
         |   CLI    |   |    MCP     |
         +----------+   +------------+
                  |
         +--------v--------+
         |      REST       |
         |   thin adapter  |
         +-----------------+
```

This diagram is intentionally conservative.

REST does not need to call `cmd_*` for every operation if the HTTP contract is better modeled directly from service/core outputs, but the command layer must still exist and remain tested.

### Layer Responsibilities

#### 1. Service/Core Layer

This is the new layer that WKS does not cleanly have today.

Responsibilities:

- own the actual business logic
- expose typed request/response models
- avoid `StageResult`
- avoid CLI/MCP/REST concerns
- avoid progress-display concerns
- provide deterministic behavior
- provide reusable logic for transport adapters and command wrappers

Examples of suitable service-layer concerns:

- resolve search strategy and run search
- transform a file and return typed transform metadata
- retrieve cached content
- compute monitor status
- perform a move and return a typed move result
- inspect daemon/service state

This layer is where the deepest tests should focus.

#### 2. Command Layer (`cmd_*`)

This layer stays.

Responsibilities:

- define the contract of each command
- perform command-level validation
- load configuration if that is part of command semantics
- convert service/core results into `StageResult`
- preserve announce/progress/result/output structure
- preserve traceable one-command-per-file behavior

Examples:

- `wks/api/search/cmd.py`
- `wks/api/cat/cmd.py`
- `wks/api/mv/cmd.py`

This layer is where command tests continue to live.

#### 3. CLI Layer

Responsibilities:

- parse user input
- invoke command wrappers
- format `StageResult`
- print to stdout/stderr correctly

It should remain thin enough that smoke/integration tests can be small.

#### 4. MCP Layer

Responsibilities:

- expose tools
- validate schema
- invoke command wrappers or service adapters consistently
- serialize structured output

It should remain thin enough that smoke/integration tests can be small.

#### 5. REST Layer

Responsibilities:

- provide HTTP access to stable read operations first
- expose typed request/response models
- map exceptions to explicit HTTP errors
- remain thin

It should begin as a read-only surface.

## Why Preserve the Command Layer

The migration must not erase the command layer because the command layer is doing more than transport adaptation.

It currently provides:

- per-command contract identity
- per-command traceability
- per-command test targeting
- `StageResult` behavior
- explicit user-facing semantics

That is valuable even after introducing a cleaner service/core layer.

If the command layer is removed, WKS loses:

- simple one-file-per-command reasoning
- direct mapping between tests and commands
- a clean place to encode command-specific behavior without polluting services

## Proposed Public Python Surface

WKS should gain an explicit Python-facing facade.

Recommended shape:

```python
from wks import services

svc = services.WKSService.from_config()
result = svc.search(query="burnup credit", index="main", k=10)
```

or:

```python
from wks.services import WKSService
```

Avoid a global mutable connection model as the primary design.

Recommended properties:

- explicit construction
- explicit configuration
- typed methods
- typed return models
- no `StageResult`

Possible methods:

- `status()`
- `search(...)`
- `cat(...)`
- `similar(...)`
- `transform(...)`
- `index_add(...)`
- `index_status(...)`
- `monitor_status()`
- `vault_status()`
- `link_show(...)`
- `mv(...)`

Not every command must be elevated to the first version of the Python facade.

Start with:

- read-only operations
- stable data-returning operations
- operations that already have clear output schemas

## Proposed REST Surface

REST should be added only after the service/core layer exists.

Recommended initial scope:

- `GET /status`
- `GET /config/sections`
- `GET /config/{section}`
- `GET /search`
- `GET /similar`
- `GET /cat` or `POST /cat`
- `GET /index/{name}/status`
- `GET /monitor/status`
- `GET /vault/status`
- `GET /link/show`

Recommended first-phase exclusions:

- daemon start/stop
- service install/uninstall
- destructive database operations
- broad write/admin operations

Those can be deferred until the read-only path is stable and tested.

### Why Read-Only First

Read-only REST:

- is easier to secure
- is easier to smoke test
- is less likely to create transport-specific edge cases
- gives real value quickly

## Testing Strategy After Migration

This is the central testing model the migration should produce.

### 1. Deep Service/Core Tests

These are the main correctness tests.

Purpose:

- prove the shared internals are correct
- cover edge cases deeply
- keep transports from needing large test matrices

Examples:

- search ranking behavior
- transform engine selection
- cache resolution
- URI/path normalization
- monitor priority logic
- move policy logic
- vault/link resolution logic

Naming recommendation:

- `test_wks_service_<domain>_<feature>.py`
- or `test_wks_core_<domain>_<feature>.py`

These should be the deepest and most numerous tests added by the migration.

### 2. Command Tests

These remain explicit and mapped to commands.

Purpose:

- prove each command contract is correct
- prove command-level validation is correct
- prove `StageResult` behavior is correct
- preserve traceability and requirement mapping

Naming should remain command-shaped:

- `test_wks_api_<domain>_cmd_<name>.py`

These tests should cover:

- required arguments
- command-level mutual exclusions
- config-loading behavior
- conversion from service/core outputs to command outputs
- expected errors and warnings

These tests remain the canonical answer to:

"Does command X still work as command X?"

### 3. Transport Smoke Tests

These should be intentionally small.

Purpose:

- prove each transport is wired
- prove serialization/schema paths work
- catch drift between transport and command/service contracts

Transport suites:

- CLI smoke
- MCP smoke
- REST smoke

These are not the place for deep business logic coverage.

### 4. Proposed Confidence Matrix

The desired assurance model is:

- Service/core tests answer:
  - "Are the internals correct?"
- Command tests answer:
  - "Does each user-facing command behave correctly?"
- Smoke tests answer:
  - "Do CLI, MCP, and REST all work at all?"

That is the correct division of labor.

## Required Traceability Policy

The migration should explicitly adopt these traceability rules.

### Rule 1: Every Command Keeps a Command Test Family

For every `cmd_*` entry point, there should remain:

- at least one dedicated command test file
- requirements/docstring traceability where applicable

### Rule 2: Service Tests Do Not Replace Command Tests

A service test proving `search` internals work does not eliminate the need for:

- `test_wks_api_search_cmd.py`

The command wrapper remains a traceable contract.

### Rule 3: Smoke Tests Stay Narrow

Smoke tests should not become the main verification vehicle.

If a behavior can only be proven by smoke tests, the architecture is too transport-heavy.

### Rule 4: Requirement Mapping Must Remain Stable

Tests that currently map requirement IDs through docstrings must keep doing so.

If new REST commands or Python facade operations create new requirements, the traceability model must be extended explicitly, not assumed.

## Recommended Smoke Matrix

Keep the smoke matrix deliberately limited.

Recommended commands/features for cross-transport smoke coverage:

- `status`
- one config read
- one search
- one content retrieval (`cat`)
- one related retrieval (`similar`) if stable
- one path-based operation like `mv` using temp fixtures
- one known failure path

Per transport:

### CLI Smoke

- binary launches
- command succeeds
- stdout/stderr shape is sane
- exit code is correct

### MCP Smoke

- server advertises tools
- one read tool call succeeds
- one search tool call succeeds
- one failure case returns structured error

### REST Smoke

- server launches
- health endpoint works
- one read endpoint works
- one search endpoint works
- one 4xx error case behaves correctly

This is enough if the service/core layer is thoroughly tested.

## Migration Phases

### Phase 0: Document Reality

Before changing code:

- correct docs that misstate the current architecture
- document the actual current path:
  - CLI -> `cmd_*`
  - MCP -> `cmd_*`
- define the target state

Deliverables:

- this document
- follow-up doc cleanup in `README.md`, `wks/README.md`, `CONTRIBUTING.md`, and `wks/mcp/README.md`

### Phase 1: Introduce Service/Core Layer Under Existing Commands

This is the most important implementation phase.

For a small set of representative domains:

- `search`
- `cat`
- `mv`
- `status`

extract reusable service/core logic below `cmd_*`.

Goal:

- command behavior unchanged
- CLI unchanged
- MCP unchanged
- new deep tests land under service/core

The `cmd_*` modules should become thinner wrappers over services.

### Phase 2: Define Typed Service Models

Introduce explicit typed request/response models for service/core operations.

These models should:

- not be `StageResult`
- not encode CLI progress behavior
- be directly usable by REST and Python callers

This reduces transport-specific shape drift.

### Phase 3: Add Python Facade

Introduce a public importable layer such as:

- `wks.services`
- possibly `WKSService`

Start with read-mostly operations.

This gives:

- a direct Python surface
- a stable internal contract for REST
- a clean target for deep tests

### Phase 4: Add Read-Only REST

Once the service/core layer is stable:

- add FastAPI
- expose a small read-only surface
- add narrow REST smoke tests

Do not start with full admin/write coverage.

### Phase 5: Expand Coverage Deliberately

Only after the pattern is proven:

- widen service/core extraction to more domains
- widen Python facade
- widen REST where justified

## Concrete Work Items

The migration should be executed as a sequence of small, reviewable changes.

### Work Item A: Correct Architecture Documentation

Update current docs to distinguish:

- current code reality
- target architecture

Files likely to change:

- `README.md`
- `CONTRIBUTING.md`
- `wks/README.md`
- `wks/mcp/README.md`
- `tests/README.md`

Expected outcomes:

- no more stale `CLI -> MCP -> API` claims if the code does not do that
- explicit statement that `cmd_*` is the command contract layer
- explicit statement that service/core is a new layer to be introduced

### Work Item B: Create a New Service Namespace

Introduce a dedicated package for reusable service/core operations.

Possible locations:

- `wks/services/`
- `wks/core_services/`

Recommendation:

- prefer `wks/services/` for the public facade
- keep lower-level helpers in domain-specific modules under it

Example structure:

```text
wks/services/
    __init__.py
    status.py
    search.py
    cat.py
    mv.py
    models.py
```

Expected outcomes:

- reusable typed operations exist without `StageResult`
- command wrappers can delegate into them

### Work Item C: Define Shared Typed Models

Introduce typed request/response models for migrated domains.

The models should be suitable for:

- Python callers
- REST serialization
- command-wrapper translation

These models should not:

- depend on CLI formatting
- depend on MCP envelopes
- encode progress state

### Work Item D: Refactor the First Command Set

Refactor the first representative commands to call the new service layer.

Recommended first set:

- `status`
- `search`
- `cat`
- `mv`

Expected outcomes:

- command behavior preserved
- command tests preserved
- new service tests added

### Work Item E: Add Python Facade

After the first commands are migrated, expose a stable importable entry surface.

Recommendation:

- `from wks import services`
- `from wks.services import WKSService`

Expected outcomes:

- a supported direct Python usage pattern exists
- deep tests can target service methods directly

### Work Item F: Add Read-Only REST Server

Only after the service/core layer is real.

Suggested implementation:

- FastAPI
- explicit response models
- no transport-specific business logic

Suggested initial endpoints:

- `/status`
- `/search`
- `/cat`
- `/config/sections`
- `/config/{section}`

### Work Item G: Add REST Smoke Tests

Add a new smoke/integration slice for REST.

Possible naming:

- `tests/integration/test_rest_<domain>.py`
- `tests/smoke/test_wks_rest_<domain>.py`

The tests should stay small and transport-focused.

### Work Item H: Update Traceability Guidance

Explicitly update test guidance so the new layering is not misread as permission to collapse command tests.

This should state:

- service tests are additive
- command tests remain mandatory
- smoke tests remain narrow

## Review Checklist

Any migration PR should be evaluated against this checklist.

### Architecture Checklist

- Is the new logic in a reusable service/core module?
- Did the command wrapper remain present?
- Did the command wrapper become thinner, not fatter?
- Did the transport stay thin?

### DRY Checklist

- Is the business rule implemented in one place?
- Did the PR avoid creating CLI-only, MCP-only, or REST-only logic forks?

### NoHedging Checklist

- Are required values still required?
- Are errors explicit?
- Did the PR avoid introducing silent fallback behavior?

### Traceability Checklist

- Does the command still have its command test file?
- Were requirement mappings preserved?
- Were any new requirements introduced explicitly?

### Testing Checklist

- Were deep service/core tests added?
- Were command tests preserved or improved?
- Were only small transport smoke/integration tests added?

## Exit Condition for the First Successful Slice

The first migration slice should be considered successful only if all of the following are true for the initial migrated domains:

- service/core functions exist and are directly unit-tested
- `cmd_*` wrappers still exist and still have command tests
- CLI still works
- MCP still works
- Python facade works
- if REST is included in that slice, REST works
- docs are updated to describe the new reality truthfully

## Recommended First Domains

The migration should not begin with the hardest domains.

Recommended first set:

### 1. `search`

Why:

- high value
- already conceptually service-like
- easy to imagine Python and REST use
- already has structured output

### 2. `cat`

Why:

- widely useful
- strong read-only candidate
- good exercise of transform/cache separation

### 3. `status`

Why:

- simple
- useful smoke-test target
- good for initial REST health/data patterns

### 4. `similar`

Why:

- useful read API
- complements `search`

Defer initially:

- `daemon`
- `service`
- destructive database operations

## What Should Stay Out of the Service Layer

The service/core layer should not absorb:

- CLI progress rendering
- stderr/stdout rules
- raw JSON-RPC envelope concerns
- HTTP status mapping
- command help behavior
- transport-specific schema generation

Those belong in command or transport layers.

## Risks

### Risk 1: Destroying Command Traceability

If the service layer becomes the only thing that matters, command identity erodes.

Mitigation:

- keep `cmd_*` as explicit wrappers
- keep command test files
- keep requirement mapping on command tests

### Risk 2: Over-Abstracting Too Early

If a giant generic service framework is built before the first few domains are proven, the migration will stall.

Mitigation:

- migrate 3-4 domains first
- let the abstractions emerge from those domains

### Risk 3: Transport Drift

If REST, MCP, and CLI each do slightly different validation or output shaping, DRY breaks.

Mitigation:

- service/core models own the data contract
- command layer owns command contract
- transports stay thin

### Risk 4: Documentation Lying Again

If the docs jump ahead of the code, the migration document becomes fiction.

Mitigation:

- update docs only when the code matches
- keep this document explicit about current vs target state

## Policy Change Required

Today, repo policy text says WKS should support only CLI and MCP.

If WKS adopts this migration, that policy must change explicitly.

Required policy update:

- WKS supports:
  - internal Python service/core APIs
  - CLI
  - MCP
  - optional REST where justified

Without that policy change, REST would remain out of bounds even if the technical design is sound.

## Recommended Documentation Updates After Approval

If this migration is accepted, the next docs to update should be:

- `README.md`
- `CONTRIBUTING.md`
- `wks/README.md`
- `wks/mcp/README.md`
- `tests/README.md`

Those updates should:

- state current architecture truthfully
- describe the new service/core layer
- define the test split clearly
- define which layers own which responsibilities

## Acceptance Criteria

The migration should be considered successful only when all of the following are true.

### Architecture

- a reusable service/core layer exists under command wrappers
- at least one public Python-facing entry surface exists
- CLI and MCP remain thin
- REST exists only if built on the same service/core layer

### Traceability

- command wrappers still exist
- command tests still map 1:1 to commands
- requirement traceability remains intact

### Testing

- deep service/core tests exist for migrated domains
- command tests still exist for migrated domains
- CLI/MCP/REST smoke tests are present but limited

### Documentation

- docs describe actual code paths, not outdated intent

## Final Recommendation

WKS should adopt the SCALEMAN-style multi-surface strategy only in the following form:

- preserve `cmd_*`
- add service/core beneath it
- keep command-level tests and traceability
- add a Python facade
- add read-only REST later
- keep smoke tests narrow
- keep deep tests on the shared internals

That gives WKS the flexibility of a multi-surface system without sacrificing the command mapping and traceability discipline that already make the repo valuable.
