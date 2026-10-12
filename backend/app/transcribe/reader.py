"""Transcribe line crops: two parallel reads per line, a stronger tiebreak read
only where they disagree, then reconciliation."""

from __future__ import annotations

import asyncio

from .providers import resolve_models
from .reconcile import finalize, readings_agree


async def read_lines(crops: list[bytes], run_sync) -> list[dict] | None:
    """Transcribe each crop. ``run_sync(fn, *args)`` runs CPU work off the event loop.

    Returns None when no transcription provider is configured.
    """
    reads, tiebreak = resolve_models()
    if not reads:
        return None
    if len(reads) == 1:
        reads = [reads[0], reads[0]]

    # All lines, both reads, in parallel: a 6-line problem takes about one call's time.
    calls = [prov.transcribe(crop, model) for crop in crops for prov, model in reads]
    results = await asyncio.gather(*calls, return_exceptions=True)
    results = [r if isinstance(r, dict) else None for r in results]
    per_line = [[results[2 * i], results[2 * i + 1]] for i in range(len(crops))]

    agree = await run_sync(_agreement, per_line)
    tiebreaks: list = [None] * len(crops)
    if tiebreak is not None:
        need = [i for i, ok in enumerate(agree) if not ok]
        if need:
            prov, model = tiebreak
            extra = await asyncio.gather(*[prov.transcribe(crops[i], model) for i in need],
                                         return_exceptions=True)
            for i, r in zip(need, extra):
                tiebreaks[i] = r if isinstance(r, dict) else None
    return await run_sync(finalize, per_line, tiebreaks)


def _agreement(per_line):
    return [readings_agree(a, b) for a, b in per_line]
