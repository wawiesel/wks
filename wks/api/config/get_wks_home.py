import os
from pathlib import Path

from .normalize_path import normalize_path


def get_wks_home() -> Path:
    wks_home_env = os.environ.get("WKS_HOME")
    if wks_home_env:
        return normalize_path(wks_home_env)
    return Path.home() / ".wks"
