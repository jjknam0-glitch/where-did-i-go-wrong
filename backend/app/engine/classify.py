"""Deterministic error classifiers.

Both lines are SymPy trees, so specific mistakes can be tested directly: the
engine builds what the student *would* have written after a particular
mistake and checks whether that matches what they actually wrote (or, for
mistakes in the student's line, whether undoing one change makes it valid).
An AI model never decides what went wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sympy import (
    Add, Dummy, Expr, Integer, Mul, Number, Pow, Rational, S, Symbol, cancel, expand, factor,
    nsimplify, simplify, solve, together,
)

from .calculus import antiderivative_facts, classify_derivative, correct_antiderivative
from .equivalence import Verdict, expr_equivalent_plain, relation_equivalent, solution_set
from .items import FLIP, REL_TEX, Item, rtex, tex
from .numeric import make_rng
from .timeout import EngineTimeout, limited


@dataclass
class Classification:
    error_type: str
    subtype: str | None = None
    facts: dict = field(default_factory=dict)
    corrected: str | None = None  # LaTeX of a corrected version of the student's line
    warning: bool = False


# --------------------------------------------------------------------------
# tree helpers
# --------------------------------------------------------------------------

def evaluate_tree(e):
    """Evaluate an unevaluated tree bottom-up."""
    if not getattr(e, "args", None):
        return e
    args = [evaluate_tree(a) for a in e.args]
    try:
        return e.func(*args)
    except Exception:
        return e


def flat_terms(raw) -> list:
    """Written terms of an unevaluated sum, flattening nested Adds."""
    if raw is None:
        return []
    if raw.is_Add:
        out = []
        for a in raw.args:
            out.extend(flat_terms(a))
        return sorted(out, key=_term_sort_key)
    return [raw]


def _term_sort_key(t):
    """Highest degree first, constants last (how people write polynomials)."""
    from sympy import Poly
    try:
        syms = sorted(t.free_symbols, key=lambda s: s.name)
        if not syms:
            return (1, 0, "")
        deg = Poly(evaluate_tree(t), *syms).total_degree()
        return (0, -deg, str(t))
    except Exception:
        return (0, -0.5, str(t))


def join_terms_tex(terms) -> str:
    out = ""
    for i, t in enumerate(terms):
        neg = _is_negative_term(t)
        body = rtex(_negate_raw(t)) if neg else rtex(t)
        if i == 0:
            out = ("-" + body) if neg else body
        else:
            out += (" - " if neg else " + ") + body
    return out or "0"


def _is_negative_term(t) -> bool:
    try:
        if t.is_Number:
            return t < 0
        if t.is_Mul and t.args and t.args[0].is_Number:
            return t.args[0] < 0
    except TypeError:
        return False
    return False


def _negate_raw(t):
    if t.is_Number:
        return -t
    if t.is_Mul and t.args[0].is_Number:
        c = -t.args[0]
        rest = t.args[1:]
        if c == 1:
            return rest[0] if len(rest) == 1 else Mul(*rest, evaluate=False)
        return Mul(c, *rest, evaluate=False)
    return Mul(-1, t, evaluate=False)


def signed_tex(v) -> str:
    """'+3' / '-3' / '+2x' for describing a moved term."""
    try:
        neg = v.could_extract_minus_sign()
    except Exception:
        neg = False
    if neg:
        return "-" + tex(-v)
    return "+" + tex(v)


def number_atoms(raw):
    """(path, value) for each written number worth adjusting."""
    found = []

    def walk(e, path, parent):
        if e.is_Number:
            if parent is not None and parent.is_Mul and abs(e) == 1:
                return
            if parent is not None and parent.is_Pow and path[-1] == 1 and e in (-1, S.Half):
                return
            found.append((tuple(path), e))
            return
        for i, a in enumerate(getattr(e, "args", ())):
            walk(a, path + [i], e)

    walk(raw, [], None)
    return found


def replace_at(raw, path, new):
    if not path:
        return new
    i = path[0]
    args = list(raw.args)
    args[i] = replace_at(args[i], path[1:], new)
    if raw.is_Add or raw.is_Mul or raw.is_Pow:
        return raw.func(*args, evaluate=False)
    return raw.func(*args)


def _ordered_sum(e):
    """An unevaluated sum whose terms print in the usual (descending) order."""
    if e.is_Add:
        return Add(*sorted(e.args, key=_term_sort_key), evaluate=False)
    return e


def subtrees(raw):
    """All (path, node) pairs of a tree."""
    out = []

    def walk(e, path):
        out.append((tuple(path), e))
        for i, a in enumerate(getattr(e, "args", ())):
            walk(a, path + [i])

    walk(raw, [])
    return out


def _is_number(e) -> bool:
    return bool(e is not None and e.is_number and not e.free_symbols)


def _nice_rational(v) -> bool:
    return v is not None and v.is_Rational and abs(v.p) < 10 ** 9 and abs(v.q) < 10 ** 6


def describe_factor(k, side: str) -> str:
    """'divided the left side by 2' / 'multiplied the left side by 3'."""
    if k.is_Rational and k.p == 1 and k.q > 1:
        return f"divided the {side} side by ${k.q}$"
    if k.is_Rational and k.p == -1 and k.q > 1:
        return f"divided the {side} side by ${-k.q}$"
    if k.is_Integer:
        return f"multiplied the {side} side by ${tex(k)}$"
    return f"multiplied the {side} side by ${tex(k)}$"


def describe_shift(d, side: str) -> str:
    if d.could_extract_minus_sign():
        return f"subtracted ${tex(-d)}$ from the {side} side"
    return f"added ${tex(d)}$ to the {side} side"


# --------------------------------------------------------------------------
# classifier context
# --------------------------------------------------------------------------

@dataclass
class StepContext:
    mode: str                  # "equation" | "expression" | "derivative" | "integral" | "system"
    var: Symbol
    valid: object              # callable(Item) -> bool
    seed: str = ""
    target: Expr | None = None     # correct value of the step (expression / derivative modes)
    func: Expr | None = None       # function being differentiated (derivative mode)
    integrand: Expr | None = None  # integrand (integral mode)
    a_solutions: list = field(default_factory=list)  # solutions of A (equation mode)
    system_solutions: list | None = None


def _eq_item(lhs, rhs, line=0):
    return Item.equation(line, lhs, rhs)


def _safe_valid(ctx: StepContext, item) -> bool:
    try:
        return bool(ctx.valid(item))
    except EngineTimeout:
        return False
    except Exception:
        return False


def _same(a, b, seed="") -> bool:
    if a is None or b is None:
        return False
    try:
        return bool(expr_equivalent_plain(a, b, seed=seed, allow_domain=False).equal)
    except Exception:
        return False


# --------------------------------------------------------------------------
# individual classifiers
# --------------------------------------------------------------------------

def classify_inequality_flip(A: Item, B: Item, ctx: StepContext):
    if B.kind != "rel":
        return None
    flipped = Item.relation(B.line, B.sides, [FLIP[o] for o in B.ops], B.raw_sides)
    if not _safe_valid(ctx, flipped):
        return None
    facts = {}
    if A.kind == "rel" and len(A.sides) == 2 and len(B.sides) == 2:
        for i in (0, 1):
            if A.sides[i] != 0 and B.sides[i] != 0:
                k = limited(lambda: cancel(A.sides[i] / B.sides[i]), 1.0, None)
                if _is_number(k) and k.is_negative:
                    facts["divisor"] = tex(k)
                    break
    return Classification("inequality_flip", None, facts, flipped.to_latex())


def classify_one_side(A: Item, B: Item, ctx: StepContext):
    if A.kind != "eq" or B.kind != "eq":
        return None
    seed = ctx.seed
    # Multiplied / divided only one side.
    for side in ("left", "right"):
        a_this, a_other = (A.lhs, A.rhs) if side == "left" else (A.rhs, A.lhs)
        b_this, b_other = (B.lhs, B.rhs) if side == "left" else (B.rhs, B.lhs)
        if a_this == 0 or not _same(b_other, a_other, seed):
            continue
        k = limited(lambda: cancel(together(b_this / a_this)), 1.0, None)
        # Only plausible operations: multiplying by an integer or dividing by one.
        plausible = _is_number(k) and k.is_Rational and (k.q == 1 or abs(k.p) == 1)
        if plausible and k not in (0, 1) and k.is_finite:
            fixed_other = limited(lambda: expand(k * a_other), 1.0, k * a_other)
            corrected = (_eq_item(b_this, fixed_other) if side == "left"
                         else _eq_item(fixed_other, b_this))
            if _safe_valid(ctx, corrected):
                return Classification("one_side_only", "scale", {
                    "action": describe_factor(k, side), "side": side,
                    "other": "right" if side == "left" else "left",
                }, corrected.to_latex())
    # Added / subtracted only on one side.
    for side in ("left", "right"):
        a_this, a_other = (A.lhs, A.rhs) if side == "left" else (A.rhs, A.lhs)
        b_this, b_other = (B.lhs, B.rhs) if side == "left" else (B.rhs, B.lhs)
        if not _same(b_other, a_other, seed):
            continue
        d = limited(lambda: expand(b_this - a_this), 1.0, None)
        if d is None or d == 0:
            continue
        # Only plausible operations: adding or subtracting a term the student wrote.
        written = [evaluate_tree(t) for t in flat_terms(A.raw_lhs) + flat_terms(A.raw_rhs)]
        if not any(_same(d, w, seed) or _same(d, -w, seed) for w in written):
            continue
        fixed_other = limited(lambda: a_other + d, 1.0, None)
        if fixed_other is None:
            continue
        corrected = (_eq_item(b_this, fixed_other) if side == "left"
                     else _eq_item(fixed_other, b_this))
        if _safe_valid(ctx, corrected):
            return Classification("one_side_only", "shift", {
                "action": describe_shift(d, side), "side": side,
                "other": "right" if side == "left" else "left",
            }, corrected.to_latex())
    return None


def classify_moved_term(A: Item, B: Item, ctx: StepContext):
    """A term moved across '=' without changing its sign."""
    if A.kind != "eq" or B.kind != "eq":
        return None
    seed = ctx.seed
    for from_side in ("left", "right"):
        if from_side == "left":
            d = limited(lambda: expand(A.lhs - B.lhs), 1.0, None)
            if d is None or d == 0:
                continue
            if _same(B.rhs, A.rhs + d, seed):
                corrected = _eq_item(B.lhs, expand(A.rhs - d))
                if _safe_valid(ctx, corrected):
                    return Classification("sign_error", "moved", {
                        "term": signed_tex(d), "fixed_term": signed_tex(-d),
                        "to": "right", "from": "left",
                    }, f"{rtex(B.raw_lhs)} = {tex(expand(A.rhs - d))}")
        else:
            d = limited(lambda: expand(A.rhs - B.rhs), 1.0, None)
            if d is None or d == 0:
                continue
            if _same(B.lhs, A.lhs + d, seed):
                corrected = _eq_item(expand(A.lhs - d), B.rhs)
                if _safe_valid(ctx, corrected):
                    return Classification("sign_error", "moved", {
                        "term": signed_tex(d), "fixed_term": signed_tex(-d),
                        "to": "left", "from": "right",
                    }, f"{tex(expand(A.lhs - d))} = {rtex(B.raw_rhs)}")
    return None


def _sides_of(item: Item):
    """(name, evaluated, raw) for each side that can be edited term-by-term."""
    if item.kind == "eq":
        return [("lhs", item.lhs, item.raw_lhs), ("rhs", item.rhs, item.raw_rhs)]
    if item.kind == "expr":
        return [("expr", item.expr, item.raw)]
    if item.kind == "rel":
        return [(i, s, r) for i, (s, r) in enumerate(zip(item.sides, item.raw_sides))]
    return []


def _rebuild(item: Item, name, new_eval, new_raw):
    if item.kind == "eq":
        if name == "lhs":
            return Item.equation(item.line, new_eval, item.rhs, new_raw, item.raw_rhs)
        return Item.equation(item.line, item.lhs, new_eval, item.raw_lhs, new_raw)
    if item.kind == "expr":
        return Item.expression(item.line, new_eval, new_raw, item.label)
    if item.kind == "rel":
        sides = list(item.sides)
        raws = list(item.raw_sides)
        sides[name] = new_eval
        raws[name] = new_raw
        return Item.relation(item.line, sides, item.ops, raws)
    return None


def _distribution_products(A: Item):
    """(c, group) for each written product c*(p + q + ...) in A."""
    found = []
    for _, side_eval, side_raw in _sides_of(A):
        for path, node in subtrees(side_raw):
            if node.is_Mul:
                adds = [f for f in node.args if f.is_Add]
                if len(adds) == 1:
                    c = Mul(*[f for f in node.args if f is not adds[0]])
                    found.append((evaluate_tree(c), adds[0]))
    return found


def classify_term_sign(A: Item, B: Item, ctx: StepContext):
    """Flipping the sign of one written term of B makes it valid."""
    products = _distribution_products(A) if A is not None else []
    for name, side_eval, side_raw in _sides_of(B):
        terms = flat_terms(side_raw)
        if len(terms) > 12:
            continue
        for i, t in enumerate(terms):
            new_terms = list(terms)
            new_terms[i] = _negate_raw(t)
            new_eval = Add(*[evaluate_tree(x) for x in new_terms])
            new_raw = Add(*new_terms, evaluate=False) if len(new_terms) > 1 else new_terms[0]
            cand = _rebuild(B, name, new_eval, new_raw)
            if cand is None or not _safe_valid(ctx, cand):
                continue
            facts = {"term": rtex(t), "fixed_term": rtex(_negate_raw(t))}
            subtype = "term"
            # Was this term produced by distributing a negative?
            fixed_val = evaluate_tree(_negate_raw(t))
            for c, group in products:
                expanded = [expand(c * evaluate_tree(g)) for g in flat_terms(group)]
                if any(_same(fixed_val, e, ctx.seed) for e in expanded) and c.could_extract_minus_sign():
                    subtype = "distribution"
                    facts.update({"multiplier": tex(c), "group": rtex(group),
                                  "expanded": join_terms_tex([expand(c * evaluate_tree(g)) for g in flat_terms(group)])})
                    break
            corrected = _replace_side_tex(B, name, join_terms_tex(new_terms))
            return Classification("sign_error", subtype, facts, corrected)
    return None


def _replace_side_tex(item: Item, name, side_tex: str) -> str:
    if item.kind == "eq":
        if name == "lhs":
            return f"{side_tex} = {rtex(item.raw_rhs)}"
        return f"{rtex(item.raw_lhs)} = {side_tex}"
    if item.kind == "expr":
        return side_tex
    if item.kind == "rel":
        parts = [rtex(s) for s in item.raw_sides]
        parts[name] = side_tex
        out = parts[0]
        for op, s in zip(item.ops, parts[1:]):
            out += f" {REL_TEX[op]} {s}"
        return out
    return side_tex


def _mutated_items(A: Item, mutate):
    """Apply ``mutate(node) -> [(subtype, replacement, correct, facts)]`` to every subtree of A."""
    out = []
    for name, side_eval, side_raw in _sides_of(A):
        for path, node in subtrees(side_raw):
            for subtype, repl, correct, facts in mutate(node):
                new_raw = replace_at(side_raw, list(path), repl)
                fixed_raw = replace_at(side_raw, list(path), correct)
                new_eval = evaluate_tree(new_raw)
                out.append((subtype, _rebuild(A, name, new_eval, new_raw),
                            _rebuild(A, name, evaluate_tree(fixed_raw), fixed_raw), facts))
    return out


def _relation_matches(cand: Item, B: Item, ctx: StepContext) -> bool:
    """Is B a valid step from the mistaken version of A?"""
    try:
        if cand.kind == "expr" and B.kind == "expr":
            return _same(cand.expr, B.expr, ctx.seed)
        if cand.kind in ("eq", "rel", "or") and B.kind in ("eq", "rel", "or"):
            return relation_equivalent(cand, B, ctx.var, seed=ctx.seed).equal is True
    except EngineTimeout:
        return False
    except Exception:
        return False
    return False


def classify_distribution(A: Item, B: Item, ctx: StepContext):
    def mutate(node):
        res = []
        if node.is_Mul:
            adds = [f for f in node.args if f.is_Add]
            if len(adds) == 1:
                group = adds[0]
                c = Mul(*[f for f in node.args if f is not group], evaluate=False)
                terms = flat_terms(group)
                if len(terms) >= 2:
                    # Only the first term got multiplied.
                    wrong = Add(Mul(c, terms[0], evaluate=False), *terms[1:], evaluate=False)
                    correct = _ordered_sum(Add(*[expand(evaluate_tree(c) * evaluate_tree(t)) for t in terms]))
                    expanded = join_terms_tex([expand(evaluate_tree(c) * evaluate_tree(t)) for t in terms])
                    res.append(("missed_term", wrong, correct, {
                        "multiplier": tex(evaluate_tree(c)), "group": rtex(group),
                        "missed": rtex(terms[-1]), "expanded": expanded}))
        return res

    for subtype, cand, fixed, facts in _mutated_items(A, mutate):
        if cand is not None and _relation_matches(cand, B, ctx):
            corrected = _fixed_tex(fixed)
            return Classification("distribution_error", subtype, facts, corrected)
    return None


def _fixed_tex(item: Item) -> str:
    if item.kind == "eq":
        return f"{_expanded_tex(item.raw_lhs)} = {_expanded_tex(item.raw_rhs)}"
    if item.kind == "expr":
        return _expanded_tex(item.raw)
    return item.to_latex()


def _expanded_tex(raw) -> str:
    # Show distributed products term by term, keeping the rest as written.
    terms = []
    for t in flat_terms(raw):
        if t.is_Mul and any(f.is_Add for f in t.args):
            inner = [f for f in t.args if f.is_Add][0]
            c = evaluate_tree(Mul(*[f for f in t.args if f is not inner]))
            terms.extend(expand(c * evaluate_tree(g)) for g in flat_terms(inner))
        else:
            terms.append(t)
    return join_terms_tex(terms)


def classify_exponent(A: Item, B: Item, ctx: StepContext):
    def mutate(node):
        res = []
        if node.is_Pow:
            base, ex = node.args
            if base.is_Add and ex.is_Integer and 2 <= ex <= 6:
                wrong = Add(*[Pow(t, ex, evaluate=False) for t in flat_terms(base)], evaluate=False)
                correct = _ordered_sum(expand(evaluate_tree(node)))
                res.append(("power_of_sum", wrong, correct, {
                    "power": rtex(node), "expanded": tex(correct), "n": str(ex)}))
            if base.is_Add and ex == S.Half:
                wrong = Add(*[Pow(t, S.Half, evaluate=False) for t in flat_terms(base)], evaluate=False)
                res.append(("root_of_sum", wrong, node, {"power": rtex(node)}))
            if base.is_Mul and ex.is_Integer and ex >= 2:
                coeffs = [f for f in base.args if f.is_Number]
                rest = [f for f in base.args if not f.is_Number]
                if coeffs and rest:
                    c = Mul(*coeffs)
                    wrong = Mul(c, Pow(Mul(*rest, evaluate=False), ex, evaluate=False), evaluate=False)
                    correct = evaluate_tree(node)
                    res.append(("power_of_product", wrong, correct, {
                        "power": rtex(node), "expanded": tex(correct), "coeff": tex(c), "n": str(ex)}))
            if base.is_Pow and base.args[1].is_number and ex.is_number:
                wrong = Pow(base.args[0], base.args[1] + ex, evaluate=False)
                correct = Pow(base.args[0], base.args[1] * ex)
                res.append(("power_of_power", wrong, correct, {
                    "power": rtex(node), "expanded": tex(correct)}))
            if ex.is_Integer and ex < 0 and ex != -1 and not base.is_number:
                wrong = Mul(-1, Pow(base, -ex, evaluate=False), evaluate=False)
                res.append(("negative_exponent", wrong, node, {"power": rtex(node)}))
        if node.is_Mul:
            pows = [f for f in node.args if f.is_Pow and f.args[1].is_number]
            bases = {}
            for p in pows:
                bases.setdefault(p.args[0], []).append(p)
            for b, ps in bases.items():
                if len(ps) == 2:
                    others = [f for f in node.args if f not in ps]
                    wrong = Mul(*others, Pow(b, ps[0].args[1] * ps[1].args[1], evaluate=False), evaluate=False)
                    correct = Mul(*others, Pow(b, ps[0].args[1] + ps[1].args[1]))
                    res.append(("product_of_powers", wrong, correct, {
                        "power": rtex(Mul(*ps, evaluate=False)), "expanded": tex(Pow(b, ps[0].args[1] + ps[1].args[1]))}))
        return res

    for subtype, cand, fixed, facts in _mutated_items(A, mutate):
        if cand is not None and _relation_matches(cand, B, ctx):
            return Classification("exponent_rule", subtype, facts, fixed.to_latex())
    return None


def _value_candidates_for_k(B: Item, raw_k: Item, k: Symbol, ctx: StepContext):
    """Values of k that make the k-version of B satisfy the step."""
    rng = make_rng("k", ctx.seed)
    var = ctx.var
    eqs = []
    if ctx.mode in ("expression", "derivative", "integral") and raw_k.kind == "expr":
        if ctx.target is None:
            return []
        target = ctx.target
        expr_k = raw_k.expr
        if ctx.mode == "integral":
            from sympy import diff
            expr_k = diff(expr_k, var)
        syms = (target.free_symbols | expr_k.free_symbols) - {k}
        for _ in range(3):
            point = {s: Rational(rng.randint(1, 30), rng.randint(1, 5)) for s in syms}
            try:
                eqs.append(expr_k.xreplace(point) - target.xreplace(point))
            except Exception:
                pass
    elif raw_k.kind in ("eq", "rel"):
        f = raw_k.lhs - raw_k.rhs if raw_k.kind == "eq" else raw_k.sides[0] - raw_k.sides[-1]
        if ctx.system_solutions:
            for sol in ctx.system_solutions[:2]:
                eqs.append(f.xreplace(sol))
        else:
            for s in ctx.a_solutions[:3]:
                eqs.append(f.xreplace({var: s}))
    else:
        return []
    values = set()
    for e in eqs:
        if not e.has(k) or e.free_symbols - {k}:
            continue
        sol = limited(lambda: solve(e, k), 1.0, None)
        for v in sol or []:
            if _nice_rational(v):
                values.add(v)
        if values:
            break
    return sorted(values, key=lambda v: abs(v))


def classify_arithmetic(A: Item, B: Item, ctx: StepContext):
    """B is right except for one written number."""
    k = Dummy("k")
    candidates = []
    a_sides = {n: ev for n, ev, _ in _sides_of(A)} if A is not None and A.kind == B.kind else {}
    for name, side_eval, side_raw in _sides_of(B):
        side_has_var = side_eval.has(ctx.var)
        if name in a_sides and ctx.mode == "equation" and _same(a_sides[name], side_eval, ctx.seed):
            continue  # the student didn't change this side
        for path, value in number_atoms(side_raw):
            depth = len(path)
            # Prefer standalone numbers, then numbers on a side without the variable,
            # then coefficients, then exponents.
            parent = side_raw
            for i in path[:-1]:
                parent = parent.args[i]
            if depth == 0 or (parent.is_Add):
                rank = 0 if not side_has_var else 1
            elif parent.is_Mul:
                rank = 2
            else:
                rank = 3
            candidates.append((rank, name, side_raw, path, value))
    candidates.sort(key=lambda c: c[0])
    for _rank, name, side_raw, path, value in candidates:
        raw_k = replace_at(side_raw, list(path), k)
        item_k = _rebuild(B, name, evaluate_tree(raw_k), raw_k)
        if item_k is None:
            continue
        for v in _value_candidates_for_k(B, item_k, k, ctx)[:3]:
            if v == value:
                continue
            fixed_raw = replace_at(side_raw, list(path), v)
            cand = _rebuild(B, name, evaluate_tree(fixed_raw), fixed_raw)
            if cand is None or not _safe_valid(ctx, cand):
                continue
            facts = {"wrong": rtex(value), "right": tex(v)}
            origin = _arithmetic_origin(A, B, v)
            if origin:
                facts["origin"] = origin
            return Classification("arithmetic_slip", None, facts, cand.to_latex())
    return None


def _arithmetic_origin(A: Item, B: Item, right) -> str | None:
    """Where the right number comes from, e.g. '7 - 3' or '10 \\div 2'."""
    if A is None or A.kind != "eq" or B.kind != "eq":
        return None
    try:
        if _is_number(A.rhs) and _is_number(B.rhs):
            d = expand(A.lhs - B.lhs)
            if _is_number(d) and d != 0 and A.rhs - d == right:
                op = "-" if d > 0 else "+"
                return f"{tex(A.rhs)} {op} {tex(abs(d))}"
            if B.lhs != 0:
                r = cancel(A.lhs / B.lhs)
                if r.is_Integer and r not in (0, 1) and A.rhs / r == right:
                    return f"{tex(A.rhs)} \\div {tex(r)}" if r > 0 else f"{tex(A.rhs)} \\div ({tex(r)})"
        if _is_number(A.lhs) and _is_number(B.lhs):
            d = expand(A.rhs - B.rhs)
            if _is_number(d) and d != 0 and A.lhs - d == right:
                op = "-" if d > 0 else "+"
                return f"{tex(A.lhs)} {op} {tex(abs(d))}"
            if B.rhs != 0:
                r = cancel(A.rhs / B.rhs)
                if r.is_Integer and r not in (0, 1) and A.lhs / r == right:
                    return f"{tex(A.lhs)} \\div {tex(r)}" if r > 0 else f"{tex(A.lhs)} \\div ({tex(r)})"
    except (TypeError, ValueError):
        return None
    return None


def classify_solution_change(A: Item, B: Item, verdict: Verdict, ctx: StepContext):
    """Lost / extra solutions. Dividing by or squaring a variable is a warning, not an error."""
    if A.kind != "eq" or B.kind != "eq":
        return None
    lost, gained = verdict.lost, verdict.gained
    var = ctx.var
    if lost and not gained:
        # Divided both sides by the same expression in x?
        gl = limited(lambda: cancel(A.lhs / B.lhs), 1.0, None) if B.lhs != 0 else None
        gr = limited(lambda: cancel(A.rhs / B.rhs), 1.0, None) if B.rhs != 0 else None
        g = None
        if gl is not None and gl.has(var) and gr is not None and _same(gl, gr, ctx.seed):
            g = gl
        elif gl is not None and gl.has(var) and A.rhs == 0 and B.rhs == 0:
            g = gl
        if g is not None and all(_is_zero_at(g, var, s) for s in lost):
            return Classification("lost_solution", "divide", {
                "divisor": tex(factor(g)), "values": [tex(v) for v in lost],
                "var": tex(var)}, None, warning=True)
        # Square root without ±
        if _same(A.lhs, B.lhs ** 2, ctx.seed) and _same(A.rhs, B.rhs ** 2, ctx.seed):
            return Classification("lost_solution", "square_root", {
                "values": [tex(v) for v in lost], "var": tex(var)},
                f"{rtex(B.raw_lhs)} = \\pm {rtex(B.raw_rhs)}" if B.raw_rhs != 0 else None)
    if gained and not lost:
        if _same(B.lhs, A.lhs ** 2, ctx.seed) and _same(B.rhs, A.rhs ** 2, ctx.seed):
            return Classification("extra_solution", "square", {
                "values": [tex(v) for v in gained], "var": tex(var)}, None, warning=True)
        gl = limited(lambda: cancel(B.lhs / A.lhs), 1.0, None) if A.lhs != 0 else None
        gr = limited(lambda: cancel(B.rhs / A.rhs), 1.0, None) if A.rhs != 0 else None
        g = None
        if gl is not None and gl.has(var) and gr is not None and _same(gl, gr, ctx.seed):
            g = gl
        if g is None:
            # Clearing denominators: B is A multiplied through by g (sides may be rearranged).
            fa, fb = A.lhs - A.rhs, B.lhs - B.rhs
            if fa != 0:
                r = limited(lambda: cancel(together(fb / fa)), 1.0, None)
                if r is not None and r.has(var) and not r.is_number:
                    g = r
        if g is not None and all(_is_zero_at(g, var, s) for s in gained):
            return Classification("extra_solution", "multiply", {
                "factor": tex(factor(g)), "values": [tex(v) for v in gained],
                "var": tex(var)}, None, warning=True)
    return None


def anti_tex(anti) -> str | None:
    return None if anti is None else f"{tex(anti)} + C"


def nice_form(e):
    """The more readable of the expanded and simplified forms."""
    ex = limited(lambda: expand(e), 1.0, e)
    si = limited(lambda: simplify(e), 1.5, e)
    try:
        return ex if ex.count_ops() <= si.count_ops() + 1 else si
    except Exception:
        return e


def _is_zero_at(g, var, value) -> bool:
    try:
        v = g.xreplace({var: value})
        v = simplify(v)
        return v == 0 or v.is_zero is True
    except Exception:
        return False


def corrected_general(A: Item, B: Item, ctx: StepContext) -> str | None:
    """A corrected version of B when no specific rule matched."""
    var = ctx.var
    try:
        if ctx.mode in ("expression",) and ctx.target is not None and B.kind == "expr":
            shaped = factor(ctx.target) if B.expr.is_Mul else expand(ctx.target)
            if shaped.count_ops() > 3 * max(ctx.target.count_ops(), 1):
                shaped = simplify(ctx.target)
            return tex(shaped)
        if ctx.mode == "derivative" and ctx.target is not None:
            return tex(nice_form(ctx.target))
        if ctx.mode == "integral" and ctx.integrand is not None:
            return anti_tex(correct_antiderivative(ctx.integrand, var))
        if B.kind == "eq" and ctx.a_solutions and len(ctx.a_solutions) == 1:
            s = ctx.a_solutions[0]
            if not B.rhs.has(var) and B.lhs.has(var):
                fixed = expand(B.lhs.xreplace({var: s}))
                cand = _eq_item(B.lhs, fixed)
                if _safe_valid(ctx, cand):
                    return f"{rtex(B.raw_lhs)} = {tex(fixed)}"
            if not B.lhs.has(var) and B.rhs.has(var):
                fixed = expand(B.rhs.xreplace({var: s}))
                cand = _eq_item(fixed, B.rhs)
                if _safe_valid(ctx, cand):
                    return f"{tex(fixed)} = {rtex(B.raw_rhs)}"
        if B.kind == "rel" and A.kind == "rel" and len(B.sides) == 2 and B.sides[0] == var:
            sol = solution_set(A, var)
            if sol is not None:
                return interval_tex(var, sol)
    except EngineTimeout:
        return None
    except Exception:
        return None
    return None


def interval_tex(var, s) -> str | None:
    """'x > 3', 'x \\le -2', '1 < x < 4' for a single real interval."""
    from sympy import Interval, oo
    v = tex(var)
    if s == S.Reals:
        return r"\text{all real } " + v
    if s is S.EmptySet:
        return r"\text{no solution}"
    if isinstance(s, Interval):
        lo, hi = s.start, s.end
        lo_op = "<" if s.left_open else r"\le"
        hi_op = "<" if s.right_open else r"\le"
        if lo == -oo and hi == oo:
            return r"\text{all real } " + v
        if lo == -oo:
            return f"{v} {hi_op} {tex(hi)}"
        if hi == oo:
            return f"{v} {'>' if s.left_open else chr(92) + 'ge'} {tex(lo)}"
        return f"{tex(lo)} {lo_op} {v} {hi_op} {tex(hi)}"
    from sympy import latex
    return f"{v} \\in {latex(s)}"


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

def classify_step(A: Item, B: Item, ctx: StepContext, verdict: Verdict | None = None) -> Classification:
    """Find the first rule that explains the broken step A -> B."""
    attempts = []
    if ctx.mode == "derivative" and ctx.func is not None and B.kind == "expr":
        attempts.append(lambda: _classify_derivative(B, ctx))
    if ctx.mode == "integral" and ctx.integrand is not None and B.kind == "expr":
        attempts.append(lambda: _classify_integral(B, ctx))
    if A is not None and A.kind == "rel" and B.kind == "rel":
        attempts.append(lambda: classify_inequality_flip(A, B, ctx))
    if A is not None:
        attempts += [
            lambda: classify_one_side(A, B, ctx),
            lambda: classify_moved_term(A, B, ctx),
        ]
    attempts.append(lambda: classify_term_sign(A, B, ctx))
    if A is not None and ctx.mode not in ("derivative", "integral"):
        attempts.append(lambda: classify_distribution(A, B, ctx))
    if A is not None and ctx.mode not in ("derivative", "integral"):
        attempts.append(lambda: classify_exponent(A, B, ctx))
    attempts.append(lambda: classify_arithmetic(A, B, ctx))
    if A is not None and verdict is not None and (verdict.lost or verdict.gained):
        attempts.append(lambda: classify_solution_change(A, B, verdict, ctx))

    for attempt in attempts:
        try:
            res = attempt()
        except EngineTimeout:
            res = None
        except RecursionError:
            res = None
        except Exception:
            res = None
        if res is not None:
            return res
    if ctx.mode == "integral":
        return Classification("antiderivative_error", "general", {}, corrected_general(A, B, ctx))
    if ctx.mode == "derivative":
        return Classification("derivative_rule", "general", {}, corrected_general(A, B, ctx))
    if verdict is not None and verdict.lost and not verdict.gained:
        return Classification("lost_solution", "general", {}, corrected_general(A, B, ctx))
    if verdict is not None and verdict.gained and not verdict.lost:
        return Classification("extra_solution", "general", {}, corrected_general(A, B, ctx))
    return Classification("general", None, {}, corrected_general(A, B, ctx))


def _classify_derivative(B: Item, ctx: StepContext):
    kind, correct = classify_derivative(ctx.func, B.expr, ctx.var, seed=ctx.seed)
    if kind is None:
        return None
    return Classification("derivative_rule", kind, {"function": tex(ctx.func)},
                          tex(nice_form(correct)) if correct is not None else None)


def _classify_integral(B: Item, ctx: StepContext):
    kind, facts = antiderivative_facts(ctx.integrand, B.expr, ctx.var, seed=ctx.seed)
    out = {"integrand": tex(ctx.integrand)}
    if facts.get("student_derivative") is not None:
        out["student_derivative"] = tex(simplify(facts["student_derivative"]))
    if "factor" in facts:
        out["factor"] = tex(facts["factor"])
    anti = correct_antiderivative(ctx.integrand, ctx.var)
    return Classification("antiderivative_error", kind, out, anti_tex(anti))
