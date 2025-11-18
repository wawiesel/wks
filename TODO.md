# WKS Code Quality Improvements

**Priority**: Following `.cursor/rules/important.mdc` compliance

## IMMEDIATE (P0)

### 1. Split monitor_controller.py (1012 lines → <900)
**Status**: 🔴 IN PROGRESS
**Lines**: 1012 (exceeds 900 limit)
**CCN Violations**: 3 functions

**Plan**:
```
wks/monitor/
  __init__.py           # Public API exports
  config.py             # MonitorConfig dataclass
  validator.py          # MonitorValidator class + validation logic
  operations.py         # List operations (add/remove)
  controller.py         # MonitorController (orchestration)
  status.py             # MonitorStatus, ConfigValidationResult dataclasses
```

**Functions to move**:
- `config.py`: MonitorConfig (174-268), ValidationError (51-58)
- `validator.py`: MonitorValidator (60-121), validation helpers
- `operations.py`: add_to_list, remove_from_list, managed directory ops
- `status.py`: MonitorStatus, ConfigValidationResult, ManagedDirectoryInfo, ListOperationResult
- `controller.py`: MonitorController (orchestration only)

**Expected outcome**: Each file <300 lines

---

### 2. Refactor high-CCN functions (CCN > 10)

#### 2a. monitor_controller.validate_config() - CCN 27, NLOC 100
**Location**: monitor_controller.py:721
**Target**: CCN <10, NLOC <100

**Refactor plan**:
```python
# Extract to separate methods:
def _validate_path_conflicts(monitor_cfg, include_map, exclude_map) -> Tuple[List[str], List[str]]
def _validate_path_redundancy(monitor_cfg, include_map, exclude_map, config) -> List[str]
def _validate_managed_directories(monitor_cfg, rules) -> Tuple[List[str], Dict]
def _validate_dirnames(monitor_cfg) -> Tuple[List[str], List[str], Dict, Dict]
def _validate_globs(monitor_cfg) -> Tuple[List[str], Dict, Dict]

def validate_config(config: dict) -> ConfigValidationResult:
    """Orchestrate validation - CCN ~5"""
    monitor_cfg = MonitorConfig.from_config_dict(config)
    rules = MonitorRules.from_config(monitor_cfg)

    issues, redundancies = _validate_path_conflicts(...)
    redundancies.extend(_validate_path_redundancy(...))
    managed_issues, managed_dirs = _validate_managed_directories(...)
    ...
```

#### 2b. monitor_controller.__post_init__() - CCN 22, NLOC 30
**Location**: monitor_controller.py:189
**Target**: CCN <10

**Refactor plan**:
```python
def _validate_list_fields(self) -> List[str]
def _validate_database_format(self) -> List[str]
def _validate_numeric_fields(self) -> List[str]

def __post_init__(self):
    errors = []
    errors.extend(self._validate_list_fields())
    errors.extend(self._validate_database_format())
    errors.extend(self._validate_numeric_fields())
    if errors:
        raise ValidationError(errors)
```

#### 2c. mongoctl.ensure_mongo_running() - CCN 20, NLOC 75
**Location**: mongoctl.py:72
**Target**: CCN <10

**Refactor plan**:
```python
def _check_mongo_running(uri: str) -> bool
def _start_local_mongod(host: str, port: int, dbpath: Path, logfile: Path, pidfile: Path) -> int
def _wait_for_mongo_ready(uri: str, deadline: float) -> bool
def _record_managed_mongo(pid: int) -> None

def ensure_mongo_running(uri: str, *, record_start: bool = False) -> None:
    if _check_mongo_running(uri):
        return
    local = local_node(uri)
    if not local or not shutil.which("mongod"):
        raise SystemExit(2)

    host, port = local
    pid = _start_local_mongod(...)
    if not _wait_for_mongo_ready(uri, time.time() + 5.0):
        raise SystemExit(2)
    if record_start:
        _record_managed_mongo(pid)
```

#### 2d. monitor_controller.add_to_list() - CCN 18, NLOC 59
**Location**: monitor_controller.py:378
**Target**: CCN <10

**Refactor plan** - Use Strategy Pattern:
```python
class ListAddStrategy:
    def normalize_value(self, value: str) -> Tuple[str, str]: ...
    def validate_value(self, value: str) -> Tuple[bool, Optional[str]]: ...
    def check_conflicts(self, config: dict, value: str) -> Optional[str]: ...

class PathListStrategy(ListAddStrategy): ...
class DirnameListStrategy(ListAddStrategy): ...
class GlobListStrategy(ListAddStrategy): ...

STRATEGIES = {
    "include_paths": PathListStrategy(resolve=True),
    "exclude_paths": PathListStrategy(resolve=True),
    "include_dirnames": DirnameListStrategy(),
    ...
}

def add_to_list(config_dict: dict, list_name: str, value: str) -> ListOperationResult:
    strategy = STRATEGIES[list_name]
    value_resolved, value_to_store = strategy.normalize_value(value)
    is_valid, error = strategy.validate_value(value_resolved)
    ...  # Much simpler logic
```

#### 2e. daemon._acquire_lock() - CCN 16, NLOC 37
**Location**: daemon.py:794
**Target**: CCN <10

**Refactor plan**:
```python
def _clean_stale_lock(lock_file: Path) -> None
def _acquire_lock_fcntl(lock_file: Path) -> Optional[Any]
def _acquire_lock_pidfile(lock_file: Path) -> None

def _acquire_lock(self):
    self.lock_file.parent.mkdir(parents=True, exist_ok=True)
    _clean_stale_lock(self.lock_file)

    if fcntl is None:
        _acquire_lock_pidfile(self.lock_file)
    else:
        self._lock_fh = _acquire_lock_fcntl(self.lock_file)
```

---

### 3. Replace print() with logger (169 violations)

**Rule**:
- Info/debug → `logger.info()` / `logger.debug()` (logs only)
- Warnings/errors → `logger.warning()` / `logger.error()` (logs + STDERR in CLI)
- CLI output → STDOUT only
- MCP mode → warnings/errors in JSON

**Files needing refactor** (by print count):
1. wks/error_messages.py: 66 prints
2. wks/cli/commands/index.py: 26 prints
3. wks/__main__.py: 12 prints
4. wks/display/cli.py: 11 prints
5. wks/cli/commands/service.py: 11 prints
6. wks/daemon.py: 9 prints
7. wks/cli/commands/monitor.py: 8 prints
8. wks/cli/commands/vault.py: 6 prints
9. wks/mongoctl.py: 5 prints
10. wks/cli/display_strategies.py: 4 prints
11. wks/monitor.py: 4 prints

**Approach**:
```python
# Before
print("WKS daemon started")

# After
logger.info("WKS daemon started")
if display_mode == "cli":
    sys.stderr.write("WKS daemon started\n")
```

**Helper function**:
```python
def emit_status(message: str, level: str = "info", display=None):
    """Emit status message to logger and optionally to CLI STDERR."""
    getattr(logger, level)(message)
    if display and hasattr(display, 'emit_status'):
        display.emit_status(message)
```

---

## HIGH PRIORITY (P1)

### 4. Convert config.py to dataclasses

**Current issues**:
- `mongo_settings()` returns dict (line 17-41)
- `load_config()` returns raw dict (line 80-107)
- No validation on load

**Target structure**:
```python
@dataclass
class MongoSettings:
    uri: str
    space_database: str
    space_collection: str
    time_database: str
    time_collection: str

    def __post_init__(self):
        if not self.uri or not self.uri.startswith("mongodb://"):
            raise ValueError(f"db.uri must start with 'mongodb://' (found: {self.uri!r})")
        if not self.space_database:
            raise ValueError("related.engines.embedding.database is required")
        # ... all validations

@dataclass
class VaultConfig:
    base_dir: Path
    wks_dir: str
    update_frequency_seconds: int
    database: str

    def __post_init__(self):
        if not self.base_dir.exists():
            raise ValueError(f"vault.base_dir does not exist: {self.base_dir}")
        # ... all validations

@dataclass
class WKSConfig:
    vault: VaultConfig
    monitor: MonitorConfig
    db: DbConfig
    mongo: MongoSettings
    similarity: Optional[SimilarityConfig] = None

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "WKSConfig":
        """Load and validate config from file."""
        if path is None:
            path = get_config_path()

        with open(path) as f:
            raw = json.load(f)

        # Construct with validation
        return cls(
            vault=VaultConfig(**raw["vault"]),
            monitor=MonitorConfig.from_config_dict(raw),
            ...
        )
```

**Files to update**:
- wks/config.py
- wks/daemon.py
- wks/__main__.py
- All CLI commands

---

### 5. Implement CLI output protocol (Rule 30)

**Rule**: Every CLI command must:
1. STDERR: "Doing X..."
2. STDERR: Progress bar
3. STDERR: "Done. Problems: Y"
4. STDOUT: Result only

**Implementation**:
```python
class CLICommand:
    def execute(self, args):
        # 1. Say what we're doing
        self.display.status(f"Loading {self.name}...")

        # 2. Show progress
        with self.display.progress(total=steps) as prog:
            for step in steps:
                prog.update(step.name)
                step.execute()

        # 3. Report completion
        if errors:
            self.display.status(f"Done. {len(errors)} problems found", level="warning")
        else:
            self.display.status("Done.", level="success")

        # 4. Output result to STDOUT
        sys.stdout.write(result)
```

**Files to update**:
- All CLI command files in wks/cli/commands/

---

## MEDIUM PRIORITY (P2)

### 6. Centralize error handling with structured aggregation

**Current state**:
- monitor_controller.py: Good aggregation
- config_validator.py: Good aggregation
- daemon.py: Individual errors only

**Target**: All subsystems collect errors, then raise once

**Example**:
```python
class ErrorCollector:
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def add_error(self, msg: str):
        self.errors.append(msg)
        logger.error(msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)
        logger.warning(msg)

    def raise_if_errors(self):
        if self.errors:
            raise ValidationError(self.errors)
```

---

### 7. Add lizard to CI

**Steps**:
1. Add lizard to dev dependencies
2. Create `.lizard.yml` config:
   ```yaml
   CCN: 10
   length: 100
   arguments: 5
   warnings_only: true
   exclude: "*/tests/*,*/.venv/*"
   ```
3. Add to CI pipeline:
   ```yaml
   - name: Check code complexity
     run: lizard wks/ --CCN 10 --length 100
   ```

---

## TRACKING

**Total violations**:
- ❌ 5 CCN violations (CCN > 10)
- ❌ 1 file size violation (>900 lines)
- ❌ 169 print() statements (should be logger)
- ❌ 2 dict-based config functions (should be dataclass)

**Target**:
- ✅ All functions CCN ≤ 10
- ✅ All files ≤ 900 lines
- ✅ All output via logger (not print)
- ✅ All config via dataclasses (not dicts)

---

**Last updated**: 2025-11-18
