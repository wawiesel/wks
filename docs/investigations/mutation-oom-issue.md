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

## Collected Evidence Summary

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
- Reported available memory stable at ~14 GB

---

## Unresolved Questions

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
