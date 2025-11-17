"""Constants for CLI commands."""

from ..constants import WKS_HOME_EXT, WKS_EXTRACT_EXT, WKS_HOME_DISPLAY

DEFAULT_MONITOR_INCLUDE_PATHS = ["~"]
DEFAULT_MONITOR_EXCLUDE_PATHS = ["~/Library", f"{WKS_HOME_DISPLAY}"]
DEFAULT_MONITOR_IGNORE_DIRS = [".git", "_build", WKS_HOME_EXT, WKS_EXTRACT_EXT]
DEFAULT_MONITOR_IGNORE_GLOBS = ["*.tmp", "*~", "._*"]

DEFAULT_OBSIDIAN_CONFIG = {
    "base_dir": "WKS",
    "log_max_entries": 500,
    "active_files_max_rows": 50,
    "source_max_chars": 40,
    "destination_max_chars": 40,
    "docs_keep": 99,
}

DEFAULT_SIMILARITY_EXTS = [
    ".md",
    ".txt",
    ".py",
    ".ipynb",
    ".tex",
    ".docx",
    ".pptx",
    ".pdf",
    ".html",
    ".csv",
    ".xlsx",
]

# Supported display modes
DISPLAY_CHOICES = ["cli", "mcp"]

DB_QUERY_MARKDOWN_TEMPLATE = """### {{ scope|capitalize }} query — {{ collection }}
{% if rows %}
| # | Document |
| --- | --- |
{% for row in rows %}
| {{ loop.index }} | {{ row | replace('|', '\\|') }} |
{% endfor %}
{% else %}
_No documents found._
{% endif %}
""".strip()
