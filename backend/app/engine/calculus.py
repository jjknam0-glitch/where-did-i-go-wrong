"""Derivative and integral helpers, including common *wrong* derivatives.

Checking is easier than computing: a student's derivative is compared to
SymPy's ``diff``; an antiderivative is checked by differentiating it. To
explain a wrong derivative, the engine builds the results of the classic
misapplications (no chain rule, product rule with one term, ...) and sees
which one the student's answer matches.
"""

from __future__ import annotations

from sympy import (
    Add, Derivative, Dummy, Function, Integer, Integral, Mul, Pow, S, Symbol, cos, cot, csc,
    diff, exp, fraction, integrate, log, sec, simplify, sin, tan, together,
)

from .equivalence import expr_equivalent_plain
from .parsing import is_constant_symbol
from .timeout import limited

# --------------------------------------------------------------------------
# buggy differentiation
# --------------------------------------------------------------------------

_TRIG_WRONG_SIGN = {
    sin: lambda g: -cos(g),
    cos: lambda g: sin(g),
    tan: lambda g: -sec(g) ** 2,
    sec: lambda g: -sec(g) * tan(g),
    csc: lambda g: csc(g) * cot(g),
    cot: lambda g: csc(g) ** 2,
}


def bdiff(e, x, bug: str | None):
    """Differentiate ``e`` w.r.t. ``x`` but make one systematic mistake.

    bug: None | "chain" | "product_both" | "product_first" | "product_second" |
         "power_no_reduce" | "power_no_coeff" | "trig_sign" | "exp_as_power" |
         "quotient_sign" | "log_no_chain"
    """
    if not e.has(x):
        return S.Zero
    if e == x:
        return S.One
    if e.is_Add:
        return Add(*[bdiff(t, x, bug) for t in e.args])
    if e.is_Mul:
        with_x = [f for f in e.args if f.has(x)]
        const = Mul(*[f for f in e.args if not f.has(x)])
        if len(with_x) == 1:
            return const * bdiff(with_x[0], x, bug)
        if bug == "product_both":
            return const * Mul(*[bdiff(f, x, bug) for f in with_x])
        if bug in ("product_first", "product_second") and len(with_x) == 2:
            u, v = with_x
            if bug == "product_first":
                return const * bdiff(u, x, bug) * v
            return const * u * bdiff(v, x, bug)
        if bug == "quotient_sign":
            nums = [f for f in with_x if not (f.is_Pow and f.exp.is_negative)]
            dens = [f for f in with_x if f.is_Pow and f.exp.is_negative]
            if nums and dens:
                u = Mul(*nums)
                v = Mul(*[d.base ** (-d.exp) for d in dens])
                return const * (diff(u, x) * v + u * diff(v, x)) / v ** 2
        terms = []
        for i, f in enumerate(with_x):
            others = Mul(*[g for j, g in enumerate(with_x) if j != i])
            terms.append(others * bdiff(f, x, bug))
        return const * Add(*terms)
    if e.is_Pow:
        base, ex = e.args
        if not ex.has(x):
            inner = S.One if (bug == "chain" and base != x) else bdiff(base, x, bug)
            if bug == "power_no_reduce":
                return ex * base ** ex * inner
            if bug == "power_no_coeff":
                return base ** (ex - 1) * inner
            return ex * base ** (ex - 1) * inner
        if not base.has(x):
            inner = S.One if (bug == "chain" and ex != x) else bdiff(ex, x, bug)
            if bug == "exp_as_power":
                return ex * base ** (ex - 1) * inner
            return e * log(base) * inner
        return diff(e, x)
    if isinstance(e, Function) and len(e.args) == 1:
        g = e.args[0]
        if bug == "trig_sign" and e.func in _TRIG_WRONG_SIGN:
            outer = _TRIG_WRONG_SIGN[e.func](g)
        else:
            t = Dummy("t")
            outer = diff(e.func(t), t).xreplace({t: g})
        if bug in ("chain", "log_no_chain") and g != x:
            if bug == "log_no_chain" and e.func != log:
                inner = bdiff(g, x, bug)
            else:
                inner = S.One
        else:
            inner = bdiff(g, x, bug)
        if e.func == exp and bug == "exp_as_power":
            return g * exp(g - 1) * inner
        return outer * inner
    return diff(e, x)


DERIVATIVE_BUGS = [
    ("chain", "chain_rule"),
    ("product_both", "product_rule"),
    ("product_first", "product_rule"),
    ("product_second", "product_rule"),
    ("quotient_sign", "quotient_rule"),
    ("power_no_reduce", "power_rule"),
    ("power_no_coeff", "power_rule"),
    ("trig_sign", "trig_derivative"),
    ("exp_as_power", "exponential"),
]


def _quotient_candidates(F, x):
    out = []
    num, den = fraction(together(F))
    if den.has(x) and num != 0:
        du, dv = diff(num, x), diff(den, x)
        out += [
            ("quotient_rule", (du * den + num * dv) / den ** 2),
            ("quotient_rule", (num * dv - du * den) / den ** 2),
            ("quotient_rule", (du * den - num * dv) / den),
            ("quotient_rule", du / dv if dv != 0 else None),
        ]
    return [(k, c) for k, c in out if c is not None]


def derivative_candidates(F, x):
    """(subtype, wrong_derivative) pairs for the classic mistakes."""
    cands = []
    for bug, kind in DERIVATIVE_BUGS:
        c = limited(lambda: bdiff(F, x, bug), 1.0, None)
        if c is not None:
            cands.append((kind, c))
        # A student may get every term right but one.
        if F.is_Add:
            for t in F.args:
                if not t.has(x):
                    continue
                correct_t = diff(t, x)
                wrong_t = limited(lambda: bdiff(t, x, bug), 1.0, None)
                if wrong_t is not None:
                    cands.append((kind, diff(F, x) - correct_t + wrong_t))
    cands += _quotient_candidates(F, x)
    if F.is_Add:
        consts = Add(*[t for t in F.args if not t.has(x)])
        if consts != 0:
            cands.append(("constant_term", diff(F, x) + consts))
    for t in (F.args if F.is_Add else [F]):
        n, d = fraction(together(t))
        if d.has(x):
            cands += [(k, diff(F, x) - diff(t, x) + c) for k, c in _quotient_candidates(t, x)] \
                if F.is_Add else []
    return cands


def classify_derivative(F, student, x, seed=""):
    """Return (subtype, correct_derivative) if the student's result matches a classic mistake."""
    correct = limited(lambda: diff(F, x), 2.0, None)
    if correct is None:
        return None, None
    for kind, cand in derivative_candidates(F, x):
        if cand is None:
            continue
        same_as_correct = expr_equivalent_plain(cand, correct, seed=seed, allow_domain=False)
        if same_as_correct.equal:
            continue
        v = expr_equivalent_plain(cand, student, seed=seed, allow_domain=False)
        if v.equal:
            return kind, correct
    return None, correct


# --------------------------------------------------------------------------
# antiderivatives
# --------------------------------------------------------------------------

def has_constant_of_integration(e) -> bool:
    return any(is_constant_symbol(s) for s in e.free_symbols)


def antiderivative_facts(integrand, student, x, seed=""):
    """Explain a wrong antiderivative by differentiating the student's answer."""
    d = limited(lambda: diff(student, x), 2.0, None)
    facts = {"integrand": integrand, "student_derivative": d}
    if d is None:
        return "general", facts
    neg = expr_equivalent_plain(d, -integrand, seed=seed, allow_domain=False)
    if neg.equal:
        return "sign", facts
    ratio = limited(lambda: simplify(d / integrand), 2.0, None) if integrand != 0 else None
    if ratio is not None and ratio.is_number and ratio.is_finite and ratio not in (0, 1):
        facts["factor"] = ratio
        return "coefficient", facts
    return "general", facts


def correct_antiderivative(integrand, x):
    res = limited(lambda: integrate(integrand, x), 2.0, None)
    if res is None or res.has(Integral):
        return None
    return res
