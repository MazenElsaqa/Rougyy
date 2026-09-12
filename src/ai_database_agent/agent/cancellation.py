"""
Cooperative cancellation for in-flight pipeline runs.

Python threads can't be killed, and the pipeline is synchronous, so
true preemption isn't possible -- but we can stop *waiting* wisely:
the frontend aborts its fetch (instant UI feedback) and tells the
backend to cancel via POST /cancel. The pipeline checks the flag
before every LLM call and between retry attempts; on cancel it stops
immediately with a "Cancelled." result that is never recorded into
conversation memory.

Flags are keyed by backend session_id. A new ask() clears any stale
flag for its session first, so an old cancel can never block a new
question.
"""
from __future__ import annotations

import threading

_lock = threading.Lock()
_flags: dict[str, threading.Event] = {}


def cancel_session(session_id: str | None) -> None:
    if not session_id:
        return
    with _lock:
        _flags.setdefault(session_id, threading.Event()).set()


def clear_session(session_id: str | None) -> None:
    if not session_id:
        return
    with _lock:
        _flags.pop(session_id, None)


def is_cancelled(session_id: str | None) -> bool:
    if not session_id:
        return False
    with _lock:
        event = _flags.get(session_id)
        return event.is_set() if event is not None else False
