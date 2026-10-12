"""Keep AI-phrased explanations honest.

An AI model may rephrase the engine's facts in friendlier words, but every
equation in its text is extracted and checked with SymPy before a student
sees it. An equation is allowed only if it is

* a true numeric fact (``7 - 3 = 4``),
* equivalent to the previous (correct) line - i.e. a valid next step,
* the corrected step itself, or
* a quote of the student's own line.

Anything else makes the explanation fail verification.
"""

from __future__ import annotations

import re

from .equivalence import expr_equivalent_plain, relation_equivalent
from .items import Item
from .parsing import try_parse_line
from .timeout import EngineTimeout

MATH_RE = re.compile(r"\$([^$]+)\$")


def _line_item(text: str):
    pl, err = try_parse_line(text)
    if pl is None or len(pl.parts) != 1:
        return None
    p = pl.parts[0]
    if p.is_equation and len(p.sides) == 2:
        return Item.equation(0, p.sides[0].expr, p.sides[1].expr)
    if p.is_expression:
        return Item.expression(0, p.sides[0].expr)
    return None


def equations_in(text: str) -> list[str]:
    return [m.group(1) for m in MATH_RE.finditer(text) if "=" in m.group(1)]


def verify_explanation(text: str, previous: str, student: str, corrected: str | None,
                       var_name: str = "x") -> bool:
    """True if every equation in ``text`` checks out against the step's facts."""
    from sympy import Symbol
    var = Symbol(var_name)
    allowed = []
    for ref in (previous, student, corrected):
        if ref:
            it = _line_item(ref)
            if it is not None:
                allowed.append(it)
    for eq in equations_in(text):
        item = _line_item(eq)
        if item is None:
            return False
        try:
            if item.kind == "eq" and not item.lhs.free_symbols and not item.rhs.free_symbols:
                if not expr_equivalent_plain(item.lhs, item.rhs, allow_domain=False).equal:
                    return False
                continue
            ok = False
            for ref in allowed:
                if ref.kind == "eq" and item.kind == "eq":
                    if relation_equivalent(ref, item, var).equal:
                        ok = True
                        break
                    # quoting the student's line exactly (same sides)
                    if expr_equivalent_plain(ref.lhs, item.lhs, allow_domain=False).equal and \
                            expr_equivalent_plain(ref.rhs, item.rhs, allow_domain=False).equal:
                        ok = True
                        break
            if not ok:
                return False
        except EngineTimeout:
            return False
    return True
