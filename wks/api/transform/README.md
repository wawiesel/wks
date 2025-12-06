# Transform Layer

Converts binary files to text/markdown with caching keyed by checksum. `controller.py` coordinates engines, options, and cache lookup; configs live in `config.py`. Avoid CLI/MCP logic here—return structured results for higher layers.
