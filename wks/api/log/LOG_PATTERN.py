import re

# Pattern to parse [ISO_TIMESTAMP] [DOMAIN] LEVEL: message
LOG_PATTERN = re.compile(r"^\[([^\]]+)\]\s*\[(\w+)\]\s*(DEBUG|INFO|WARN|ERROR):\s*(.*)$", re.IGNORECASE)
