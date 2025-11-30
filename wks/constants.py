"""Shared constants for WKS dot-directories and artefact locations."""

WKS_HOME_EXT = ".wks"   # user-level state/config directory suffix

WKS_HOME_DISPLAY = f"~/{WKS_HOME_EXT}"  # user-readable path hint

# Convenience set for directories that should be auto-ignored in scans
WKS_DOT_DIRS = {WKS_HOME_EXT}

# Display width constant - standardize to 80 characters max
MAX_DISPLAY_WIDTH = 80

# Default timestamp format for display
DEFAULT_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
