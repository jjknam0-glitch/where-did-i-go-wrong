"""Randomized engine evaluation.

Builds random problems, solves them with random *valid* steps, and checks:
  * false alarms: correct lines flagged as errors (must be zero), and
  * localization: after planting one error, is the circled line the planted one?

Run:  python -m eval.engine_stress [N]
"""

import random
import sys
import time

from sympy import Eq, Rational, Symbol, expand, factor, latex, sstr

from app.engine.checker import check_lines

x = Symbol("x")


def text(e):
    return sstr(e).replace("**", "^")


def random_linear(rng):
    sol = rng.randint(-9, 9)
    a, c = rng.sample([v for v in range(-9, 10) if v not in (0,)], 2)
    b = rng.randint(-15, 15)
    d = a * sol + b - c * sol
    k = rng.choice([1, 1, 2, -3])
    if k * a == c:
        c += 1 if c != -1 else 2
        d = a * sol + b - c * sol
    L = k * (a * x + b) if k != 1 else a * x + b
    return Eq(L, c * x + d, evaluate=False)


def valid_step(rng, L, R):
    op = rng.random()
    if op < 0.25:
        t = rng.choice([t for t in (L.as_ordered_terms() + R.as_ordered_terms())])
        return expand(L - t), expand(R - t)
    if op < 0.45:
        k = rng.choice([2, 3, -1, -2])
        return expand(k * L), expand(k * R)
    if op < 0.65:
        f = expand(L - R)
        coeff = f.coeff(x)
        if coeff != 0:
            return x, -(f - coeff * x) / coeff
        return L, R
    if op < 0.8:
        return R, L
    return expand(L), expand(R)


def chain(rng, steps=4, plant_at=None):
    """A correct solution; with plant_at, one step adds a slip and later steps follow from it."""
    eq = random_linear(rng)
    L, R = eq.lhs, eq.rhs
    lines = [f"{text(L)} = {text(R)}"]
    for i in range(1, steps + 1):
        L, R = valid_step(rng, L, R)
        if i == plant_at:
            R = R + rng.choice([1, -1, 2, -2])
        lines.append(f"{text(L)} = {text(R)}")
    return lines


def plant_error(rng, lines):
    i = rng.randint(1, len(lines) - 1)
    bad = list(lines)
    s = bad[i]
    import re
    nums = list(re.finditer(r"(?<![\^\w])\d+", s))
    if not nums:
        return None, None
    m = rng.choice(nums)
    delta = rng.choice([1, -1, 2])
    new = str(max(0, int(m.group()) + delta))
    if new == m.group():
        return None, None
    bad[i] = s[:m.start()] + new + s[m.end():]
    return bad, i


def main(n=200, seed=1):
    rng = random.Random(seed)
    false_alarms = located = planted = uncertain_correct = 0
    t0 = time.time()
    for k in range(n):
        lines = chain(rng, rng.randint(2, 5))
        res = check_lines([{"index": i, "math": m} for i, m in enumerate(lines)])
        st = [l["status"] for l in res["lines"]]
        if "error" in st:
            false_alarms += 1
            print("FALSE ALARM:", lines, st)
        if "uncertain" in st:
            uncertain_correct += 1
            print("UNCERTAIN on correct work:", lines, st)
        steps = rng.randint(2, 5)
        i = rng.randint(1, steps)
        bad = chain(rng, steps, plant_at=i)
        res = check_lines([{"index": j, "math": m} for j, m in enumerate(bad)])
        planted += 1
        if res["first_error"] == i:
            located += 1
        else:
            print("MISSED:" if res["first_error"] is None else "MISLOCATED:", bad, "planted", i,
                  "got", res["first_error"], [l["status"] for l in res["lines"]], res["sanity_check"])
    dt = time.time() - t0
    print(f"\n{n} correct solutions: {false_alarms} false alarms, {uncertain_correct} with uncertain lines")
    print(f"{planted} planted errors: located {located} ({located / max(planted, 1):.0%})")
    print(f"{dt:.1f}s total")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200)
