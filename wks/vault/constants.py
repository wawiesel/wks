"""Constants for vault link management."""

__all__ = [
    "DOC_TYPE_LINK",
    "DOC_TYPE_META",
    "META_DOCUMENT_ID",
    "STATUS_OK",
    "STATUS_MISSING_SYMLINK",
    "STATUS_MISSING_TARGET",
    "STATUS_LEGACY_LINK",
    "LINK_TYPE_WIKILINK",
    "LINK_TYPE_EMBED",
    "LINK_TYPE_MARKDOWN_URL",
    "TARGET_KIND_VAULT_NOTE",
    "TARGET_KIND_LEGACY_PATH",
    "TARGET_KIND_LINKS_SYMLINK",
    "TARGET_KIND_ATTACHMENT",
    "TARGET_KIND_EXTERNAL_URL",
    "MAX_LINE_PREVIEW",
]

# MongoDB document types
DOC_TYPE_LINK = "link"
DOC_TYPE_META = "meta"

# MongoDB special document IDs
META_DOCUMENT_ID = "__meta__"

# Link status values
STATUS_OK = "ok"
STATUS_MISSING_SYMLINK = "missing_symlink"
STATUS_MISSING_TARGET = "missing_target"
STATUS_LEGACY_LINK = "legacy_link"

# Link types
LINK_TYPE_WIKILINK = "wikilink"
LINK_TYPE_EMBED = "embed"
LINK_TYPE_MARKDOWN_URL = "markdown_url"

# Target kinds
TARGET_KIND_VAULT_NOTE = "vault_note"
TARGET_KIND_LEGACY_PATH = "legacy_path"
TARGET_KIND_LINKS_SYMLINK = "_links_symlink"
TARGET_KIND_ATTACHMENT = "attachment"
TARGET_KIND_EXTERNAL_URL = "external_url"

# Display limits
MAX_LINE_PREVIEW = 400
