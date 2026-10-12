"""Random-value testing.

Substitutes random exact fractions for every variable and compares the two
sides. Rational results are compared exactly, so rounding can never cause a
false alarm; anything else (trig, logs, roots) is evaluated to 30 significant
digits and compared with a tight relative tolerance. Points where either side
is undefined or non-real are skipped, which automatically keeps the test
inside the valid domain of sqrt, log and division.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from sympy import Float, Rational, S, nan, oo, zoo

from .timeout import EngineTimeout, time_limit

PREC = 30
REL_TOL = Float("1e-15", PREC)
IMAG_TOL = Float("1e-20", PREC)


@dataclass
class NumericResult:
    outcome: str  # "same" | "different" | "inconclusive"
    witness: dict | None = None
    exact_witness: bool = False
    valid_points: int = 0


def make_rng(*seed_parts) -> random.Random:
    """Deterministic RNG so the same work always gets the same verdict."""
    return random.Random("|".join(str(p) for p in seed_parts))


def _random_value(rng: random.Random, positive: bool) -> Rational:
    r = rng.random()
    if positive:
        if r < 0.5:
            return Rational(rng.randint(1, 60), rng.randint(1, 9))
        return Rational(rng.randint(1, 12), rng.randint(1, 4))
    if r < 0.55:
        return Rational(rng.randint(-50, 50), rng.randint(1, 9))
    if r < 0.8:
        return Rational(rng.randint(-9, 9), rng.randint(1, 4))
    return Rational(rng.randint(1, 60), rng.randint(1, 9))


def value_at(expr, point: dict):
    """Value of ``expr`` at ``point``: an exact Rational, a Float, or None when undefined."""
    try:
        v = expr.xreplace(point) if point else expr
    except EngineTimeout:
        raise
    except Exception:
        return None
    try:
        if v.has(zoo, nan, oo, -oo, S.ComplexInfinity):
            return None
        if v.is_Rational:
            return v
        if v.free_symbols:
            return None
        c = v.evalf(PREC)
        if c.has(zoo, nan, oo, -oo):
            return None
        re_part, im_part = c.as_real_imag()
        if not (re_part.is_Number and im_part.is_Number):
            return None
        if abs(im_part) > IMAG_TOL * max(1, abs(re_part)):
            return None  # non-real: outside the real domain
        return Float(re_part, PREC)
    except EngineTimeout:
        raise
    except Exception:
        return None


def same_value(a, b) -> bool:
    if a.is_Rational and b.is_Rational:
        return a == b
    fa, fb = Float(a, PREC), Float(b, PREC)
    scale = max(Float(1, PREC), abs(fa), abs(fb))
    return abs(fa - fb) <= REL_TOL * scale


def numeric_compare(a, b, symbols, rng: random.Random, *, need: int = 8, max_tries: int = 48,
                    positive: bool = False, min_valid: int = 4, seconds: float = 1.5) -> NumericResult:
    """Compare two expressions at random points.

    "different" is definitive (a witness point is returned). "same" means every
    valid point agreed. "inconclusive" means too few points were defined.
    """
    syms = sorted(symbols, key=lambda s: s.name)
    valid = 0
    try:
        with time_limit(seconds):
            for _ in range(max_tries):
                point = {s: _random_value(rng, positive) for s in syms}
                va = value_at(a, point)
                if va is None:
                    continue
                vb = value_at(b, point)
                if vb is None:
                    continue
                valid += 1
                if not same_value(va, vb):
                    return NumericResult("different", point, va.is_Rational and vb.is_Rational, valid)
                if valid >= need:
                    return NumericResult("same", None, False, valid)
    except EngineTimeout:
        pass
    if valid >= min_valid:
        return NumericResult("same", None, False, valid)
    return NumericResult("inconclusive", None, False, valid)
