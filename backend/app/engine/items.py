"""Comparable "items" built from parsed lines.

A line can hold one or more items (``a = b = c`` written as a chain holds
several). Consecutive items are compared to find the first broken step.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sympy import Expr, latex


@dataclass
class Item:
    kind: str  # "expr" | "eq" | "rel" | "or" | "sys"
    line: int
    expr: Expr | None = None
    raw: Expr | None = None
    lhs: Expr | None = None
    rhs: Expr | None = None
    raw_lhs: Expr | None = None
    raw_rhs: Expr | None = None
    sides: list = field(default_factory=list)
    raw_sides: list = field(default_factory=list)
    ops: list = field(default_factory=list)
    eqs: list = field(default_factory=list)
    label: tuple | None = None  # (name, derivative order)

    # ---- constructors -------------------------------------------------
    @staticmethod
    def expression(line, expr, raw=None, label=None):
        return Item("expr", line, expr=expr, raw=raw if raw is not None else expr, label=label)

    @staticmethod
    def equation(line, lhs, rhs, raw_lhs=None, raw_rhs=None):
        return Item("eq", line, lhs=lhs, rhs=rhs,
                    raw_lhs=raw_lhs if raw_lhs is not None else lhs,
                    raw_rhs=raw_rhs if raw_rhs is not None else rhs)

    @staticmethod
    def relation(line, sides, ops, raw_sides=None):
        return Item("rel", line, sides=list(sides), ops=list(ops),
                    raw_sides=list(raw_sides) if raw_sides is not None else list(sides))

    @staticmethod
    def disjunction(line, eqs):
        return Item("or", line, eqs=list(eqs))

    @staticmethod
    def system(line, eqs):
        return Item("sys", line, eqs=list(eqs))

    # ---- helpers --------------------------------------------------------
    def with_sides(self, lhs, rhs):
        """A copy of an equation item with new (evaluated) sides."""
        return Item.equation(self.line, lhs, rhs, lhs, rhs)

    def to_latex(self) -> str:
        if self.kind == "expr":
            return rtex(self.raw if self.raw is not None else self.expr)
        if self.kind == "eq":
            return f"{rtex(self.raw_lhs)} = {rtex(self.raw_rhs)}"
        if self.kind == "rel":
            out = rtex(self.raw_sides[0])
            for op, s in zip(self.ops, self.raw_sides[1:]):
                out += f" {REL_TEX[op]} {rtex(s)}"
            return out
        if self.kind == "or":
            return r" \text{ or } ".join(e.to_latex() for e in self.eqs)
        if self.kind == "sys":
            return r",\quad ".join(e.to_latex() for e in self.eqs)
        return ""


REL_TEX = {"=": "=", "<": "<", ">": ">", "<=": r"\le", ">=": r"\ge"}
FLIP = {"<": ">", ">": "<", "<=": ">=", ">=": "<=", "=": "="}


def tex(e) -> str:
    """LaTeX for an evaluated expression (terms in the usual order)."""
    try:
        return latex(e)
    except Exception:
        return str(e)


def rtex(e) -> str:
    """LaTeX for an unevaluated (as-written) tree.

    SymPy doesn't keep the written order of terms in a sum, so the usual
    descending order is used for both evaluated and as-written trees.
    """
    return tex(e)
