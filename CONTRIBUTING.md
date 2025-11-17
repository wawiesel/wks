# Repository Guidelines

## Project Structure & Module Organization
- Source: `wks/` (Python package)
  - `cli.py` (console entry `wks`), `daemon.py` (background agent), `obsidian.py` (vault ops), `monitor.py` (FS watch), `similarity.py` (embeddings/MongoDB), `links.py`, `activity.py`, `__main__.py`.
- Packaging: `setup.py` (installs `wks` console script).
- Docs: `README.md`, `SPEC.md`, `ROADMAP.md`, `TASKS.md`.
- Scripts: `scripts/` (utility placeholders).

## Build, Test, and Development Commands
- Create env: `python -m venv venv && source venv/bin/activate`
- Install editable: `pip install -e .`
- CLI help: `wks -h`
- Daemon: `wks service start | stop | status | restart`
- Analyze/similarity: `wks analyze index <paths...>`, `wks analyze query ...`, `wks analyze route --path <file>`

## Coding Style & Naming Conventions
- Python ≥ 3.8; PEP 8; 4 spaces; type hints preferred.
- `snake_case` (functions/vars), `PascalCase` (classes), `UPPER_SNAKE` (constants).
- Keep modules focused; avoid cross‑cutting side effects.
- If you use Black/Ruff locally, avoid unrelated mass reformatting.

## Testing Guidelines
- Use `pytest`; add tests under `tests/`, named `test_*.py`.
- Prefer pure functions; mock filesystem/IO; avoid touching `~/_vault` or `~/.wks`.
- Aim for reasonable coverage on changed code; document a brief test plan in PRs.

## Commit & Pull Request Guidelines
- Conventional Commits (`feat:`, `fix:`, `chore:`). Keep scope small.
- PRs include: summary, motivation, linked issues/tasks, and CLI examples; screenshots optional for vault artifacts.
- Avoid destructive defaults; gate with flags and document safeguards.
- Update relevant docs (`SPEC.md`, `TASKS.md`) when changing behavior/workflows.

## Security & Configuration Tips
- User config: `~/.wks/config.json` (e.g., `obsidian.base_dir`, monitor paths, similarity settings). Never commit secrets.
- Default Mongo: `mongodb://localhost:27017/` (any single-host loopback URI auto-starts when `mongod` is available). Support offline models where possible.
- Respect ignore settings; never write outside the configured vault base dir.
