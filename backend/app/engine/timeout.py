"""Time limits for SymPy calls.

SymPy can run for a very long time (or forever) on some inputs, so every
potentially slow call is wrapped in ``time_limit``. The limit uses
``SIGALRM``/``setitimer``, which only works in the main thread of a process.
The API runs the engine in worker processes (see ``app.worker``) where the
engine *is* the main thread, so limits are always enforced in production.
In other threads the limit degrades to a no-op instead of crashing.
"""

from __future__ import annotations

import contextlib
import signal
import threading
import time


class EngineTimeout(BaseException):
    """Raised when a time limit expires.

    Derives from BaseException (like KeyboardInterrupt) so that SymPy's own
    ``except Exception`` blocks cannot swallow it.
    """


def _can_use_alarm() -> bool:
    return hasattr(signal, "setitimer") and threading.current_thread() is threading.main_thread()


@contextlib.contextmanager
def time_limit(seconds: float | None):
    if not seconds or seconds <= 0 or not _can_use_alarm():
        yield
        return

    def _handler(signum, frame):  # pragma: no cover - exercised via tests indirectly
        raise EngineTimeout()

    start = time.monotonic()
    old_handler = signal.signal(signal.SIGALRM, _handler)
    outer_remaining, _ = signal.getitimer(signal.ITIMER_REAL)
    # Never extend an enclosing (outer) limit.
    if outer_remaining and outer_remaining < seconds:
        seconds = outer_remaining
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        if outer_remaining:
            left = outer_remaining - (time.monotonic() - start)
            signal.setitimer(signal.ITIMER_REAL, max(left, 0.001))


def limited(fn, seconds: float, default=None):
    """Run ``fn()`` under a time limit; return ``default`` on timeout or error."""
    try:
        with time_limit(seconds):
            return fn()
    except EngineTimeout:
        return default
    except Exception:
        return default


class Budget:
    """A wall-clock budget shared by all the steps of one check."""

    def __init__(self, seconds: float):
        self.deadline = time.monotonic() + seconds

    def remaining(self) -> float:
        return max(self.deadline - time.monotonic(), 0.0)

    def exhausted(self) -> bool:
        return self.remaining() <= 0.05

    def slice(self, seconds: float) -> float:
        """A per-call limit that never exceeds what's left of the budget."""
        return max(min(seconds, self.remaining()), 0.05)
