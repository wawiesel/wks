from ..daemon.process_identity import pid_exists


def _pid_running(pid: int) -> bool:
    return pid_exists(pid)
