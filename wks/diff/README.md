# Diff Layer

Computes diffs across text/binary targets using pluggable engines. `controller.py` routes requests based on config from `config.py` and engine definitions in `engines.py`. Inputs can be file paths or transform checksums; keep logic here shared by CLI/MCP.
