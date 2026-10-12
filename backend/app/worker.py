"""Run CPU-heavy work (SymPy, OpenCV) in worker processes.

Inside a worker the engine runs on the main thread, so its SIGALRM time
limits (2 s per SymPy call) are enforced. An outer timeout protects the API
if a worker ever stalls; a stalled or crashed pool is replaced.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import multiprocessing as mp
import threading
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool

from . import config

log = logging.getLogger(__name__)

_executor: ProcessPoolExecutor | None = None
_lock = threading.Lock()


class EngineBusy(Exception):
    """The engine didn't finish in time."""


def _warm():
    # Import the heavy modules once per worker so the first request is fast.
    import sympy  # noqa: F401

    from .engine import checker  # noqa: F401
    from .vision import pipeline  # noqa: F401
    checker.check_lines([{"index": 0, "math": "2x + 1 = 3"}, {"index": 1, "math": "x = 1"}])


def _get_executor() -> ProcessPoolExecutor | None:
    global _executor
    if config.ENGINE_WORKERS <= 0:
        return None
    with _lock:
        if _executor is None:
            ctx = mp.get_context("spawn")
            _executor = ProcessPoolExecutor(max_workers=config.ENGINE_WORKERS, mp_context=ctx,
                                            initializer=_warm)
        return _executor


def _reset_executor():
    global _executor
    with _lock:
        ex, _executor = _executor, None
    if ex is not None:
        procs = list((getattr(ex, "_processes", None) or {}).values())
        try:
            ex.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        # Make sure stuck workers don't linger.
        for p in procs:
            try:
                p.kill()
            except Exception:
                pass


async def run(fn, *args, timeout: float | None = None, **kwargs):
    """Run ``fn(*args, **kwargs)`` in a worker process and await the result."""
    timeout = timeout or config.CHECK_TIMEOUT
    loop = asyncio.get_running_loop()
    call = functools.partial(fn, *args, **kwargs)
    ex = _get_executor()
    if ex is None:
        return await asyncio.wait_for(loop.run_in_executor(None, call), timeout)
    try:
        return await asyncio.wait_for(loop.run_in_executor(ex, call), timeout)
    except asyncio.TimeoutError:
        log.warning("engine call timed out; restarting workers")
        _reset_executor()
        raise EngineBusy()
    except BrokenProcessPool:
        log.warning("engine pool broke; restarting workers")
        _reset_executor()
        ex = _get_executor()
        try:
            return await asyncio.wait_for(loop.run_in_executor(ex, call), timeout)
        except (asyncio.TimeoutError, BrokenProcessPool):
            _reset_executor()
            raise EngineBusy()


def warm_up():
    """Start the pool and warm every worker (called at app start-up)."""
    ex = _get_executor()
    if ex is None:
        return
    futures = [ex.submit(_noop) for _ in range(config.ENGINE_WORKERS)]
    for f in futures:
        try:
            f.result(timeout=120)
        except Exception:
            pass


def _noop():
    return True


def shutdown():
    _reset_executor()
