"""Constants for vault link management (private)."""

# Spec-defined status values (vault.md Database Schema)
STATUS_OK = "ok"
STATUS_MISSING_SYMLINK = "missing_symlink"
STATUS_MISSING_TARGET = "missing_target"
STATUS_LEGACY_LINK = "legacy_link"  # Extension for backwards compat

# Internal document types for MongoDB
DOC_TYPE_LINK = "link"
DOC_TYPE_META = "meta"
META_DOCUMENT_ID = "__meta__"

# Internal link types for scanner
LINK_TYPE_WIKILINK = "wikilink"
LINK_TYPE_EMBED = "embed"
LINK_TYPE_MARKDOWN_URL = "markdown_url"

# Display limits
MAX_LINE_PREVIEW = 400
