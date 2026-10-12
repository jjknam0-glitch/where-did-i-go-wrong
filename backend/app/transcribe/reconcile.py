"""Read twice, compare meaning.

Each line is transcribed twice. Both readings are parsed into SymPy and
compared mathematically, not as strings (``x*2`` and ``2x`` agree). Agreement
means confident; disagreement marks the line uncertain and offers both
readings as one-tap choices. Lookalike letters (s/5, z/2, l/1, ...) are
flagged when they don't fit the rest of the problem.

These functions are pure and synchronous; the API runs them in the engine
worker processes.
"""

from __future__ import annotations

import re

from ..engine.equivalence import expr_equivalent_plain
from ..engine.parsing import CONSTANT_NAMES, looks_like_calculus, try_parse_line
from ..engine.render import line_to_latex
from ..engine.timeout import EngineTimeout

DIGIT_LOOKALIKES = {"s": "5", "S": "5", "z": "2", "Z": "2", "l": "1", "I": "1", "O": "0",
                    "o": "0", "b": "6", "g": "9", "q": "9", "B": "8", "G": "6"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").lower())


def readings_agree(a: dict | None, b: dict | None, natural_log: bool = False) -> bool:
    if not a or not b:
        return False
    if a["type"] == "note" or b["type"] == "note":
        return a["type"] == b["type"] and _norm(a["math"]) == _norm(b["math"])
    if _norm(a["math"]) == _norm(b["math"]):
        return True
    pa, _ = try_parse_line(a["math"], natural_log=natural_log)
    pb, _ = try_parse_line(b["math"], natural_log=natural_log)
    if pa is None or pb is None:
        return False
    if (len(pa.parts) != len(pb.parts) or pa.connective != pb.connective
            or pa.continuation != pb.continuation):
        return False
    try:
        for p, q in zip(pa.parts, pb.parts):
            if p.ops != q.ops or len(p.sides) != len(q.sides):
                return False
            if (p.label is None) != (q.label is None):
                return False
            if p.label is not None and (p.label.name, p.label.order) != (q.label.name, q.label.order):
                return False
            for s, t in zip(p.sides, q.sides):
                v = expr_equivalent_plain(s.expr, t.expr, allow_domain=False)
                if v.equal is not True:
                    return False
    except EngineTimeout:
        return False
    return True


def _letters(math: str, natural_log: bool) -> set:
    pl, _ = try_parse_line(math, natural_log=natural_log)
    if pl is None:
        return set()
    return {s.name for s in pl.symbols if len(s.name) == 1 and s.name not in CONSTANT_NAMES}


def _distinct(readings, natural_log):
    out = []
    for r in readings:
        if not r or not r.get("math"):
            continue
        if any(readings_agree(r, o, natural_log) for o in out):
            continue
        out.append(r)
    return out


def finalize(per_line: list[list[dict | None]], tiebreaks: list[dict | None] | None = None) -> list[dict]:
    """Combine the readings of every line into one transcription with a confidence."""
    tiebreaks = tiebreaks or [None] * len(per_line)
    all_text = [r["math"] for reads in per_line for r in reads if r]
    natural_log = looks_like_calculus(all_text)
    lines = []
    for reads, tb in zip(per_line, tiebreaks):
        a, b = (reads + [None, None])[:2]
        if readings_agree(a, b, natural_log):
            primary, conf, alts = a, "high", []
        else:
            candidates = [r for r in (tb, a, b) if r]
            if not candidates:
                lines.append({"type": "equation", "math": "", "latex": "", "confidence": "low",
                              "alternatives": [], "unreadable": True})
                continue
            primary = candidates[0]
            if tb and a and b:
                # Prefer the first read the strong model agrees with.
                for r in (a, b):
                    if readings_agree(tb, r, natural_log):
                        primary = r
                        break
            conf = "low"
            alts = [r["math"] for r in _distinct([a, b, tb], natural_log)]
        line = {"type": primary["type"], "math": primary["math"], "latex": primary.get("latex") or primary["math"],
                "confidence": conf, "alternatives": alts if len(alts) > 1 else []}
        if line["type"] != "note":
            pl, err = try_parse_line(line["math"], natural_log=natural_log)
            if pl is None:
                line["confidence"] = "low"
                line["parse_error"] = err
            else:
                ltx, _ = line_to_latex(line["math"], natural_log)
                if ltx and not line.get("latex"):
                    line["latex"] = ltx
        lines.append(line)
    flag_lookalikes(lines, natural_log)
    return lines


def flag_lookalikes(lines: list[dict], natural_log: bool = False) -> None:
    """A stray letter that looks like a digit is probably a misread digit."""
    letter_lines: dict = {}
    per_line_letters = []
    for i, l in enumerate(lines):
        letters = set() if l["type"] == "note" or not l["math"] else _letters(l["math"], natural_log)
        per_line_letters.append(letters)
        for ch in letters:
            letter_lines.setdefault(ch, set()).add(i)
    if not letter_lines:
        return
    main = {ch for ch, idx in letter_lines.items() if len(idx) >= 2}
    if not main:
        return
    for i, letters in enumerate(per_line_letters):
        for ch in letters:
            if ch in main or ch not in DIGIT_LOOKALIKES:
                continue
            l = lines[i]
            digit = DIGIT_LOOKALIKES[ch]
            fixed = re.sub(rf"(?<![A-Za-z]){re.escape(ch)}(?![A-Za-z])", digit, l["math"])
            if fixed == l["math"]:
                continue
            l["alternatives"] = list(dict.fromkeys([l["math"], fixed] + (l.get("alternatives") or [])))
            l["confidence"] = "low"
            l["lookalike"] = {"letter": ch, "digit": digit}
