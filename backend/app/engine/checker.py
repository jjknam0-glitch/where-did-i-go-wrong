"""Check a whole problem, line by line.

Each line is compared only to the line before it; the first pair that is not
equivalent is the error. Later lines that correctly follow from the mistake
are marked ``follows_from_error``. Notes are skipped. Anything the engine
cannot verify is marked ``uncertain`` instead of guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sympy import (
    Derivative, Integral, Limit, S, Symbol, diff, latex, simplify, solve_univariate_inequality,
)

from . import hints as H
from .classify import Classification, StepContext, classify_step
from .equivalence import (
    Verdict, evaluate_operators, expr_equivalent, expr_equivalent_plain, has_calculus,
    implied_by, indefinite_integrals, item_symbols, relation_equivalent, solution_set,
    strip_constants, system_solutions,
)
from .items import Item, tex
from .parsing import (
    Label, ParsedLine, is_constant_symbol, looks_like_calculus, plain_letter, try_parse_line,
)
from .timeout import Budget, EngineTimeout, limited

STATUS_START = "start"
STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_WARNING = "warning"
STATUS_FOLLOWS = "follows_from_error"
STATUS_UNCERTAIN = "uncertain"
STATUS_SKIPPED = "skipped"

REASON_TEXT = {
    "parse_error": "We couldn't read this line as math.",
    "inconclusive": "We couldn't verify this step either way.",
    "timeout": "This step took too long to verify.",
    "substitution": "Substitution steps can't be verified automatically yet.",
    "mixed": "This line can't be compared with the line before (an equation next to an expression).",
    "gap": "We can't tell which step broke, because the line before couldn't be checked.",
    "unsolvable": "We couldn't solve these equations to compare them.",
    "multivariable": "Steps with several variables like this can't be verified yet.",
    "sanity_conflict": ("Your final answer is right, but this step doesn't seem to follow. "
                        "Please double-check that we read this line correctly."),
    "sanity": "The final answer doesn't match the original problem, so we can't fully trust this step.",
    "limit_unevaluated": "We couldn't evaluate this limit.",
    "derivative_unevaluated": "We couldn't evaluate this derivative.",
    "unsupported": "This kind of line isn't supported yet.",
    "budget": "We ran out of time checking this problem.",
}


@dataclass
class LineResult:
    index: int
    status: str = STATUS_OK
    tier: str | None = None
    error_type: str | None = None
    subtype: str | None = None
    hints: list = field(default_factory=list)
    corrected: str | None = None
    note: str | None = None
    reason: str | None = None
    message: str | None = None
    lesson: str | None = None
    compared_to: int | None = None
    facts: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {"index": self.index, "status": self.status}
        for key in ("tier", "error_type", "subtype", "corrected", "note", "reason", "message",
                    "lesson", "compared_to"):
            v = getattr(self, key)
            if v is not None:
                d[key] = v
        if self.hints:
            d["hints"] = self.hints
        if self.error_type:
            d["error_name"] = H.ERROR_NAMES.get(self.error_type, "Mistake")
        return d


# --------------------------------------------------------------------------
# set-up: parsing, variable and mode
# --------------------------------------------------------------------------

def _main_variable(parsed: list[ParsedLine]) -> Symbol:
    counts: dict = {}
    for pl in parsed:
        for s in pl.symbols:
            if is_constant_symbol(s):
                continue
            counts[s] = counts.get(s, 0) + 1
    for name in ("x", "t", "theta", "y", "z", "n", "a"):
        for s in counts:
            if s.name == name:
                return s
    if counts:
        return max(counts, key=lambda s: (counts[s], -ord(s.name[0])))
    return Symbol("x")


def _detect_mode(parsed: list, var) -> str:
    first = parsed[0]
    if first.connective == "and":
        return "system"
    if first.connective == "or":
        return "equation"
    fp = first.parts[0]
    if fp.label is not None:
        return "function"
    if fp.is_equation and len(fp.sides) == 2:
        letter = plain_letter(fp.sides[0].text)
        if letter and Symbol(letter) != var and Symbol(letter) not in fp.sides[1].expr.free_symbols:
            if any(p.parts[0].label is not None and p.parts[0].label.name == letter
                   for p in parsed[1:] if len(p.parts) == 1):
                fp.label = Label(letter, 0)
                fp.sides = fp.sides[1:]
                fp.ops = []
                return "function"
    if fp.is_expression:
        return "expression"
    if has_calculus(fp.sides[0].expr):
        return "expression"
    if fp.is_equation:
        later = parsed[1:]
        all_expr_like = bool(later) and all(
            p.continuation or (len(p.parts) == 1 and p.parts[0].is_expression) for p in later)
        if all_expr_like or len(fp.sides) > 2:
            if all(_identity(fp.sides[0].expr, s.expr) for s in fp.sides[1:]):
                return "expression"
        return "equation"
    return "equation"


def _identity(a, b) -> bool:
    try:
        return expr_equivalent_plain(a, b, allow_domain=False).equal is True
    except EngineTimeout:
        return False


# --------------------------------------------------------------------------
# items per line
# --------------------------------------------------------------------------

@dataclass
class BuildResult:
    items: list = field(default_factory=list)
    reason: str | None = None
    skip_note: str | None = None
    substitution: tuple | None = None
    new_chain: bool = False


_DIFFERENTIAL_RE = re.compile(r"^\s*d\s*[a-z]\s*=")


def _eq_items_from_part(part, line, prev_eq=None, continuation=False):
    items = []
    sides = part.sides
    if continuation and prev_eq is not None:
        for s in sides:
            items.append(Item.equation(line, prev_eq.lhs, s.expr, prev_eq.raw_lhs, s.raw))
        return items
    for s in sides[1:]:
        items.append(Item.equation(line, sides[0].expr, s.expr, sides[0].raw, s.raw))
    return items


def _relation_item(part, line):
    if "=" in part.ops:
        return None
    return Item.relation(line, [s.expr for s in part.sides], part.ops, [s.raw for s in part.sides])


def _build_items(pl: ParsedLine, line: int, mode: str, state) -> BuildResult:
    parts = pl.parts
    if mode == "system":
        if pl.connective == "and":
            eqs = []
            for p in parts:
                if not p.is_equation or len(p.sides) != 2:
                    return BuildResult(reason="unsupported")
                eqs.append(Item.equation(line, p.sides[0].expr, p.sides[1].expr, p.sides[0].raw, p.sides[1].raw))
            return BuildResult([Item.system(line, eqs)])
        if pl.connective == "or":
            return BuildResult(reason="unsupported")
        p = parts[0]
        if p.is_equation:
            return BuildResult([Item.system(line, _eq_items_from_part(p, line))])
        return BuildResult(reason="unsupported")

    if mode == "equation":
        if pl.connective == "and":
            return BuildResult(reason="unsupported")
        if pl.connective == "or":
            eqs = []
            for p in parts:
                if not p.is_equation or len(p.sides) != 2:
                    return BuildResult(reason="unsupported")
                eqs.append(Item.equation(line, p.sides[0].expr, p.sides[1].expr, p.sides[0].raw, p.sides[1].raw))
            return BuildResult([Item.disjunction(line, eqs)])
        p = parts[0]
        if p.label is not None:
            return BuildResult(reason="unsupported")
        if p.is_expression:
            if pl.continuation and state.last_eq is not None:
                return BuildResult(_eq_items_from_part(p, line, state.last_eq, True))
            return BuildResult(reason="mixed")
        if p.is_equation:
            return BuildResult(_eq_items_from_part(p, line, state.last_eq, pl.continuation))
        it = _relation_item(p, line)
        return BuildResult([it]) if it is not None else BuildResult(reason="unsupported")

    if mode == "expression":
        if pl.connective is not None:
            return BuildResult(reason="unsupported")
        p = parts[0]
        if _DIFFERENTIAL_RE.match(pl.text.replace(" ", " ")):
            return BuildResult(skip_note="differential")
        if p.is_inequality:
            return BuildResult(reason="mixed")
        if p.is_equation and len(p.sides) == 2 and isinstance(p.sides[0].expr, Symbol):
            sym = p.sides[0].expr
            if sym != state.var and sym not in state.seen_symbols and p.sides[1].expr.has(state.var):
                return BuildResult(skip_note="substitution", substitution=(sym, p.sides[1].expr))
        return BuildResult([Item.expression(line, s.expr, s.raw) for s in p.sides])

    # function mode
    if pl.connective is not None:
        return BuildResult(reason="unsupported")
    p = parts[0]
    label = p.label
    if label is None and p.is_equation and len(p.sides) >= 2:
        letter = plain_letter(p.sides[0].text)
        if letter and letter in state.label_names:
            label = Label(letter, 0)
            p = type(p)(p.sides[1:], p.ops[1:], label)
    if label is not None:
        return BuildResult([Item.expression(line, s.expr, s.raw, (label.name, label.order)) for s in p.sides])
    if p.is_expression:
        return BuildResult([Item.expression(line, s.expr, s.raw, None) for s in p.sides])
    # An equation inside a function problem (e.g. solving f'(x) = 0) starts a new chain.
    if p.is_equation:
        if state.prev is not None and state.prev.kind == "eq":
            return BuildResult(_eq_items_from_part(p, line, state.last_eq, pl.continuation))
        return BuildResult(_eq_items_from_part(p, line), new_chain=True)
    it = _relation_item(p, line)
    if it is None:
        return BuildResult(reason="unsupported")
    return BuildResult([it], new_chain=state.prev is None or state.prev.kind != "rel")


# --------------------------------------------------------------------------
# comparing two items
# --------------------------------------------------------------------------

@dataclass
class Outcome:
    verdict: Verdict
    ctx: StepContext | None = None
    note: str | None = None
    definition: bool = False


class WalkState:
    def __init__(self, var, mode, seed):
        self.var = var
        self.mode = mode
        self.seed = seed
        self.prev: Item | None = None
        self.prev_math_line: int | None = None
        self.last_eq: Item | None = None
        self.defs: dict = {}
        self.subs: dict = {}
        self.seen_symbols: set = set()
        self.label_names: set = set()
        self.system_solutions = None
        self.system_syms = set()
        self.all_items: list = []
        self.max_decimals = 0


def _solutions_list(item: Item, var):
    if item.kind == "rel" and len(item.sides) == 2:
        # The boundary of an inequality: where the two sides are equal.
        item = Item.equation(item.line, item.sides[0], item.sides[1])
    s = solution_set(item, var) if item.kind in ("eq", "or", "rel") else None
    try:
        if s is not None and s.is_FiniteSet:
            return [v for v in s.args if v.is_real is not False]
    except Exception:
        pass
    return []


def _make_valid(mode, prev: Item, var, state: WalkState, target=None, decimals=0):
    seed = state.seed

    def valid(cand: Item) -> bool:
        if mode in ("expression", "derivative", "integral") and cand.kind == "expr":
            if mode == "integral":
                return expr_equivalent(prev.expr, cand.expr, var, subs=state.subs, seed=seed).equal is True
            if target is None:
                return False
            return expr_equivalent_plain(target, cand.expr, seed=seed).equal is True
        if mode == "system":
            sub_eqs = cand.eqs if cand.kind == "sys" else [cand]
            return implied_by(state.system_solutions, sub_eqs, seed=seed) is True
        if cand.kind in ("eq", "or", "rel") and prev.kind in ("eq", "or", "rel"):
            return relation_equivalent(prev, cand, var, decimals=decimals, seed=seed).equal is True
        return False

    return valid


def _compare(prev: Item, cur: Item, state: WalkState, decimals: int) -> Outcome:
    var, seed = state.var, state.seed
    mode = state.mode

    if mode == "system":
        sub_eqs = cur.eqs if cur.kind == "sys" else [cur]
        res = implied_by(state.system_solutions, sub_eqs, seed=seed)
        v = Verdict(res, "verified" if res is not None else None,
                    reason="" if res is not None else "unsolvable")
        ctx = StepContext("system", var, _make_valid("system", prev, var, state), seed,
                          system_solutions=state.system_solutions)
        return Outcome(v, ctx)

    if cur.kind == "expr" and prev.kind == "expr":
        # Function mode: labels decide what to compare against.
        if cur.label is not None:
            name, order = cur.label
            if prev.label == cur.label:
                pass
            elif (name, order) in state.defs:
                prev = Item.expression(prev.line, state.defs[(name, order)], label=cur.label)
            elif (name, order - 1) in state.defs:
                F = state.defs[(name, order - 1)]
                target = limited(lambda: diff(F, var), 2.0, None)
                if target is None:
                    return Outcome(Verdict(None, reason="timeout"))
                v = expr_equivalent(target, cur.expr, var, seed=seed)
                ctx = StepContext("derivative", var, None, seed, target=target, func=F)
                ctx.valid = _make_valid("derivative", prev, var, state, target)
                return Outcome(v, ctx)
            else:
                return Outcome(Verdict(True, None), definition=True)
        elif prev.label is not None:
            cur.label = prev.label

        v = expr_equivalent(prev.expr, cur.expr, var, subs=state.subs, seed=seed)
        note = None
        sub_mode, target, func, integrand = "expression", None, None, None
        pe = prev.expr
        if isinstance(pe, Derivative) and not cur.expr.has(Derivative):
            sub_mode, func = "derivative", pe.expr
        elif isinstance(pe, Integral) and indefinite_integrals(pe) and not cur.expr.has(Integral):
            sub_mode, integrand = "integral", pe.function
            if v.equal and not any(is_constant_symbol(s) for s in cur.expr.free_symbols):
                note = "Don't forget the constant of integration: $+\\,C$."
        if sub_mode != "integral":
            target, _ = evaluate_operators(apply_subs(prev.expr, state))
        ctx = StepContext(sub_mode, var, None, seed, target=target, func=func, integrand=integrand)
        ctx.valid = _make_valid(sub_mode, prev, var, state, target)
        return Outcome(v, ctx, note)

    if cur.kind in ("eq", "or", "rel") and prev.kind in ("eq", "or", "rel"):
        v = relation_equivalent(prev, cur, var, decimals=decimals, seed=seed)
        ctx = StepContext("equation", var, _make_valid("equation", prev, var, state, decimals=decimals),
                          seed, a_solutions=_solutions_list(prev, var))
        note = None
        if v.equal and v.reason == "rounded":
            exact = solution_set(prev, var)
            note = "Rounded answer — fine. The exact value is $" + _set_tex(exact) + "$." if exact is not None \
                else "Rounded answer."
        return Outcome(v, ctx, note)

    return Outcome(Verdict(None, reason="mixed"))


def apply_subs(e, state):
    from .equivalence import apply_substitutions
    return apply_substitutions(e, state.subs, state.var)


def _set_tex(s) -> str:
    try:
        if s.is_FiniteSet:
            return ", ".join(tex(v) for v in s.args)
        return latex(s)
    except Exception:
        return str(s)


# --------------------------------------------------------------------------
# main entry point
# --------------------------------------------------------------------------

def check_lines(lines: list[dict], *, acknowledge_sanity: bool = False,
                budget_seconds: float = 30.0) -> dict:
    budget = Budget(budget_seconds)
    texts = [str(l.get("math") or "") for l in lines]
    natural_log = looks_like_calculus(texts)
    results: list[LineResult] = []
    parsed_by_line: dict[int, ParsedLine] = {}

    for pos, l in enumerate(lines):
        idx = int(l.get("index", pos))
        r = LineResult(idx)
        results.append(r)
        if (l.get("type") == "note") or not str(l.get("math") or "").strip():
            r.status = STATUS_SKIPPED
            continue
        pl, err = try_parse_line(l.get("math"), natural_log=natural_log)
        if pl is None:
            r.status = STATUS_UNCERTAIN
            r.reason = "parse_error"
            r.message = f"{REASON_TEXT['parse_error']} ({err})"
            continue
        parsed_by_line[pos] = pl

    math_positions = [p for p in range(len(lines)) if p in parsed_by_line]
    if not math_positions:
        return _finish(results, None, "skipped", None, None, "none")

    parsed_list = [parsed_by_line[p] for p in math_positions]
    var = _main_variable(parsed_list)
    try:
        mode = _detect_mode(parsed_list, var)
    except EngineTimeout:
        mode = "equation"
    seed = "|".join(texts)
    state = WalkState(var, mode, seed)
    for pl in parsed_list:
        for p in pl.parts:
            if p.label is not None:
                state.label_names.add(p.label.name)

    first_error: int | None = None
    first_item: Item | None = None
    last_item: Item | None = None
    any_math_line_seen = False
    prev_pos: int | None = None  # position of the line that produced state.prev

    for pos, l in enumerate(lines):
        r = results[pos]
        if r.status == STATUS_SKIPPED:
            continue
        if pos not in parsed_by_line:
            continue
        pl = parsed_by_line[pos]
        state.max_decimals = max(state.max_decimals, pl.decimals)
        if budget.exhausted():
            r.status, r.reason, r.message = STATUS_UNCERTAIN, "budget", REASON_TEXT["budget"]
            continue
        try:
            built = _build_items(pl, r.index, mode, state)
        except EngineTimeout:
            built = BuildResult(reason="timeout")
        if built.skip_note:
            r.status = STATUS_SKIPPED
            if built.substitution:
                sym, val = built.substitution
                state.subs[sym] = val
                r.note = f"Substitution: ${tex(sym)} = {tex(val)}$"
            continue
        if built.reason:
            r.status, r.reason = STATUS_UNCERTAIN, built.reason
            r.message = REASON_TEXT.get(built.reason)
            continue

        line_statuses = []
        for item in built.items:
            state.seen_symbols |= item_symbols(item)
            if state.prev is None or built.new_chain:
                if state.prev is None and mode == "system":
                    state.system_syms = strip_constants(item_symbols(item))
                    state.system_solutions = system_solutions(item.eqs, state.system_syms)
                if first_item is None:
                    first_item = item
                line_statuses.append((STATUS_START, None, None, None))
                built.new_chain = False
                _accept(state, item)
                prev_pos = pos
                continue

            gap = _has_gap(prev_pos, pos, results)
            try:
                out = _compare(state.prev, item, state, pl.decimals)
            except EngineTimeout:
                out = Outcome(Verdict(None, reason="timeout"))
            except RecursionError:
                out = Outcome(Verdict(None, reason="inconclusive"))
            v = out.verdict
            if out.definition:
                line_statuses.append((STATUS_START, None, None, None))
            elif v.equal is True:
                if v.reason == "domain_positive":
                    line_statuses.append((STATUS_WARNING, v, None, out))
                else:
                    status = STATUS_FOLLOWS if first_error is not None else STATUS_OK
                    line_statuses.append((status, v, None, out))
            elif v.equal is False:
                if gap:
                    line_statuses.append((STATUS_UNCERTAIN, Verdict(None, reason="gap"), None, out))
                else:
                    try:
                        c = classify_step(state.prev, item, out.ctx, v) if out.ctx else \
                            Classification("general")
                    except EngineTimeout:
                        c = Classification("general")
                    if c.warning:
                        line_statuses.append((STATUS_WARNING, v, c, out))
                    else:
                        line_statuses.append((STATUS_ERROR, v, c, out))
            else:
                line_statuses.append((STATUS_UNCERTAIN, v, None, out))
            prev_line = state.prev.line
            _accept(state, item)
            prev_pos = pos
            line_statuses[-1] = line_statuses[-1] + (prev_line,)
        _summarize_line(r, line_statuses, first_error is not None)
        if r.status == STATUS_ERROR and first_error is None:
            first_error = r.index
        if built.items:
            last_item = built.items[-1]
        any_math_line_seen = True

    # Whole-problem sanity check.
    sanity = "skipped"
    if first_item is not None and last_item is not None and first_item is not last_item \
            and not budget.exhausted():
        try:
            sanity, first_error = _sanity_check(first_item, last_item, results, first_error, state,
                                                acknowledge_sanity)
        except EngineTimeout:
            sanity = "skipped"

    topic = detect_topic(parsed_list, mode, var)
    return _finish(results, first_error, sanity, mode, var, topic)


def _has_gap(prev_pos, pos, results) -> bool:
    if prev_pos is None:
        return False
    for p in range(prev_pos + 1, pos):
        if results[p].status not in (STATUS_SKIPPED,):
            return True
    return False


def _accept(state: WalkState, item: Item):
    state.prev = item
    state.all_items.append(item)
    if item.kind == "eq":
        state.last_eq = item
    if item.kind == "expr" and item.label is not None:
        state.defs[item.label] = item.expr


def _summarize_line(r: LineResult, statuses, after_error: bool):
    """Combine the comparisons inside one line into a single status."""
    if not statuses:
        return
    rank = {STATUS_ERROR: 5, STATUS_UNCERTAIN: 4, STATUS_WARNING: 3, STATUS_FOLLOWS: 2,
            STATUS_OK: 1, STATUS_START: 0}
    worst = max(statuses, key=lambda s: rank[s[0]])
    status, v, c, out = worst[0], worst[1], worst[2], worst[3]
    compared_to = worst[4] if len(worst) > 4 else None
    r.status = status
    r.compared_to = compared_to
    if status == STATUS_START:
        if all(s[0] == STATUS_START for s in statuses):
            return
    if v is not None and v.tier:
        r.tier = v.tier
    if out is not None and out.note:
        r.note = out.note
    if status == STATUS_UNCERTAIN:
        reason = v.reason if v is not None and v.reason else "inconclusive"
        r.reason = reason
        r.message = REASON_TEXT.get(reason, REASON_TEXT["inconclusive"])
        r.tier = None
    elif status == STATUS_WARNING and c is None:
        r.error_type = "domain"
        r.note = "This step is only true when the variable is positive. Check whether that's given."
    if c is not None:
        r.error_type = c.error_type
        r.subtype = c.subtype
        r.corrected = c.corrected
        from_line = (compared_to if compared_to is not None else r.index) + 1
        r.hints = H.build_hints(c, from_line, r.index + 1)
        r.lesson = H.lesson_for(c)
        r.facts = c.facts


def _sanity_check(first_item, last_item, results, first_error, state, acknowledge):
    var = state.var
    if state.mode == "system":
        # Collect "variable = number" results, latest first, until every unknown is known.
        known = {}
        for it in reversed(state.all_items):
            for e in (it.eqs if it.kind == "sys" else [it] if it.kind == "eq" else []):
                if isinstance(e.lhs, Symbol) and e.rhs.is_number and e.lhs not in known:
                    known[e.lhs] = e.rhs
        if not state.system_syms or not state.system_syms <= set(known) or not state.system_solutions:
            return "skipped", first_error
        sols = state.system_solutions
        same = len(sols) == 1 and all(
            k in sols[0] and expr_equivalent_plain(sols[0][k], known[k], allow_domain=False).equal
            for k in state.system_syms)
    elif first_item.kind == "expr" and last_item.kind == "expr":
        if first_item.label is not None or last_item.label is not None:
            if first_item.label != last_item.label:
                return "skipped", first_error
        v = expr_equivalent(first_item.expr, last_item.expr, var, subs=state.subs, seed=state.seed)
        if v.equal is None:
            return "skipped", first_error
        same = v.equal
    elif first_item.kind in ("eq", "or", "rel") and last_item.kind in ("eq", "or", "rel"):
        v = relation_equivalent(first_item, last_item, var, decimals=state.max_decimals, seed=state.seed)
        if v.equal is None:
            return "skipped", first_error
        same = v.equal
    else:
        return "skipped", first_error

    has_warning = any(r.status == STATUS_WARNING for r in results)
    if first_error is None:
        if same:
            return "consistent", first_error
        if has_warning:
            return "final_differs", first_error
        # Every step passed but the answer is wrong: distrust numeric-only steps.
        suspects = [r for r in results if r.status == STATUS_OK and r.tier == "numeric"]
        if not suspects:
            suspects = [r for r in reversed(results) if r.status == STATUS_OK][:1]
        for r in suspects:
            r.status, r.reason, r.message = STATUS_UNCERTAIN, "sanity", REASON_TEXT["sanity"]
            r.tier = None
        return "inconsistent", first_error

    if same:
        if acknowledge:
            return "acknowledged", first_error
        # A step failed but the final answer is right: usually a misread line or
        # two mistakes that cancel. Ask instead of accusing.
        for r in results:
            if r.status == STATUS_ERROR:
                r.status = STATUS_UNCERTAIN
                r.reason = "sanity_conflict"
                r.message = REASON_TEXT["sanity_conflict"]
            elif r.status == STATUS_FOLLOWS:
                r.status = STATUS_OK
        return "conflict", None
    return "consistent", first_error


def detect_topic(parsed: list, mode: str, var) -> str:
    first = parsed[0]
    all_exprs = []
    for pl in parsed:
        for p in pl.parts:
            all_exprs += [s.expr for s in p.sides]
    if mode == "function" or any(e.has(Derivative) for e in all_exprs):
        if any(e.has(Integral) for e in all_exprs):
            return "integrals"
        return "derivatives"
    if any(e.has(Integral) for e in all_exprs):
        return "integrals"
    if any(e.has(Limit) for e in all_exprs):
        return "limits"
    if mode == "system":
        return "systems"
    fp = first.parts[0]
    if fp.is_inequality:
        return "inequalities"
    from sympy import exp, log, sin, cos, tan, sec, csc, cot, Poly
    if any(e.atoms(sin, cos, tan, sec, csc, cot) for e in all_exprs):
        return "trig"
    if any(e.atoms(exp, log) for e in all_exprs) or any(
            p.is_Pow and p.exp.has(var) for e in all_exprs for p in e.atoms(__import__("sympy").Pow)):
        return "exponentials"
    if mode == "expression":
        last = parsed[-1].parts[0].sides[-1].expr
        if last.is_Mul and any(f.is_Add or (f.is_Pow and f.base.is_Add) for f in last.args):
            return "factoring"
        return "simplifying"
    try:
        f = fp.sides[0].expr - fp.sides[-1].expr
        deg = Poly(f, var).degree()
        if deg == 2:
            return "quadratics"
        if deg == 1:
            return "linear"
    except Exception:
        pass
    return "equations"


ADVANCED_TOPICS = {"derivatives", "integrals", "limits"}


def _finish(results, first_error, sanity, mode, var, topic) -> dict:
    lines = [r.to_dict() for r in results]
    counts = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    error_line = next((r for r in results if r.index == first_error), None)
    all_good = first_error is None and not any(
        r.status in (STATUS_UNCERTAIN, STATUS_ERROR, STATUS_WARNING) for r in results)
    return {
        "lines": lines,
        "first_error": first_error,
        "error_type": error_line.error_type if error_line else None,
        "sanity_check": sanity,
        "mode": mode,
        "variable": str(var) if var is not None else None,
        "topic": topic,
        "advanced": topic in ADVANCED_TOPICS,
        "all_correct": all_good and sum(1 for r in results if r.status in (STATUS_OK, STATUS_START)) > 0
                       and any(r.status == STATUS_OK for r in results),
        "counts": counts,
    }


# --------------------------------------------------------------------------
# fix it yourself
# --------------------------------------------------------------------------

def check_fix(lines: list[dict], index: int, new_math: str, **kw) -> dict:
    """Check the student's rewrite of line ``index`` and, if it is right, re-check the rest."""
    positions = [i for i, l in enumerate(lines) if int(l.get("index", i)) == index]
    if not positions:
        raise ValueError("No such line")
    pos = positions[0]
    updated = [dict(l) for l in lines]
    updated[pos] = dict(updated[pos], math=new_math, type="equation")
    updated[pos].pop("latex", None)

    # First judge the fix on its own: everything up to and including the fixed line.
    head = updated[:pos + 1]
    head_result = check_lines(head, acknowledge_sanity=True, **kw)
    fixed_line = head_result["lines"][pos]
    valid = fixed_line["status"] in (STATUS_OK, STATUS_START, STATUS_WARNING)
    # A fix only counts if nothing before it is broken.
    earlier_problem = any(l["status"] in (STATUS_ERROR,) for l in head_result["lines"][:pos])
    if earlier_problem:
        valid = False
    full = check_lines(updated, **kw) if valid else None
    return {
        "valid": valid,
        "fix": fixed_line,
        "check": full,
        "lines": updated,
    }


# --------------------------------------------------------------------------
# the final answer (only when the student explicitly asks)
# --------------------------------------------------------------------------

def final_answer(lines: list[dict]) -> dict:
    texts = [str(l.get("math") or "") for l in lines if l.get("type") != "note"]
    natural_log = looks_like_calculus(texts)
    parsed = []
    for t in texts:
        if not t.strip():
            continue
        pl, err = try_parse_line(t, natural_log=natural_log)
        if pl is None:
            return {"available": False, "message": "The first line couldn't be read."}
        parsed.append(pl)
        break
    if not parsed:
        return {"available": False, "message": "There's nothing to solve."}
    pl = parsed[0]
    var = _main_variable([pl])
    p = pl.parts[0]
    try:
        if pl.connective == "and":
            eqs = [Item.equation(0, q.sides[0].expr, q.sides[1].expr) for q in pl.parts]
            syms = strip_constants(item_symbols(Item.system(0, eqs)))
            sols = system_solutions(eqs, syms)
            if not sols:
                return {"available": False, "message": "This system has no unique solution."}
            out = [", ".join(f"{tex(k)} = {tex(v)}" for k, v in sorted(s.items(), key=lambda kv: kv[0].name))
                   for s in sols]
            return {"available": True, "latex": r" \quad\text{or}\quad ".join(out)}
        if p.label is not None:
            e = p.sides[0].expr
            d = limited(lambda: simplify(diff(e, var)), 3.0, None)
            if d is None:
                return {"available": False, "message": "Couldn't compute this one in time."}
            name = p.label.name + "'" * (p.label.order + 1)
            return {"available": True, "latex": f"{name}({tex(var)}) = {tex(d)}"}
        if p.is_expression or has_calculus(p.sides[0].expr):
            e = p.sides[0].expr
            if indefinite_integrals(e):
                from sympy import integrate
                inner = e
                res = limited(lambda: inner.doit(), 3.0, None)
                if res is None or res.has(Integral):
                    return {"available": False, "message": "Couldn't compute this integral in time."}
                return {"available": True, "latex": tex(simplify(res)) + " + C"}
            val, _ = evaluate_operators(e, 3.0)
            if val is None:
                return {"available": False, "message": "Couldn't compute this one in time."}
            s = limited(lambda: simplify(val), 3.0, val)
            return {"available": True, "latex": tex(s)}
        item = (_relation_item(p, 0) if p.is_inequality
                else Item.equation(0, p.sides[0].expr, p.sides[-1].expr))
        if pl.connective == "or":
            return {"available": False, "message": "This line is already a list of answers."}
        if item is None:
            return {"available": False, "message": "This kind of problem can't be solved automatically."}
        if p.is_inequality:
            from sympy import Lt, Gt, Le, Ge
            rel = {"<": Lt, ">": Gt, "<=": Le, ">=": Ge}
            if len(p.ops) == 1:
                r = limited(lambda: solve_univariate_inequality(
                    rel[p.ops[0]](p.sides[0].expr, p.sides[1].expr), var, relational=True), 3.0, None)
                if r is not None:
                    return {"available": True, "latex": tex(r)}
        s = solution_set(item, var, 3.0)
        if s is None:
            return {"available": False, "message": "Couldn't solve this one exactly."}
        if s.is_FiniteSet:
            if not s.args:
                return {"available": True, "latex": r"\text{no real solution}"}
            return {"available": True,
                    "latex": r" \text{ or } ".join(f"{tex(var)} = {tex(v)}" for v in s.args)}
        if s == S.Reals:
            return {"available": True, "latex": r"\text{every real number}"}
        return {"available": True, "latex": f"{tex(var)} \\in {latex(s)}"}
    except EngineTimeout:
        return {"available": False, "message": "Couldn't compute this one in time."}
