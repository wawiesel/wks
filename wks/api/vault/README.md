# Vault Layer

Manages vault link graph and symlinks. `controller.py` and `status_controller.py` are entry points; `config.py` defines vault settings, `git_watcher.py` tracks repo changes, and `obsidian.py` handles the reference vault type. Keep URI-first handling and deterministic IDs here.
