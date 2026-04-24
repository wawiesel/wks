import re

LOG_PATTERN = re.compile(r"^\[([^\]]+)\]\s*\[([^\]]+)\]\s*(DEBUG|INFO|WARN|ERROR):\s*(.*)$", re.IGNORECASE)
