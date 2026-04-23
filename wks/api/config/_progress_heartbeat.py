"""Utilities for relaying progress with periodic heartbeat updates."""

from __future__ import annotations

from collections.abc import Callable, Generator
from queue import Empty, Queue
from threading import Thread
from typing import Any, TypeVar

from .StageResult import StageResult

_T = TypeVar("_T")


def call_with_heartbeat(
    func: Callable[[], _T],
    *,
    progress: float,
    message: str,
    heartbeat_secs: float,
) -> Generator[tuple[float, str], None, _T]:
    """Yield heartbeat updates while waiting for one blocking function call."""
    result_queue: Queue[tuple[str, Any]] = Queue(maxsize=1)

    def worker() -> None:
        try:
            result_queue.put(("ok", func()))
        except BaseException as exc:  # pragma: no cover - exercised in runtime
            result_queue.put(("err", exc))

    if heartbeat_secs <= 0:
        yield (progress, message)
        return func()

    thread = Thread(target=worker, daemon=True)
    thread.start()
    elapsed = 0.0
    while True:
        try:
            status, payload = result_queue.get(timeout=heartbeat_secs)
        except Empty:
            elapsed += heartbeat_secs
            yield (progress, f"{message} ({elapsed:.0f}s elapsed)")
            continue
        if status == "err":
            raise payload
        return payload


def relay_stage_with_heartbeat(
    result_obj: StageResult,
    *,
    start_progress: float,
    end_progress: float,
    heartbeat_secs: float,
    idle_message: str,
    prefix: str = "",
) -> Generator[tuple[float, str], None, None]:
    """Relay a nested StageResult generator with periodic idle heartbeats."""
    progress_queue: Queue[tuple[str, Any]] = Queue()

    def worker() -> None:
        try:
            for child_progress, child_message in result_obj.progress_callback(result_obj):
                progress_queue.put(("progress", (child_progress, child_message)))
            progress_queue.put(("done", None))
        except BaseException as exc:  # pragma: no cover - exercised in runtime
            progress_queue.put(("err", exc))

    thread = Thread(target=worker, daemon=True)
    thread.start()
    span = end_progress - start_progress
    last_progress = start_progress
    elapsed = 0.0
    while True:
        try:
            status, payload = progress_queue.get(timeout=heartbeat_secs)
        except Empty:
            elapsed += heartbeat_secs
            yield (last_progress, f"{idle_message} ({elapsed:.0f}s elapsed)")
            continue
        if status == "err":
            raise payload
        if status == "done":
            return
        child_progress, child_message = payload
        last_progress = start_progress + span * float(child_progress)
        elapsed = 0.0
        display_message = f"{prefix}: {child_message}" if prefix else child_message
        yield (last_progress, display_message)
