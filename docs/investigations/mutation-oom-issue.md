# Mutation Test OOM Issue Investigation

## Problem Statement

Transform domain mutation tests in CI receive SIGTERM (exit code 143), terminating early.

---

## Investigation Timeline

### Step 1: Identify Signal Source

**Action:** Added signal handlers in Python and bash to log which signals are received.

**Evidence:**
```
>>> PYTHON SIGNAL RECEIVED: SIGTERM (15)
```

**Finding:** Process receives SIGTERM, not SIGKILL. Something is gracefully asking the process to terminate.

---

### Step 2: Test Systemd Hypothesis

**Action:** Ran mutation tests with two different container init processes:
- `/lib/systemd/systemd` as PID 1
- `tail -f /dev/null` as PID 1

**Evidence:**

| Container Init | Transform Result | Exit Code |
|----------------|------------------|-----------|
| `tail -f /dev/null` | ✅ Completes all 1166 mutations | 0 |
| `/lib/systemd/systemd` | ❌ Terminates at ~mutation 1040 | 143 |

**Finding:** Problem only occurs when systemd is running as container init.

---

### Step 3: Add Resource Monitoring

**Action:** Added periodic logging of process count, zombie processes, and available memory.

**Evidence:**
```
>>> RESOURCES: procs=6 zombies=0 mem_avail=14844MB
>>> RESOURCES: procs=6 zombies=0 mem_avail=14834MB
>>> RESOURCES: procs=6 zombies=0 mem_avail=14715MB
>>> RESOURCES: procs=6 zombies=0 mem_avail=14668MB
>>> RESOURCES: procs=6 zombies=0 mem_avail=14781MB
>>> PYTHON SIGNAL RECEIVED: SIGTERM (15)
```

**Finding:** Process count and zombie count remain stable. Available memory reported as ~14GB throughout.

---

### Step 4: Check Mutation Timing

**Action:** Observed mutation progress vs SIGTERM arrival.

**Evidence:**
```
⠇ 1040/1166  🎉 610 🫥 0  ⏰ 1  🤔 0  🙁 429  🔇 0
>>> PYTHON SIGNAL RECEIVED: SIGTERM (15)
⠏ 1041/1166  🎉 611 🫥 0  ⏰ 1  🤔 0  🙁 429  🔇 0
Error: Process completed with exit code 143.
```

**Finding:** Mutation 1041 completes AFTER SIGTERM is received. The signal doesn't immediately kill the process.

---

### Step 5: Add Journalctl Logging

**Action:** Captured systemd journal output to see what systemd was doing.

**Evidence:**
```
kernel: Out of memory: Killed process 9912 (mutmut: wks.api)
        total-vm:21090640kB, anon-rss:15842540kB, file-rss:192kB
kernel: oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),
        cpuset=docker.service,mems_allowed=0,global_oom,
        task_memcg=/system.slice/docker-...scope/init.scope,
        task=mutmut: wks.api,pid=9912,uid=1001
systemd[1]: init.scope: A process of this unit has been killed by the OOM killer.
```

**Finding:** Linux kernel OOM killer terminates the process due to memory exhaustion.

---

### Step 6: Analyze Process Memory at OOM

**Action:** Examined kernel's process list dump at time of OOM.

**Evidence:**
```
[   4736]  1001  4736   264514     4616     4616        0         0   458752    30912             0 mutmut
[   9912]  1001  9912  5272660  3960683  3960635       48         0 40288256   983296             0 mutmut: wks.api
```

Interpreting the columns for PID 9912 (`mutmut: wks.api`):
- `total_vm: 5272660` pages = ~20.5 GB virtual memory
- `rss: 3960683` pages = ~15.5 GB resident in RAM
- `swapents: 983296` pages = ~3.8 GB swapped out

System state:
```
Free swap  = 228kB
Total swap = 4194300kB
```

**Finding:** The mutmut worker process has ~15.5 GB in RAM + ~3.8 GB swapped = ~19.3 GB total allocated. Swap is nearly exhausted.

---

### Step 7: Analyze Mutation Rate Over Time

**Action:** Extracted timestamps from CI log (run 20874385343) to measure mutation throughput over time.

**Evidence:**

| Timestamp | Mutation | Rate |
|-----------|----------|------|
| 06:44:26 | 0 | (start) |
| 06:44:30 | 37 | ~9 mutations/sec |
| 06:50:30 | 835 | ~2.2 mutations/sec average |
| 06:55:02 | 1040 | ~0.75 mutations/sec (last 205 mutations) |
| 06:55:43 | 1041 | **41 seconds for 1 mutation** |

Raw log lines:
```
2026-01-10T06:44:26.5601676Z Running mutation testing
2026-01-10T06:44:26.6801403Z ⠇ 0/1166  🎉 0 🫥 0  ⏰ 0  🤔 0  🙁 0  🔇 0
2026-01-10T06:50:30.5104081Z ⠸ 835/1166  🎉 457 🫥 0  ⏰ 0  🤔 0  🙁 378  🔇 0
2026-01-10T06:55:02.8126073Z ⠇ 1040/1166  🎉 610 🫥 0  ⏰ 1  🤔 0  🙁 429  🔇 0
2026-01-10T06:55:43.9558812Z >>> PYTHON SIGNAL RECEIVED: SIGTERM (15)
2026-01-10T06:55:44.2599962Z ⠏ 1041/1166  🎉 611 🫥 0  ⏰ 1  🤔 0  🙁 429  🔇 0
```

**Finding:** Mutation rate degrades dramatically over time: from ~9/sec at start to taking 41 seconds for a single mutation at failure. This slowdown pattern is characteristic of **swap thrashing** from gradual memory exhaustion, not a sudden spike.

---

### Step 8: Local vs CI Context

**Action:** Documented environmental differences between local development and CI.

**Evidence:**

| Environment | Mutation Tests | Memory Issues |
|-------------|----------------|---------------|
| Local (macOS) | ✅ Complete successfully | None observed |
| CI with systemd | ❌ OOM at ~1040 | Yes |
| CI without systemd | ✅ Complete successfully | None observed |

**Observations:**
- Local development machines typically have 32-64 GB RAM
- GitHub Actions `ubuntu-latest` runners have ~16 GB RAM for public repos
- Local testing cannot reproduce the CI memory constraint

**Finding:** The issue is specific to CI environment memory constraints. Local testing is not a valid reproduction environment.

---

### Step 9: Investigate MemAvailable Discrepancy

**Action:** Analyzed why Step 3 showed stable ~14 GB memory while OOM occurred.

**Evidence:**
- Step 3 RESOURCES logs: `mem_avail=14844MB` → `14668MB` → `14781MB` (stable)
- Step 5 OOM: Process killed with 15.5 GB RSS + 3.8 GB swap = 19.3 GB

**Observation:** The ~14 GB MemAvailable from `/proc/meminfo` represents **host memory**, while the OOM occurred in a container with cgroup limits. When systemd runs as init, it creates `/system.slice/docker-.../init.scope` cgroup hierarchy which enforces memory accounting.

**Finding:** The RESOURCES monitoring was measuring the wrong metric. Container-level memory consumption was invisible to our monitoring.

---

### Step 10: Experiment 1 - Implement Cgroup Memory Measurement

**Action:** Modified `_log_resources()` in `test_mutation_api.py` to read cgroup v2/v1 memory metrics instead of host `/proc/meminfo`. Added logging of `cgroup_mem`, `cgroup_limit`, and `host_mem` for comparison.

**Evidence from run [20898439660](https://github.com/wawiesel/wks/actions/runs/20898439660):**

Run configuration:
- Docker flags: `--cgroupns=host -v /sys/fs/cgroup:/sys/fs/cgroup:rw`
- Container init: `/lib/systemd/systemd`
- Same setup as runs that OOM killed

Log output:
```
>>> RESOURCES: procs=5 zombies=0 cgroup_mem=N/A cgroup_limit=N/A host_mem=14803MB
>>> RESOURCES: procs=5 zombies=0 cgroup_mem=N/A cgroup_limit=N/A host_mem=14815MB
...
Running mutation testing
[1]⠇ 0/1166  🎉 0 🫥 0  ⏰ 0  🤔 0  🙁 0  🔇 0
[1]⠏ 1/1166  🎉 1 🫥 0  ⏰ 0  🤔 0  🙁 0  🔇 0
...
✅ All 1166 mutations completed successfully
Run completed in 13m48s with NO OOM
```

**Observations:**
1. `cgroup_mem=N/A` - Cgroup v2 paths (`/sys/fs/cgroup/memory.current`) don't exist inside container
2. `host_mem=14803MB` - Host memory stable at ~14.8 GB throughout
3. **All 1166 mutations completed successfully** - NO OOM kill
4. Run time: 13m48s (faster than previous 15+ min before OOM)

**Unexpected Finding:** This run used the **same systemd configuration** that previously caused OOM kills, yet it succeeded. This contradicts earlier evidence from Step 2.

**Questions Raised:**
1. Why did this run succeed when previous runs with identical config OOM'd?
2. Is there variance in GitHub Actions runner memory availability?
3. Were there code changes between runs that affected memory usage?
4. Why don't cgroup paths exist inside the container?

---

### Step 11: Analyze CI Run History and Code Changes

**Action:** Examined CI run history and code diffs between OOM and non-OOM runs.

**Evidence - CI Run History:**

| Run ID | Commit | OOM in logs? | Result |
|--------|--------|--------------|--------|
| 20898439660 | 1373e78 | NO | success (genuine) |
| 20874385343 | fa7825c | YES | success (workflow continued) |
| 20874029042 | 1b32570 | NO | success (no systemd) |
| 20873648465 | c5853ba | YES | failure |

**Important clarification:** Run `20874385343` shows "success" in GitHub UI but **did have OOM kill** inside:
```
Jan 10 06:55:43 kernel: oom-kill:...task=mutmut: wks.api,pid=7115
Jan 10 06:55:43 systemd[1]: init.scope: A process killed by OOM killer
```
The workflow uses `|| true` so it continues despite OOM and commits stats.

**Code changes between fa7825c (OOM) and 1373e78 (no OOM):**
```
scripts/test_mutation_api.py | 58 ++++++++++++++++++++++++++++++++------
 1 file changed, 51 insertions(+), 7 deletions(-)
```
Only logging changes - no functional code changes.

**Finding:** The OOM occurrence varies **between identical code runs** on different GitHub runners. This strongly suggests the issue is runner memory variance, not code-caused.

---

## System Mental Model

### How Mutmut Uses Memory

1. **Parent process**: Loads Python interpreter, all imports, pytest infrastructure, mutmut state
2. **Fork on each mutation**: Creates child worker via `os.fork()`
3. **Copy-on-Write (CoW)**: Initially shares parent memory pages
4. **Python refcounting problem**: Even "read" operations increment refcounts, causing page copies
5. **Memory growth**: Over 1000+ mutations, duplicated pages accumulate

This explains why memory grows over time (observed in Step 7 timing analysis).

### How Container Memory Limits Work

1. **GitHub Actions runners**: ~16 GB RAM for public repos
2. **Docker container**: Inherits host cgroup limits
3. **With systemd as init**: Creates additional cgroup hierarchy that enforces accounting
4. **Without systemd**: Looser memory enforcement, may allow overcommit

### Why OOM is Intermittent

The 20 GB peak memory usage is **on the edge of available resources**:
- 16 GB host RAM + 4 GB swap = 20 GB total
- Mutmut worker peak: ~19.3 GB (per Step 6)
- Variance in available RAM per runner: possibly ±1-2 GB
- Same code succeeds on "good" runners, OOM's on "bad" runners

### What changes between working and failing runs:

| Factor | Without systemd | With systemd |
|--------|-----------------|--------------|
| Container init | `tail -f /dev/null` | `/lib/systemd/systemd` |
| Result | ✅ Completes | ❌ OOM killed |
| Exit code | 0 | 143 |

### What stays the same:

- Same Docker image
- Same mutation test code
- Same transform domain
- Same `--max-children=1` setting
- Reported available memory stable at ~14 GB (host memory)

### Key Observations:

1. **Mutation rate degrades over time** (9/sec → 41 sec/mutation)
2. **Worker allocates ~20 GB** at time of OOM
3. **Swap nearly exhausted** when OOM occurs
4. **Works without systemd** in same container otherwise
5. **Works locally** with no memory issues
6. **MemAvailable monitoring shows host, not container memory**

---

## Original Unresolved Questions (Historical Record)

*These questions were documented before Steps 7-9. They are now addressed by the hypotheses below.*

1. **Why does `mutmut: wks.api` allocate ~20 GB?**
   - Is this normal for mutmut running 1166 mutations?
   - Does mutmut have a memory leak?
   - Are transform dependencies (tree-sitter, docling, sentence-transformers) loading large models?

2. **Why does OOM occur with systemd but not without?**
   - Does systemd configure cgroup memory limits differently?
   - Is our `MemAvailable` measurement (from `/proc/meminfo`) showing host memory instead of container limit?
   - Does systemd consume enough additional memory to push over the edge?

3. **Is memory accumulating or large from the start or a single mutation spikes it?**
   - Available memory stayed stable at ~14 GB throughout monitoring
   - No observed gradual decline
   - Worker may have allocated large amount early

---

## Hypotheses (Not Yet Proven)

### H1: Memory Accumulates Gradually Over 1040 Mutations

**Supporting evidence:**
- Dramatic slowdown pattern (9/sec → 41 sec/1 mutation)
- Slowdown characteristic of swap thrashing

**Counter-evidence:**
- MemAvailable showed stable ~14 GB (but this was host memory, not container)
- No per-mutation memory samples exist

**Status:** Plausible, but needs per-mutation memory profiling in CI

---

### H2: Systemd Cgroup Memory Accounting Causes Stricter OOM

**Supporting evidence:**
- Same tests pass without systemd
- OOM message shows `task_memcg=/system.slice/docker-.../init.scope`

**Counter-evidence:**
- None found

**Status:** Likely true, but doesn't explain why 20 GB is allocated

---

### H3: Tree-sitter Addition Pushed Baseline Over Edge

**Supporting evidence:**
- Issue started after `feat: enable transform (#38)` which added tree-sitter
- 17 tree-sitter language packages in dependencies
- Tree-sitter `_CACHE` persists loaded languages

**Counter-evidence:**
- Languages loaded lazily, not all 17 at once
- Docling existed before without issues

**Status:** Possible contributing factor, needs verification

---

### H4: Single Specific Mutation Causes Large Memory Spike

**Supporting evidence:**
- None

**Counter-evidence:**
- Slowdown is gradual, not sudden
- Failure occurs at consistent mutation number (~1040) across runs

**Status:** Unlikely based on timing pattern

---

## Next Steps (CI Experiments Needed)

### Experiment 1: Measure Cgroup Memory (Not Host Memory)

**Goal:** Get accurate container memory readings in CI.

**Method:** Replace `/proc/meminfo` reading with cgroup-aware measurement:
```python
# Cgroup v2
cat /sys/fs/cgroup/memory.current  # Current usage in bytes
cat /sys/fs/cgroup/memory.max      # Limit in bytes

# Cgroup v1 (fallback)
cat /sys/fs/cgroup/memory/memory.usage_in_bytes
```

**Expected outcome:** See actual container memory consumption over time.

---

### Experiment 2: Per-Mutation Memory Logging

**Goal:** Identify whether memory grows per mutation or stays flat.

**Method:** Modify mutmut or wrapper to log cgroup memory after each mutation.

**Expected outcome:** Graph of memory vs mutation number to confirm accumulation pattern.

---

### Experiment 3: Binary Search for Memory Growth Trigger

**Goal:** Identify which mutation range causes most memory growth.

**Method:** Run mutations in ranges (0-500, 500-1000, etc.) and compare final memory.

**Expected outcome:** Identify if specific files/mutations cause growth.

---

### Experiment 4: Compare Before/After Tree-sitter

**Goal:** Confirm whether tree-sitter addition correlates with OOM.

**Method:** Checkout commit before `feat: enable transform (#38)` and run same CI mutation tests.

**Expected outcome:** If OOM doesn't occur, tree-sitter is confirmed as contributing factor.

---

## Files Involved

- `.github/workflows/test.yml` - CI workflow
- `scripts/test_mutation_api.py` - Mutation test runner with resource logging
- `docker/Dockerfile.ci-runner` - CI Docker image

**⚠️ Temporary Modifications:**
The CI workflow on the `fix/mutation-timeout` branch has been modified to only run `transform` domain mutation tests (not all domains) for faster debugging iterations. This needs to be reverted before merging.

---

## List of GitHub Pages with Relevant Information

| Run | Description | Result |
|-----|-------------|--------|
| [20874385343](https://github.com/wawiesel/wks/actions/runs/20874385343) | With systemd + journalctl logging | ❌ OOM killed |
| [20874029042](https://github.com/wawiesel/wks/actions/runs/20874029042) | Without systemd (`tail -f /dev/null`) | ✅ Completed |
| [20873648465](https://github.com/wawiesel/wks/actions/runs/20873648465) | With systemd, verbose mutation output | ❌ OOM killed |
| [20873312581](https://github.com/wawiesel/wks/actions/runs/20873312581) | With systemd + depth limit fix | ❌ OOM killed |
