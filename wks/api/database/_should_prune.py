from datetime import datetime, timezone

from ._get_last_prune_timestamp import _get_last_prune_timestamp


def _should_prune(database_name: str, prune_frequency_secs: float) -> bool:
    if prune_frequency_secs <= 0:
        return False

    last_prune = _get_last_prune_timestamp(database_name)
    if last_prune is None:
        return True  # Never pruned

    now = datetime.now(timezone.utc)
    elapsed = (now - last_prune).total_seconds()
    return elapsed >= prune_frequency_secs
