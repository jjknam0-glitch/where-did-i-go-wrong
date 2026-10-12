"""Targeted practice problems.

Problems are generated from templates aimed at one kind of mistake, and every
answer is computed and checked by the engine, never by an AI. The server is
stateless: a problem carries its own statement, and checking recomputes the
answer from it, so answers are never sent to the browser in advance.
"""

from __future__ import annotations

import random
import re

from sympy import (
    Abs, Add, Integral, Mul, Pow, S, Symbol, diff, expand, factor, latex, simplify, sympify,
)

from .equivalence import (
    expr_equivalent_plain, implied_by, item_symbols, relation_equivalent, solution_set,
    strip_constants, system_solutions,
)
from .items import Item, tex
from .parsing import parse_line, try_parse_line
from .timeout import EngineTimeout, limited

x = Symbol("x")

SKILL_INFO = {
    "sign_error": ("Moving terms across the equals sign", "linear"),
    "one_side_only": ("Doing the same thing to both sides", "linear"),
    "distribution_error": ("Distributing, especially negatives", "linear"),
    "arithmetic_slip": ("Careful arithmetic in multi-step equations", "linear"),
    "exponent_rule": ("Exponent rules", "simplifying"),
    "inequality_flip": ("Inequalities with negatives", "inequalities"),
    "derivative_rule": ("Derivative rules", "derivatives"),
    "antiderivative_error": ("Antiderivatives", "integrals"),
    "lost_solution": ("Keeping every solution", "quadratics"),
    "extra_solution": ("Checking for extra solutions", "equations"),
    "general": ("Mixed equation practice", "linear"),
    # topics (for "try a harder one")
    "linear": ("Linear equations", "linear"),
    "quadratic": ("Quadratic equations", "quadratics"),
    "simplify": ("Simplifying expressions", "simplifying"),
    "factor": ("Factoring", "factoring"),
    "derivative": ("Derivatives", "derivatives"),
    "integral": ("Integrals", "integrals"),
    "inequality": ("Inequalities", "inequalities"),
    "system": ("Systems of equations", "systems"),
    "limit": ("Limits", "limits"),
    "exponential": ("Exponential equations", "exponentials"),
}

TOPIC_TO_SKILL = {
    "linear": "linear", "quadratics": "quadratic", "simplifying": "simplify",
    "factoring": "factor", "derivatives": "derivative", "integrals": "integral",
    "inequalities": "inequality", "systems": "system", "limits": "limit",
    "exponentials": "exponential", "trig": "derivative", "equations": "linear",
}

KIND_PROMPT = {
    "solve": "Solve for $x$.",
    "solve_system": "Solve the system.",
    "expand": "Expand and simplify.",
    "simplify": "Simplify.",
    "factor": "Factor completely.",
    "differentiate": "Find the derivative.",
    "integrate": "Find the antiderivative.",
    "limit": "Evaluate the limit.",
}


def _nz(rng, lo, hi):
    while True:
        v = rng.randint(lo, hi)
        if v != 0:
            return v


def _fmt_lin(a, b, var="x"):
    """'3x - 7' style text for a*x + b."""
    if a == 1:
        s = var
    elif a == -1:
        s = f"-{var}"
    else:
        s = f"{a}{var}"
    if b > 0:
        s += f" + {b}"
    elif b < 0:
        s += f" - {-b}"
    return s


def _scale(level):
    return {1: 9, 2: 15, 3: 25}.get(level, 9)


# --------------------------------------------------------------------------
# generators: each returns (kind, math_text)
# --------------------------------------------------------------------------

def g_sign(rng, level):
    m = _scale(level)
    sol = _nz(rng, -m, m)
    a = _nz(rng, 2, 9)
    b = _nz(rng, -m, m)
    if rng.random() < 0.5:
        return "solve", f"{_fmt_lin(a, b)} = {a * sol + b}"
    # c - a x = d
    c = _nz(rng, 1, m)
    return "solve", f"{c} - {a}x = {c - a * sol}"


def g_one_side(rng, level):
    m = _scale(level)
    choice = rng.random()
    if choice < 0.33:
        a = rng.randint(2, 6)
        q = _nz(rng, -4, 4)
        b = _nz(rng, -m, m)
        return "solve", f"x/{a} {'+' if b > 0 else '-'} {abs(b)} = {q + b}"
    if choice < 0.66:
        a, c = rng.sample([2, 3, 4, 5, 6, 7, 8], 2)
        sol = _nz(rng, -m, m)
        return "solve", f"{a}x = {_fmt_lin(c, (a - c) * sol)}"
    a = rng.randint(2, 5)
    k = _nz(rng, 1, 9)
    q = _nz(rng, -m, m)
    return "solve", f"(x + {k})/{a} = {q}"


def g_distribution(rng, level):
    m = _scale(level)
    sol = _nz(rng, -m, m)
    a = rng.choice([-5, -4, -3, -2, 2, 3, 4, 5])
    b = _nz(rng, -9, 9)
    c = _nz(rng, -m, m)
    lhs = f"{a}(x {'+' if b > 0 else '-'} {abs(b)})"
    if level >= 2:
        lhs += f" {'+' if c > 0 else '-'} {abs(c)}"
        return "solve", f"{lhs} = {a * (sol + b) + c}"
    return "solve", f"{lhs} = {a * (sol + b)}"


def g_arithmetic(rng, level):
    m = _scale(level) + 5
    sol = _nz(rng, -m // 2, m // 2)
    a, c = rng.sample(range(2, 13), 2)
    b = _nz(rng, -m, m)
    d = a * sol + b - c * sol
    return "solve", f"{_fmt_lin(a, b)} = {_fmt_lin(c, d)}"


def g_exponent(rng, level):
    r = rng.random()
    if r < 0.4:
        k = _nz(rng, -9, 9)
        sign = "+" if k > 0 else "-"
        return "expand", f"(x {sign} {abs(k)})^2"
    if r < 0.7:
        c = rng.randint(2, 5)
        p, n = rng.randint(2, 4), rng.randint(2, 3)
        return "simplify", f"({c}x^{p})^{n}"
    p, q = rng.randint(2, 6), rng.randint(2, 6)
    return "simplify", f"x^{p} * x^{q}"


def g_inequality(rng, level):
    m = _scale(level)
    sol = _nz(rng, -m, m)
    a = -rng.randint(2, 7)
    b = _nz(rng, -m, m)
    op = rng.choice([">", "<", ">=", "<="])
    return "solve", f"{_fmt_lin(a, b)} {op} {a * sol + b}"


def g_derivative(rng, level):
    n = rng.randint(2, 5)
    a = rng.randint(2, 6)
    b = _nz(rng, -6, 6)
    options = [
        f"x^{n} sin(x)",
        f"({_fmt_lin(a, b)})^{n}",
        f"sin({a}x)",
        f"cos(x^{n})",
        f"x^{n} e^({a}x)",
        f"({a}x + 1)/(x - {abs(b)})",
        f"ln({_fmt_lin(a, abs(b))})",
    ]
    if level == 1:
        options = options[:4] + [f"{a}x^{n} {'+' if b > 0 else '-'} {abs(b)}x"]
    return "differentiate", rng.choice(options)


def g_integral(rng, level):
    n = rng.randint(1, 5)
    a = rng.randint(2, 6)
    options = [
        f"{(n + 1) * a}x^{n}",
        f"cos({a}x)",
        f"sin({a}x)",
        f"e^({a}x)",
        f"{a}x^{n} + {rng.randint(1, 9)}",
        f"2x cos(x^2)",
    ]
    return "integrate", rng.choice(options)


def g_lost_solution(rng, level):
    a = _nz(rng, -9, 9)
    if rng.random() < 0.5:
        return "solve", f"x^2 = {a}x"
    k = rng.randint(2, 9)
    return "solve", f"x^2 = {k * k}"


def g_extra_solution(rng, level):
    # sqrt(x + c) = x - d with one valid root and one extraneous root.
    for _ in range(50):
        r = rng.randint(2, 9)
        d = rng.randint(0, r - 1)
        c = (r - d) ** 2 - r
        disc_roots = solution_set(Item.equation(0, x + c, (x - d) ** 2), x)
        if disc_roots is None or not disc_roots.is_FiniteSet or len(disc_roots.args) != 2:
            continue
        if all(v.is_Integer for v in disc_roots.args):
            sign = "+" if c >= 0 else "-"
            return "solve", f"sqrt(x {sign} {abs(c)}) = x - {d}" if d else f"sqrt(x {sign} {abs(c)}) = x"
    return "solve", "sqrt(x + 2) = x"


def g_quadratic(rng, level):
    r1, r2 = _nz(rng, -9, 9), _nz(rng, -9, 9)
    b, c = -(r1 + r2), r1 * r2
    s = "x^2"
    if b:
        s += f" {'+' if b > 0 else '-'} {abs(b) if abs(b) != 1 else ''}x"
    if c:
        s += f" {'+' if c > 0 else '-'} {abs(c)}"
    return "solve", f"{s} = 0"


def g_simplify(rng, level):
    a, b, c = _nz(rng, 2, 6), _nz(rng, -9, 9), _nz(rng, 2, 6)
    d = _nz(rng, -9, 9)
    return "simplify", f"{a}(x {'+' if b > 0 else '-'} {abs(b)}) - {c}(x {'+' if d > 0 else '-'} {abs(d)})"


def g_factor(rng, level):
    r1, r2 = _nz(rng, -9, 9), _nz(rng, -9, 9)
    e = expand((x - r1) * (x - r2))
    return "factor", str(e).replace("**", "^")


def g_system(rng, level):
    xs, ys = _nz(rng, -6, 6), _nz(rng, -6, 6)
    a, b = _nz(rng, 1, 4), _nz(rng, 1, 4)
    c, d = _nz(rng, 1, 4), -_nz(rng, 1, 4)
    if a * d - b * c == 0:
        d -= 1
    return "solve_system", f"{a}x + {b}y = {a * xs + b * ys}; {c}x - {abs(d)}y = {c * xs + d * ys}"


def g_limit(rng, level):
    r = _nz(rng, -6, 6)
    k = _nz(rng, -6, 6)
    while k == r:
        k = _nz(rng, -6, 6)
    num = expand((x - r) * (x - k))
    den = f"x {'-' if r > 0 else '+'} {abs(r)}"
    return "limit", f"lim_(x->{r}) ({str(num).replace('**', '^')})/({den})"


def g_exponential(rng, level):
    base = rng.choice([2, 3, 5])
    n = rng.randint(2, 5)
    k = rng.randint(1, 3)
    return "solve", f"{base}^(x + {k}) = {base ** (n + k)}"


GENERATORS = {
    "sign_error": g_sign, "one_side_only": g_one_side, "distribution_error": g_distribution,
    "arithmetic_slip": g_arithmetic, "exponent_rule": g_exponent, "inequality_flip": g_inequality,
    "derivative_rule": g_derivative, "antiderivative_error": g_integral,
    "lost_solution": g_lost_solution, "extra_solution": g_extra_solution, "general": g_arithmetic,
    "linear": g_arithmetic, "quadratic": g_quadratic, "simplify": g_simplify, "factor": g_factor,
    "derivative": g_derivative, "integral": g_integral, "inequality": g_inequality,
    "system": g_system, "limit": g_limit, "exponential": g_exponential,
}


def problem_latex(kind, math):
    pl = parse_line(math, natural_log=True)
    if kind in ("differentiate",):
        return r"\frac{d}{dx}\left[" + tex(pl.parts[0].sides[0].expr) + r"\right]"
    if kind == "integrate":
        return r"\int " + tex(pl.parts[0].sides[0].expr) + r"\,dx"
    parts = []
    for p in pl.parts:
        from .items import REL_TEX
        out = tex(p.sides[0].raw)
        for op, s in zip(p.ops, p.sides[1:]):
            out += f" {REL_TEX[op]} {tex(s.raw)}"
        parts.append(out)
    return r",\quad ".join(parts)


def make_problems(skill: str, count: int = 3, level: int = 1, seed=None) -> list[dict]:
    if skill not in GENERATORS:
        skill = "general"
    rng = random.Random(seed if seed is not None else random.randrange(1 << 30))
    gen = GENERATORS[skill]
    title, topic = SKILL_INFO.get(skill, ("Practice", "linear"))
    out, seen = [], set()
    attempts = 0
    while len(out) < count and attempts < count * 20:
        attempts += 1
        kind, math = gen(rng, max(1, min(3, level)))
        if math in seen:
            continue
        try:
            if not compute_answer({"kind": kind, "math": math}).get("available"):
                continue
            ltx = problem_latex(kind, math)
        except Exception:
            continue
        seen.add(math)
        out.append({
            "id": f"{skill}-{abs(hash(math)) % 10 ** 8}",
            "skill": skill, "topic": topic, "title": title, "kind": kind,
            "prompt": KIND_PROMPT[kind], "math": math, "latex": ltx, "level": level,
        })
    return out


# --------------------------------------------------------------------------
# answers
# --------------------------------------------------------------------------

def _first_part(math):
    pl = parse_line(math, natural_log=True)
    return pl, pl.parts[0]


def compute_answer(problem: dict) -> dict:
    """The verified answer (only sent when the student asks for it)."""
    kind, math = problem.get("kind"), problem.get("math", "")
    try:
        pl, p = _first_part(math)
        e = p.sides[0].expr
        if kind == "solve":
            if p.is_inequality:
                item = Item.relation(0, [s.expr for s in p.sides], p.ops)
                s = solution_set(item, x)
                if s is None:
                    return {"available": False}
                from .classify import interval_tex
                return {"available": True, "latex": interval_tex(x, s)}
            item = Item.equation(0, p.sides[0].expr, p.sides[1].expr)
            s = solution_set(item, x)
            if s is None or not s.is_FiniteSet or not s.args:
                return {"available": False}
            if any(not v.is_Rational for v in s.args):
                return {"available": False}
            return {"available": True,
                    "latex": r" \text{ or } ".join(f"x = {tex(v)}" for v in sorted(s.args))}
        if kind == "solve_system":
            eqs = [Item.equation(0, q.sides[0].expr, q.sides[1].expr) for q in pl.parts]
            syms = strip_constants(item_symbols(Item.system(0, eqs)))
            sols = system_solutions(eqs, syms)
            if not sols or len(sols) != 1:
                return {"available": False}
            sol = sols[0]
            return {"available": True, "latex": ", ".join(
                f"{tex(k)} = {tex(v)}" for k, v in sorted(sol.items(), key=lambda kv: kv[0].name))}
        if kind == "expand":
            return {"available": True, "latex": tex(expand(e))}
        if kind == "simplify":
            return {"available": True, "latex": tex(simplify(e))}
        if kind == "factor":
            return {"available": True, "latex": tex(factor(e))}
        if kind == "differentiate":
            d = limited(lambda: diff(e, x), 2.0, None)
            if d is None:
                return {"available": False}
            from .classify import nice_form
            return {"available": True, "latex": tex(nice_form(d))}
        if kind == "integrate":
            from .calculus import correct_antiderivative
            a = correct_antiderivative(e, x)
            if a is None:
                return {"available": False}
            return {"available": True, "latex": tex(a) + " + C"}
        if kind == "limit":
            v = limited(lambda: e.doit(), 2.0, None)
            if v is None or v.has(Integral) or not v.is_number:
                return {"available": False}
            return {"available": True, "latex": tex(v)}
    except EngineTimeout:
        return {"available": False}
    except Exception:
        return {"available": False}
    return {"available": False}


def _is_expanded(e) -> bool:
    for node in [e] + list(e.atoms(Mul, Pow)) + [n for n in _walk(e)]:
        if node.is_Pow and node.base.is_Add and node.exp.is_Integer and node.exp > 1:
            return False
        if node.is_Mul and any(f.is_Add for f in node.args):
            return False
    return True


def _walk(e):
    for a in e.args:
        yield a
        yield from _walk(a)


def check_answer(problem: dict, answer: str) -> dict:
    """Is the student's final answer right? Uses the engine, never an AI."""
    kind, math = problem.get("kind"), problem.get("math", "")
    answer = (answer or "").strip()
    if not answer:
        return {"correct": False, "message": "Type an answer first."}
    try:
        pl, p = _first_part(math)
    except Exception:
        return {"correct": False, "message": "This problem couldn't be read."}
    natural = True
    try:
        if kind == "solve":
            text = answer
            if not re.search(r"[=<>≤≥]", text):
                values = [v.strip() for v in re.split(r",|\bor\b", text) if v.strip()]
                text = " or ".join(f"x = {v}" for v in values)
            ans, err = try_parse_line(text, natural_log=natural)
            if ans is None:
                return {"correct": False, "message": f"Couldn't read your answer: {err}"}
            if p.is_inequality:
                prob = Item.relation(0, [s.expr for s in p.sides], p.ops)
            else:
                prob = Item.equation(0, p.sides[0].expr, p.sides[1].expr)
            if ans.connective == "or":
                a_item = Item.disjunction(0, [Item.equation(0, q.sides[0].expr, q.sides[1].expr)
                                              for q in ans.parts if q.is_equation])
            else:
                q = ans.parts[0]
                if q.is_inequality:
                    a_item = Item.relation(0, [s.expr for s in q.sides], q.ops)
                elif q.is_equation and len(q.sides) == 2:
                    a_item = Item.equation(0, q.sides[0].expr, q.sides[1].expr)
                else:
                    return {"correct": False, "message": "Write your answer like x = 4."}
            v = relation_equivalent(prob, a_item, x, decimals=ans.decimals)
            if v.equal is None:
                return {"correct": False, "message": "We couldn't verify that answer."}
            if not v.equal:
                return {"correct": False, "message": "Not quite. Check your work and try again."}
            solved = _is_solved_form(ans)
            if not solved:
                return {"correct": False, "equivalent": True,
                        "message": "That's equivalent, but not solved yet — get x by itself."}
            return {"correct": True, "message": "Correct!" + (" (rounded)" if v.reason == "rounded" else "")}
        if kind == "solve_system":
            ans, err = try_parse_line(answer.replace(" and ", ", "), natural_log=natural)
            if ans is None:
                return {"correct": False, "message": f"Couldn't read your answer: {err}"}
            eqs = [Item.equation(0, q.sides[0].expr, q.sides[1].expr) for q in pl.parts]
            syms = strip_constants(item_symbols(Item.system(0, eqs)))
            sols = system_solutions(eqs, syms)
            given = {}
            for q in ans.parts:
                if q.is_equation and len(q.sides) == 2 and isinstance(q.sides[0].expr, Symbol):
                    given[q.sides[0].expr] = q.sides[1].expr
            if not sols or set(given) != set(syms):
                return {"correct": False, "message": "Give a value for each variable, like x = 1, y = 2."}
            ok = all(expr_equivalent_plain(sols[0][k], given[k], allow_domain=False).equal for k in syms)
            return {"correct": bool(ok), "message": "Correct!" if ok else "Not quite. Try again."}

        ans, err = try_parse_line(answer, natural_log=natural)
        if ans is None:
            return {"correct": False, "message": f"Couldn't read your answer: {err}"}
        q = ans.parts[0]
        a_expr = q.sides[-1].expr if q.ops else q.sides[0].expr
        e = p.sides[0].expr
        if kind == "integrate":
            d = limited(lambda: diff(a_expr, x), 2.0, None)
            ok = d is not None and expr_equivalent_plain(d, e, allow_domain=False).equal
            if not ok:
                return {"correct": False, "message": "Not quite. Differentiate your answer to check it."}
            from .calculus import has_constant_of_integration
            msg = "Correct!" if has_constant_of_integration(a_expr) else "Correct — don't forget + C."
            return {"correct": True, "message": msg}
        if kind == "differentiate":
            target = diff(e, x)
        elif kind == "limit":
            target = limited(lambda: e.doit(), 2.0, None)
            if target is None:
                return {"correct": False, "message": "We couldn't verify that answer."}
        else:
            target = e
        v = expr_equivalent_plain(target, a_expr, allow_domain=False)
        if not v.equal:
            return {"correct": False, "message": "Not quite. Check your work and try again."}
        if kind == "expand" and not _is_expanded(a_expr if True else q.sides[0].raw):
            return {"correct": False, "equivalent": True, "message": "Equivalent — now multiply it all out."}
        if kind == "factor":
            raw = q.sides[-1].raw if q.ops else q.sides[0].raw
            if not (raw.is_Mul or raw.is_Pow):
                return {"correct": False, "equivalent": True, "message": "Equivalent — now write it as a product."}
        if kind == "simplify":
            simplest = simplify(target)
            if a_expr.count_ops() > simplest.count_ops() + 2:
                return {"correct": False, "equivalent": True, "message": "Equivalent — can you simplify it further?"}
        return {"correct": True, "message": "Correct!"}
    except EngineTimeout:
        return {"correct": False, "message": "We couldn't verify that answer in time."}


def _is_solved_form(ans) -> bool:
    for q in ans.parts:
        if not q.ops:
            return False
        lhs, rhs = q.sides[0].expr, q.sides[-1].expr
        if isinstance(lhs, Symbol) and not rhs.free_symbols:
            continue
        if isinstance(rhs, Symbol) and not lhs.free_symbols:
            continue
        return False
    return True
