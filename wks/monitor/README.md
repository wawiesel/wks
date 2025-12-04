# Monitor Layer

Tracks filesystem state and priorities. `controller.py` is the entry point; configs live in `config.py` and are validated via `validator.py`. Keep DB access and path rules here, not in CLI/MCP.
