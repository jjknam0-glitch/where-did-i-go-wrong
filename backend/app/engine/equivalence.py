"""Step verification: is line B a valid consequence of line A?

Two checks always run together (spec: "Two checks together"):

* a numeric test with random exact fractions - fast and decisive when the two
  sides differ, and
* a symbolic test (simplify / solveset) under a 2-second limit - exact
  confirmation when they agree.

Verdicts carry a trust tier: ``verified`` (proved exactly) or ``numeric``
(passed random testing only). ``equal=None`` means "couldn't verify" and is
always preferred over a guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sympy import (
    Abs, Add, Complement, ConditionSet, Derivative, EmptySet, Expr, FiniteSet, ImageSet,
    Integral, Intersection, Interval, Limit, Mul, Rational, S, Symbol, Union, cancel, diff,
    expand, expand_log, factor, logcombine, nsimplify, simplify, solve, solveset, together,
    trigsimp,
)
from sympy.core.relational import Relational

from .numeric import make_rng, numeric_compare, value_at
from .parsing import is_constant_symbol
from .timeout import EngineTimeout, limited, time_limit

SYMBOLIC_SECONDS = 2.0


@dataclass
class Verdict:
    equal: bool | None
    tier: str | None = None  # "verified" | "numeric"
    reason: str = ""
    witness: dict | None = None
    lost: list = field(default_factory=list)
    gained: list = field(default_factory=list)
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.equal is True


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def has_calculus(e) -> bool:
    return bool(e.atoms(Derivative, Integral, Limit))


def indefinite_integrals(e) -> list:
    return [i for i in e.atoms(Integral) if any(len(lim) == 1 for lim in i.limits)]


def strip_constants(syms) -> set:
    return {s for s in syms if not is_constant_symbol(s)}


def evaluate_operators(e, seconds: float = SYMBOLIC_SECONDS):
    """Evaluate Derivative / Limit / definite Integral nodes. Returns (expr, tier) or (None, reason)."""
    if not e.has(Derivative, Limit, Integral):
        return e, "verified"
    tier = "verified"

    def _do():
        return e.doit()

    out = limited(_do, seconds, None)
    if out is None:
        return None, "timeout"
    if out.has(Limit):
        return None, "limit_unevaluated"
    # Definite integrals that SymPy can't do in closed form: fall back to numbers.
    leftover = [i for i in out.atoms(Integral) if all(len(lim) == 3 for lim in i.limits)]
    if leftover:
        try:
            with time_limit(seconds):
                out = out.xreplace({i: i.evalf(30) for i in leftover})
            tier = "numeric"
        except (EngineTimeout, Exception):
            return None, "timeout"
    if out.has(Derivative):
        return None, "derivative_unevaluated"
    return out, tier


def symbolic_zero(d, seconds: float = SYMBOLIC_SECONDS) -> bool | None:
    """True if d is proved identically zero; False if not proved; None on timeout."""
    if d == 0:
        return True
    try:
        with time_limit(seconds):
            for f in (expand, cancel, together):
                if f(d) == 0:
                    return True
            if d.atoms(*_TRIG):
                t = trigsimp(d)
                if t == 0 or expand(t) == 0:
                    return True
            if d.atoms(*_LOG):
                l = expand_log(d, force=True)
                if l == 0 or simplify(l) == 0:
                    return True
                if logcombine(d, force=True) == 0:
                    return True
            s = simplify(d)
            if s == 0:
                return True
            if expand(s) == 0:
                return True
            return False
    except EngineTimeout:
        return None
    except Exception:
        return False


def _trig_classes():
    from sympy import cos, cot, csc, sec, sin, tan
    return (sin, cos, tan, sec, csc, cot)


def _log_classes():
    from sympy import exp, log
    return (log, exp)


_TRIG = _trig_classes()
_LOG = _log_classes()


# --------------------------------------------------------------------------
# expressions
# --------------------------------------------------------------------------

def expr_equivalent_plain(a, b, *, seed="", allow_domain=True) -> Verdict:
    """Are expressions a and b equal wherever both are defined?"""
    syms = a.free_symbols | b.free_symbols
    rng = make_rng("expr", seed, a, b)
    res = numeric_compare(a, b, syms, rng)
    if res.outcome == "different":
        if allow_domain and syms:
            res_pos = numeric_compare(a, b, syms, make_rng("pos", seed, a, b), positive=True)
            if res_pos.outcome == "same":
                proved = symbolic_zero(_positive_version(a - b, syms))
                return Verdict(True, "verified" if proved else "numeric", reason="domain_positive",
                               witness=res.witness)
        return Verdict(False, "verified" if res.exact_witness else "numeric", witness=res.witness)
    proved = symbolic_zero(a - b)
    if res.outcome == "same":
        return Verdict(True, "verified" if proved else "numeric")
    if proved:
        return Verdict(True, "verified")
    return Verdict(None, reason="inconclusive")


def _positive_version(e, syms):
    reps = {s: Symbol(s.name, positive=True) for s in syms}
    return e.xreplace(reps)


def apply_substitutions(e, subs: dict, var):
    """Map substitution variables back (u = g(x)), including ∫ f(u) du -> ∫ f(g) g' dx."""
    if not subs:
        return e
    def fix_integral(i):
        f = i.function
        new_limits = []
        for lim in i.limits:
            v = lim[0]
            if v in subs and len(lim) == 1:
                g = subs[v]
                f = f.xreplace({v: g}) * diff(g, var)
                new_limits.append((var,))
            else:
                new_limits.append(lim)
        return Integral(f, *new_limits)
    e = e.replace(lambda n: isinstance(n, Integral), fix_integral)
    return e.xreplace(subs)


def expr_equivalent(a, b, var, *, subs=None, seed="") -> Verdict:
    """Expression step check, aware of derivatives, integrals and limits."""
    subs = subs or {}
    a = apply_substitutions(a, subs, var)
    b = apply_substitutions(b, subs, var)

    if indefinite_integrals(a) or indefinite_integrals(b):
        for integral in indefinite_integrals(a) + indefinite_integrals(b):
            for lim in integral.limits:
                if lim[0] != var:
                    return Verdict(None, reason="substitution")
        # Antiderivatives are equal up to a constant iff their derivatives are equal.
        da = limited(lambda: diff(a, var), SYMBOLIC_SECONDS, None)
        db = limited(lambda: diff(b, var), SYMBOLIC_SECONDS, None)
        if da is None or db is None:
            return Verdict(None, reason="timeout")
        da, ta = evaluate_operators(da)
        db, tb = evaluate_operators(db)
        if da is None or db is None:
            return Verdict(None, reason=ta if da is None else tb)
        v = expr_equivalent_plain(da, db, seed=seed)
        v.note = v.note or "antiderivative"
        if v.equal and "numeric" in (ta, tb):
            v.tier = "numeric"
        return v

    a2, ta = evaluate_operators(a)
    b2, tb = evaluate_operators(b)
    if a2 is None or b2 is None:
        return Verdict(None, reason=ta if a2 is None else tb)
    v = expr_equivalent_plain(a2, b2, seed=seed)
    if v.equal and "numeric" in (ta, tb):
        v.tier = "numeric"
    return v


# --------------------------------------------------------------------------
# solution sets (equations and inequalities in one variable)
# --------------------------------------------------------------------------

def relation_set(lhs, rhs, op, var, seconds=SYMBOLIC_SECONDS):
    """Real solution set of ``lhs op rhs``. None if SymPy can't produce a usable set."""
    from sympy import Eq, Ge, Gt, Le, Lt
    rel = {"=": Eq, "<": Lt, ">": Gt, "<=": Le, ">=": Ge}[op]

    def _solve():
        if op == "=":
            return solveset(lhs - rhs, var, S.Reals)
        return solveset(rel(lhs, rhs), var, S.Reals)

    out = limited(_solve, seconds, None)
    if out is None or isinstance(out, ConditionSet) or out.has(ConditionSet):
        return None
    return out


def solution_set(item, var, seconds=SYMBOLIC_SECONDS):
    """Real solution set of an equation / inequality chain / disjunction item."""
    kind = item.kind
    if kind == "eq":
        return relation_set(item.lhs, item.rhs, "=", var, seconds)
    if kind == "rel":
        result = S.Reals
        for i, op in enumerate(item.ops):
            s = relation_set(item.sides[i], item.sides[i + 1], op, var, seconds)
            if s is None:
                return None
            result = limited(lambda: Intersection(result, s), seconds, None)
            if result is None:
                return None
        return result
    if kind == "or":
        result = S.EmptySet
        for sub in item.eqs:
            s = solution_set(sub, var, seconds)
            if s is None:
                return None
            result = limited(lambda: Union(result, s), seconds, None)
            if result is None:
                return None
        return result
    return None


def _finite_values(s):
    try:
        return [x.evalf(30) for x in s.args]
    except Exception:
        return None


def sets_equal(a, b, tolerance=None) -> bool | None:
    """Compare two real solution sets. tolerance allows rounded decimals."""
    try:
        if a == b:
            return True
        if isinstance(a, FiniteSet) and isinstance(b, FiniteSet):
            va, vb = _finite_values(a), _finite_values(b)
            if va is None or vb is None:
                return None
            if any(not v.is_real for v in va + vb):
                return None
            if len(va) != len(vb):
                return False
            tol = tolerance if tolerance is not None else 1e-20
            used = [False] * len(vb)
            for x in va:
                hit = False
                for j, y in enumerate(vb):
                    if not used[j] and abs(x - y) <= tol * max(1, abs(x)):
                        used[j] = True
                        hit = True
                        break
                if not hit:
                    return False
            return True
        if (isinstance(a, ImageSet) or a.has(ImageSet) or isinstance(b, ImageSet)
                or b.has(ImageSet)):
            d1 = limited(lambda: Complement(a, b), SYMBOLIC_SECONDS, None)
            d2 = limited(lambda: Complement(b, a), SYMBOLIC_SECONDS, None)
            if d1 is S.EmptySet and d2 is S.EmptySet:
                return True
            return None
        d1 = limited(lambda: Complement(a, b), SYMBOLIC_SECONDS, None)
        d2 = limited(lambda: Complement(b, a), SYMBOLIC_SECONDS, None)
        if d1 is None or d2 is None:
            return None
        if d1 is S.EmptySet and d2 is S.EmptySet:
            return True
        if _definitely_nonempty(d1) or _definitely_nonempty(d2):
            return False
        return None
    except EngineTimeout:
        return None
    except Exception:
        return None


def _definitely_nonempty(s) -> bool:
    if s is S.EmptySet:
        return False
    if isinstance(s, (FiniteSet, Interval)):
        return s.is_empty is False
    if isinstance(s, Union):
        return any(_definitely_nonempty(a) for a in s.args)
    return s.is_empty is False


def _set_difference_values(a, b):
    try:
        d = limited(lambda: Complement(a, b), SYMBOLIC_SECONDS, None)
        if isinstance(d, FiniteSet):
            return list(d.args)
    except Exception:
        pass
    return []


def _eq_function(item):
    """Single expression f with the item's solutions as the zeros of f (eq / or)."""
    if item.kind == "eq":
        return item.lhs - item.rhs
    if item.kind == "or" and all(e.kind == "eq" for e in item.eqs):
        return Mul(*[e.lhs - e.rhs for e in item.eqs])
    return None


def relation_equivalent(a, b, var, *, decimals: int = 0, seed="") -> Verdict:
    """Same real solution set (equations, inequalities, 'x = 2 or x = 3')."""
    fa, fb = _eq_function(a), _eq_function(b)
    syms = set()
    for it in (a, b):
        syms |= item_symbols(it)
    syms = strip_constants(syms)

    # Fast path: one equation is a nonzero constant multiple of the other.
    if a.kind == "eq" and b.kind == "eq" and fa is not None and fb is not None:
        if fb == 0 and fa == 0:
            return Verdict(True, "verified")
        if fb != 0:
            r = limited(lambda: cancel(together(fa / fb)), 1.0, None)
            if r is not None and r.is_number and r.is_finite and r != 0 and not r.has(S.NaN):
                return Verdict(True, "verified")

    if len(syms) <= 1:
        v = var if var in syms or not syms else next(iter(syms))
        sa = solution_set(a, v)
        sb = solution_set(b, v)
        if sa is None or sb is None:
            return _numeric_relation_fallback(a, b, v, seed)
        tol = None
        if decimals:
            tol = 0.5 * 10 ** (-decimals)
        same = sets_equal(sa, sb)
        if same is False and tol is not None:
            if sets_equal(sa, sb, tolerance=tol):
                return Verdict(True, "verified", reason="rounded")
        if same is True:
            return Verdict(True, "verified")
        if same is False:
            return Verdict(False, "verified", lost=_set_difference_values(sa, sb),
                           gained=_set_difference_values(sb, sa))
        return Verdict(None, reason="unsolvable")

    # Several variables: equations only.
    if a.kind == "eq" and b.kind == "eq":
        return _multivar_equivalent(a, b, syms, var, seed)
    return Verdict(None, reason="multivariable")


def _numeric_relation_fallback(a, b, var, seed) -> Verdict:
    """When solveset can't help: if f_a / f_b is constant, the zeros agree."""
    fa, fb = _eq_function(a), _eq_function(b)
    if fa is None or fb is None:
        return Verdict(None, reason="unsolvable")
    v = expr_equivalent_plain(fa, fb, seed=seed, allow_domain=False)
    if v.equal:
        return Verdict(True, v.tier)
    v2 = expr_equivalent_plain(fa, -fb, seed=seed, allow_domain=False)
    if v2.equal:
        return Verdict(True, v2.tier)
    return Verdict(None, reason="unsolvable")


def _choose_variables(a, b, syms, var):
    order = []
    # Prefer a variable that B isolates ("y = 3 - 2x").
    if isinstance(b.lhs, Symbol) and b.lhs in syms:
        order.append(b.lhs)
    if isinstance(b.rhs, Symbol) and b.rhs in syms:
        order.append(b.rhs)
    if var in syms:
        order.append(var)
    order += sorted(syms, key=lambda s: s.name)
    seen, out = set(), []
    for s in order:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _multivar_equivalent(a, b, syms, var, seed) -> Verdict:
    fa, fb = a.lhs - a.rhs, b.lhs - b.rhs
    for v in _choose_variables(a, b, syms, var)[:3]:
        sa = limited(lambda: solve(fa, v), SYMBOLIC_SECONDS, None)
        sb = limited(lambda: solve(fb, v), SYMBOLIC_SECONDS, None)
        if not sa or not sb:
            continue
        tier = "verified"
        matched_b = [False] * len(sb)
        for ea in sa:
            hit = False
            for j, eb in enumerate(sb):
                if matched_b[j]:
                    continue
                vv = expr_equivalent_plain(ea, eb, seed=seed, allow_domain=False)
                if vv.equal:
                    matched_b[j] = True
                    hit = True
                    if vv.tier == "numeric":
                        tier = "numeric"
                    break
            if not hit:
                return Verdict(False, "numeric")
        if not all(matched_b):
            return Verdict(False, "numeric")
        return Verdict(True, tier)
    return Verdict(None, reason="unsolvable")


def item_symbols(item) -> set:
    if item.kind == "expr":
        return set(item.expr.free_symbols)
    if item.kind == "eq":
        return item.lhs.free_symbols | item.rhs.free_symbols
    if item.kind == "rel":
        out = set()
        for s in item.sides:
            out |= s.free_symbols
        return out
    if item.kind in ("or", "sys"):
        out = set()
        for e in item.eqs:
            out |= item_symbols(e)
        return out
    return set()


# --------------------------------------------------------------------------
# systems
# --------------------------------------------------------------------------

def system_solutions(eqs, syms, seconds=SYMBOLIC_SECONDS * 2):
    """All solutions of a system as a list of dicts (possibly parametric). None on failure."""
    exprs = [e.lhs - e.rhs for e in eqs]
    unknowns = sorted(syms, key=lambda s: s.name)

    def _solve():
        return solve(exprs, unknowns, dict=True)

    out = limited(_solve, seconds, None)
    if out is None:
        return None
    return out


def implied_by(solutions, eqs, *, seed="") -> bool | None:
    """Does every solution of the original system satisfy every equation in eqs?"""
    if solutions is None:
        return None
    if solutions == []:
        return True  # an inconsistent system implies anything
    for sol in solutions:
        for e in eqs:
            f = (e.lhs - e.rhs).xreplace(sol)
            f = limited(lambda: cancel(f), SYMBOLIC_SECONDS, f)
            if f.free_symbols:
                v = expr_equivalent_plain(f, S.Zero, seed=seed, allow_domain=False)
                if v.equal is None:
                    return None
                if not v.equal:
                    return False
            else:
                val = value_at(f, {})
                if val is None:
                    return None
                if val != 0 and abs(val) > 1e-20:
                    return False
    return True
