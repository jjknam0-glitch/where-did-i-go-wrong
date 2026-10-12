"""Turn a line of math, as people actually write it, into SymPy objects.

The input is the ``math`` field from transcription or what a student typed:
``2x + 3 = 7``, ``f'(x) = 3x^2 sin x``, ``∫ 2x dx = x^2 + C``, ``x = 2 or x = -3``,
``x + y = 5; x - y = 1``. Parsing uses ``parse_expr`` with implicit
multiplication and ``^`` as power, which is far more forgiving than
``parse_latex``.

Security: ``parse_expr`` evaluates Python code, so the text is first reduced
to a strict whitelist of characters and names, and evaluation runs with no
builtins. Inputs that would build astronomically large numbers are rejected
before evaluation.
"""

from __future__ import annotations

import math
import re
import string
from dataclasses import dataclass, field

from sympy import (
    Abs, Add, Mul, Derivative, E, Float, Function, Integer, Integral, Limit, Pow, Rational, Symbol,
    acos, acot, acsc, asec, asin, atan, cbrt, cos, cosh, cot, csc, exp, factorial, factorial2,
    log, oo, pi, sec, sin, sinh, sqrt, tan, tanh,
)
from sympy.core.expr import Expr
from sympy.parsing.sympy_parser import (
    _token_splittable, convert_xor, function_exponentiation, implicit_application,
    implicit_multiplication, parse_expr, rationalize, split_symbols_custom,
    standard_transformations,
)

MAX_LINE_LENGTH = 300

GREEK = [
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa",
    "lamda", "mu", "nu", "xi", "omicron", "rho", "sigma", "tau", "upsilon", "phi", "chi",
    "psi", "omega",
]
GREEK_UNICODE = {
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon", "ζ": "zeta",
    "η": "eta", "θ": "theta", "ι": "iota", "κ": "kappa", "λ": "lamda", "μ": "mu", "ν": "nu",
    "ξ": "xi", "ρ": "rho", "σ": "sigma", "τ": "tau", "υ": "upsilon", "φ": "phi", "ϕ": "phi",
    "χ": "chi", "ψ": "psi", "ω": "omega",
}
FUNCTION_NAMES = [
    "arcsin", "arccos", "arctan", "arcsec", "arccsc", "arccot", "asin", "acos", "atan",
    "sinh", "cosh", "tanh", "sin", "cos", "tan", "sec", "csc", "cot", "exp", "ln", "log",
    "sqrt", "cbrt", "abs", "Abs",
]
CALCULUS_NAMES = ["diff", "Derivative", "integrate", "Integral", "limit", "Limit"]
# Symbols treated as arbitrary constants of integration.
CONSTANT_NAMES = {"C", "K", "C1", "C2", "C_1", "C_2"}

SUPERSCRIPTS = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5", "⁶": "6",
                "⁷": "7", "⁸": "8", "⁹": "9", "⁻": "-", "⁺": "+", "ⁿ": "n"}

SUPERSCRIPT_RUN_RE = re.compile("[" + "".join(SUPERSCRIPTS) + "]+")


class ParseError(ValueError):
    """The line could not be understood as math."""


# --------------------------------------------------------------------------
# SymPy namespace
# --------------------------------------------------------------------------

def _log_natural(*args, **kwargs):
    # log(x) -> natural log; log(x, b) -> base b.
    evaluate = kwargs.get("evaluate", True)
    if len(args) == 1:
        return log(args[0], evaluate=evaluate)
    if len(args) == 2:
        return log(args[0], args[1], evaluate=evaluate)
    raise ParseError("log takes one or two arguments")


def _log_ten(*args, **kwargs):
    # In algebra, a bare "log" means base 10.
    evaluate = kwargs.get("evaluate", True)
    if len(args) == 1:
        return log(args[0], 10, evaluate=evaluate)
    if len(args) == 2:
        return log(args[0], args[1], evaluate=evaluate)
    raise ParseError("log takes one or two arguments")


def _log10(arg, **kwargs):
    return log(arg, 10, evaluate=kwargs.get("evaluate", True))


def _diff(f, *args, **kwargs):
    if not args:
        args = (Symbol("x"),)
    return Derivative(f, *args)


def _integrate(f, *args, **kwargs):
    if not args:
        args = (Symbol("x"),)
    return Integral(f, *args)


def _limit(f, var=None, point=None, direction=None, **kwargs):
    if var is None or point is None:
        raise ParseError("limit needs a variable and a point")
    if direction is None:
        return Limit(f, var, point, dir="+-") if point not in (oo, -oo) else Limit(f, var, point)
    return Limit(f, var, point, dir=str(direction))


def _build_local_dict() -> dict:
    d: dict = {}
    for ch in string.ascii_letters:
        d[ch] = Symbol(ch)
    for g in GREEK:
        d[g] = Symbol(g)
    for name in ("C1", "C2", "C_1", "C_2"):
        d[name] = Symbol(name)
    d.update({
        "e": E, "E": E, "pi": pi, "oo": oo, "infinity": oo,
        "sin": sin, "cos": cos, "tan": tan, "sec": sec, "csc": csc, "cot": cot,
        "asin": asin, "acos": acos, "atan": atan, "asec": asec, "acsc": acsc, "acot": acot,
        "arcsin": asin, "arccos": acos, "arctan": atan, "arcsec": asec, "arccsc": acsc,
        "arccot": acot, "sinh": sinh, "cosh": cosh, "tanh": tanh,
        "exp": exp, "ln": log, "log": _log_ten, "logten": _log10,
        "sqrt": sqrt, "cbrt": cbrt, "abs": Abs, "Abs": Abs,
        "diff": _diff, "Derivative": _diff, "integrate": _integrate, "Integral": _integrate,
        "limit": _limit, "Limit": _limit,
    })
    return d


LOCAL_DICT = _build_local_dict()
GLOBAL_DICT = {
    "__builtins__": {},
    "Integer": Integer, "Rational": Rational, "Float": Float, "Symbol": Symbol,
    "Function": Function, "factorial": factorial, "factorial2": factorial2,
    "Add": Add, "Mul": Mul, "Pow": Pow,
}
KNOWN_NAMES = set(LOCAL_DICT) | {"Integer", "Rational", "Float", "Symbol", "Function"}


def _can_split(name: str) -> bool:
    if name in KNOWN_NAMES or name in CONSTANT_NAMES:
        return False
    return _token_splittable(name)


TRANSFORMATIONS = standard_transformations + (
    convert_xor,
    rationalize,
    split_symbols_custom(_can_split),
    implicit_multiplication,
    implicit_application,
    function_exponentiation,
)

# --------------------------------------------------------------------------
# Text normalization
# --------------------------------------------------------------------------

_LATEX_SIMPLE = [
    (r"\\left|\\right|\\displaystyle|\\,|\\;|\\!|\\quad|\\qquad", " "),
    (r"\\cdot|\\times|\\ast", "*"),
    (r"\\div", "/"),
    (r"\\pm", "±"),
    (r"\\mp", "∓"),
    (r"\\leq|\\le(?![a-z])", "<="),
    (r"\\geq|\\ge(?![a-z])", ">="),
    (r"\\neq|\\ne(?![a-z])", "!="),
    (r"\\to|\\rightarrow", "→"),
    (r"\\infty", "oo"),
    (r"\\pi", "pi"),
    (r"\\int", "∫"),
    (r"\\lim", "lim"),
    (r"\\ln", "ln"),
    (r"\\log", "log"),
    (r"\\exp", "exp"),
    (r"\\(arcsin|arccos|arctan|sinh|cosh|tanh|sin|cos|tan|sec|csc|cot)", r"\1"),
    (r"\\prime", "'"),
    (r"\\(alpha|beta|gamma|delta|epsilon|zeta|eta|theta|iota|kappa|mu|nu|xi|rho|sigma|tau|upsilon|phi|chi|psi|omega)", r"\1"),
    (r"\\lambda", "lamda"),
    (r"\\therefore", ""),
]


def _replace_frac(s: str) -> str:
    """\\frac{a}{b} -> ((a)/(b)), handling nested braces."""
    out = s
    for _ in range(20):
        i = out.find("\\frac")
        if i < 0:
            i = out.find("\\dfrac")
            if i < 0:
                break
            j = i + len("\\dfrac")
        else:
            j = i + len("\\frac")
        groups = []
        k = j
        for _g in range(2):
            while k < len(out) and out[k] == " ":
                k += 1
            if k >= len(out) or out[k] != "{":
                return out.replace("\\frac", "").replace("\\dfrac", "")
            depth = 0
            start = k
            while k < len(out):
                if out[k] == "{":
                    depth += 1
                elif out[k] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            groups.append(out[start + 1:k])
            k += 1
        out = out[:i] + f"(({groups[0]})/({groups[1]}))" + out[k:]
    return out


def _replace_sqrt_latex(s: str) -> str:
    s = re.sub(r"\\sqrt\s*\[([^\]]+)\]\s*\{([^{}]*)\}", r"((\2)^(1/(\1)))", s)
    return re.sub(r"\\sqrt", "sqrt", s)


def _replace_abs_bars(s: str) -> str:
    for _ in range(10):
        new = re.sub(r"\|([^|]+)\|", r"Abs(\1)", s)
        if new == s:
            break
        s = new
    if "|" in s:
        raise ParseError("Unmatched absolute-value bar |")
    return s


def _replace_superscripts(s: str) -> str:
    def rep(m):
        return "^(" + "".join(SUPERSCRIPTS[c] for c in m.group(0)) + ")"
    return SUPERSCRIPT_RUN_RE.sub(rep, s)


def _replace_radicals(s: str) -> str:
    # √(x+1) -> sqrt(x+1); √x -> sqrt(x); √2x -> sqrt(2)x (the radical covers the next token)
    s = re.sub(r"√\s*\(", "sqrt(", s)
    s = re.sub(r"√\s*([0-9]+(?:\.[0-9]+)?|[A-Za-z])", r"sqrt(\1)", s)
    s = re.sub(r"∛\s*\(", "cbrt(", s)
    s = re.sub(r"∛\s*([0-9]+(?:\.[0-9]+)?|[A-Za-z])", r"cbrt(\1)", s)
    if "√" in s or "∛" in s:
        raise ParseError("Couldn't tell what the square root covers")
    return s


_FUNC_ALT = "|".join(sorted([f for f in FUNCTION_NAMES if f not in ("abs", "Abs", "sqrt", "cbrt")],
                            key=len, reverse=True))
# sin x, sin 2x, sin x^2, sinx, cos^2 x  ->  explicit parentheses
_FUNC_ARG_RE = re.compile(
    r"\b(" + _FUNC_ALT + r")\s*(\^\s*\(?-?\d+\)?)?\s*"
    r"((?:\d+(?:\.\d+)?)?(?:[A-Za-z]|theta|alpha|beta|phi)(?:\^\(?\d+\)?)?)(?![A-Za-z0-9(])"
)


def _explicit_function_args(s: str) -> str:
    for _ in range(4):
        new = _FUNC_ARG_RE.sub(lambda m: f"{m.group(1)}{m.group(2) or ''}({m.group(3)})", s)
        if new == s:
            break
        s = new
    return s


def _unglue_functions(s: str) -> str:
    """'sinx' -> 'sin x', '2cosx' -> '2cos x' (only when the rest is not another name)."""
    def rep(m):
        return m.group(1) + " " + m.group(2)
    names = sorted([f for f in FUNCTION_NAMES if f not in ("abs", "Abs")], key=len, reverse=True)
    pat = re.compile(r"(?<![A-Za-z])(" + "|".join(names) + r")([A-Za-z0-9])")
    out = []
    i = 0
    while i < len(s):
        m = pat.match(s, i)
        if m and (i == 0 or not s[i - 1].isalpha()):
            rest = s[m.end(1):]
            # don't split "sinh" into "sin h", "sqrt" etc.: longest-name-first handles that.
            word_end = re.match(r"[A-Za-z]*", rest).end()
            word = m.group(1) + rest[:word_end]
            if word in KNOWN_NAMES and word != m.group(1):
                out.append(s[i:i + len(word)])
                i += len(word)
                continue
            out.append(m.group(1) + " ")
            i = m.end(1)
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def normalize_text(text: str) -> str:
    """Normalize unicode, light LaTeX and common handwriting conventions to plain ASCII math."""
    if text is None:
        raise ParseError("Empty line")
    s = str(text).strip()
    if not s:
        raise ParseError("Empty line")
    if len(s) > MAX_LINE_LENGTH:
        raise ParseError("Line is too long")

    s = s.replace("$", "")
    # LaTeX bits a model or student might use.
    s = _replace_frac(s)
    s = _replace_sqrt_latex(s)
    for pat, rep in _LATEX_SIMPLE:
        s = re.sub(pat, rep, s)
    s = s.replace("\\{", "(").replace("\\}", ")")
    s = s.replace("{", "(").replace("}", ")")
    s = s.replace("\\", " ")

    replacements = {
        "−": "-", "–": "-", "—": "-", "‐": "-", "‑": "-", "﹣": "-", "－": "-",
        "×": "*", "·": "*", "⋅": "*", "•": "*", "∙": "*", "✕": "*",
        "÷": "/", "∕": "/", "⁄": "/",
        "≤": "<=", "⩽": "<=", "≥": ">=", "⩾": ">=", "≠": "!=",
        "→": "→", "⟶": "→", "->": "→", "=>": "⇒",
        "∞": "oo", "π": "pi", "∴": "", "⇒": "", "⟹": "",
        "′": "'", "’": "'", "‘": "'", "″": "''", "`": "'",
        "[": "(", "]": ")", "（": "(", "）": ")",
        "∓": "∓", "+/-": "±", "+-": "±",
        "\u00a0": " ", "\u2009": " ", "\u200b": "",
        "½": "(1/2)", "⅓": "(1/3)", "¼": "(1/4)", "¾": "(3/4)", "⅔": "(2/3)",
    }
    for a, b in replacements.items():
        s = s.replace(a, b)
    for ch, name in GREEK_UNICODE.items():
        s = s.replace(ch, f" {name} ")
    s = _replace_superscripts(s)
    s = _replace_radicals(s)
    s = s.replace("**", "^")

    # Words and decorations that carry no math.
    s = re.sub(r"(?i)^\s*(therefore|so|thus|hence|answer\s*:|ans\s*:)\s*", "", s)
    s = re.sub(r"(?i)\bln\b", "ln", s)
    s = re.sub(r"\blog_?\(?10\)?\s*\(", "logten(", s)
    s = re.sub(r"\blog_\(?([0-9A-Za-z]+)\)?\s*\(([^()]*)\)", r"log(\2, \1)", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.rstrip(".")
    s = _replace_abs_bars(s)
    return s


_ALLOWED_RE = re.compile(r"^[A-Za-z0-9\s+\-*/^().,=<>!'_;±∓∫→]*$")


def _check_safe(s: str) -> None:
    if not _ALLOWED_RE.match(s):
        bad = sorted({c for c in s if not _ALLOWED_RE.match(c)})
        raise ParseError(f"Unexpected character(s): {' '.join(bad)}")
    if "__" in s:
        raise ParseError("Unexpected '__'")
    # A dot is only allowed inside a decimal number.
    for m in re.finditer(r"\.", s):
        i = m.start()
        before = s[i - 1] if i > 0 else ""
        after = s[i + 1] if i + 1 < len(s) else ""
        if not (before.isdigit() or after.isdigit()):
            raise ParseError("Unexpected '.'")
    for word in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", s):
        if word in {"lambda", "import", "exec", "eval", "class", "def", "global", "nonlocal",
                    "yield", "await", "async", "with", "while", "for", "del", "return", "raise",
                    "try", "except", "finally", "assert", "pass", "break", "continue", "from",
                    "as", "is", "not", "in", "if", "else", "elif", "None", "True", "False"}:
            raise ParseError(f"Unexpected word '{word}'")


# --------------------------------------------------------------------------
# Calculus notation
# --------------------------------------------------------------------------

def _matching_paren(s: str, i: int) -> int:
    depth = 0
    for k in range(i, len(s)):
        if s[k] == "(":
            depth += 1
        elif s[k] == ")":
            depth -= 1
            if depth == 0:
                return k
    raise ParseError("Unbalanced parentheses")


def _transform_integrals(s: str) -> str:
    for _ in range(10):
        i = s.find("∫")
        if i < 0:
            return s
        j = i + 1
        lower = upper = None
        m = re.match(r"\s*_\s*(\(([^()]*)\)|-?[0-9A-Za-z.]+)\s*\^\s*(\(([^()]*)\)|-?[0-9A-Za-z.]+)", s[j:])
        if m:
            lower = m.group(2) if m.group(2) is not None else m.group(1)
            upper = m.group(4) if m.group(4) is not None else m.group(3)
            j += m.end()
        # Integrand runs until the first differential "dx" at depth 0.
        depth = 0
        k = j
        found = None
        while k < len(s):
            c = s[k]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth < 0:
                    break
            elif depth == 0 and c == "d" and k + 1 < len(s) and s[k + 1] in string.ascii_letters:
                prev = s[k - 1] if k > j else " "
                nxt = s[k + 2] if k + 2 < len(s) else " "
                if not prev.isalpha() or prev in "0123456789)":
                    if not nxt.isalpha():
                        found = k
                        break
                elif prev.isalpha() and not nxt.isalpha() and s[k + 1] in "xytuvzsrθ":
                    # glued like "2xdx"
                    found = k
                    break
            k += 1
        if found is None:
            raise ParseError("Couldn't find the dx at the end of the integral")
        integrand = s[j:found].strip()
        var = s[found + 1]
        if not integrand:
            integrand = "1"
        if lower is not None:
            rep = f"integrate(({integrand}), ({var}, {lower}, {upper}))"
        else:
            rep = f"integrate(({integrand}), {var})"
        s = s[:i] + rep + s[found + 2:]
    return s


def _transform_derivatives(s: str) -> str:
    # d/dx(...), d/dx [ ... ], d²/dx² ..., (d/dx) f
    pat = re.compile(r"\(?\s*d\s*(\^\s*\(?2\)?)?\s*/\s*d\s*([a-z])\s*(\^\s*\(?2\)?)?\s*\)?")
    for _ in range(10):
        m = pat.search(s)
        if not m:
            return s
        order = 2 if (m.group(1) or m.group(3)) else 1
        var = m.group(2)
        rest_start = m.end()
        while rest_start < len(s) and s[rest_start] == " ":
            rest_start += 1
        if rest_start < len(s) and s[rest_start] == "(":
            end = _matching_paren(s, rest_start)
            inner = s[rest_start + 1:end]
            tail = s[end + 1:]
        else:
            inner = s[rest_start:]
            tail = ""
        if not inner.strip():
            raise ParseError("d/dx needs something to differentiate")
        order_arg = f", {order}" if order > 1 else ""
        s = s[:m.start()] + f"diff(({inner}), {var}{order_arg})" + tail
    return s


def _transform_limits(s: str) -> str:
    pat = re.compile(r"\blim\s*_?\s*\(?\s*([a-z])\s*→\s*(-?\s*(?:oo|[0-9A-Za-z./]+))\s*(\^?\s*[+-])?\s*\)?")
    for _ in range(5):
        m = pat.search(s)
        if not m:
            return s
        var, point = m.group(1), m.group(2).replace(" ", "")
        direction = (m.group(3) or "").replace("^", "").strip()
        rest = s[m.end():].strip()
        if rest.startswith("(") and _matching_paren(rest, 0) == len(rest) - 1:
            rest = rest[1:-1]
        if not rest:
            raise ParseError("lim needs an expression")
        dir_arg = f", '{direction}'" if direction else ""
        if dir_arg:
            # Directions are passed as plain symbols to keep the whitelist strict.
            dir_arg = ", plus" if direction == "+" else ", minus"
        s = s[:m.start()] + f"limit(({rest}), {var}, {point}{dir_arg})"
    return s


# --------------------------------------------------------------------------
# Expressions
# --------------------------------------------------------------------------

def _magnitude_ok(expr) -> bool:
    """Reject numbers too large to compute (e.g. 9^9^9) before evaluating.

    Works on the unevaluated tree with log10 estimates, never computing the
    big number itself.
    """
    def est(e) -> float:
        # Upper bound on log10(|value|) of the numeric part of e (0 for symbols).
        if e.is_Rational:
            p, q = abs(int(e.p)), abs(int(e.q))
            return math.log10(max(p, q, 1))
        if e.is_Float:
            v = abs(float(e))
            return math.log10(v) if v > 1 else 0.0
        if isinstance(e, Pow):
            base, ex = e.args
            lb = est(base)
            if ex.free_symbols:
                est(ex)
                return lb
            lx = est(ex)
            if lx > 4.5:
                raise ParseError("Exponent too large")
            if ex.is_Rational:
                xval = abs(float(ex))
            else:
                xval = 10 ** lx
            return lb * xval
        if e.func == factorial:
            arg = e.args[0]
            if not arg.is_Integer or abs(arg) > 500:
                if arg.is_number:
                    raise ParseError("Factorial too large")
            return 1200.0 if arg.is_number else est(arg)
        if e.is_Mul:
            return sum(est(a) for a in e.args)
        if e.is_Add:
            return max((est(a) for a in e.args), default=0.0) + 1
        return max((est(a) for a in e.args), default=0.0)

    try:
        return est(expr) < 3000
    except (TypeError, ValueError, OverflowError):
        return False


def clean_raw(e):
    """Tidy an unevaluated tree without evaluating it: Mul(-1, 3) -> -3."""
    if not e.args:
        return e
    if e.is_Mul and len(e.args) == 2 and e.args[0] == -1 and e.args[1].is_Number:
        return -e.args[1]
    args = [clean_raw(a) for a in e.args]
    if e.is_Add or e.is_Mul or e.is_Pow:
        return e.func(*args, evaluate=False)
    try:
        return e.func(*args)
    except Exception:
        return e


def _parse_expr_text(s: str, evaluate: bool, natural_log: bool = False):
    local = dict(LOCAL_DICT)
    if natural_log:
        local["log"] = _log_natural
    local["plus"] = "+"
    local["minus"] = "-"
    try:
        return parse_expr(s, local_dict=local, global_dict=dict(GLOBAL_DICT),
                          transformations=TRANSFORMATIONS, evaluate=evaluate)
    except ParseError:
        raise
    except Exception as exc:  # SyntaxError, TokenError, TypeError, ...
        raise ParseError("Couldn't read this as math") from exc


def parse_side(text: str, natural_log: bool = False):
    """Parse one side of a relation. Returns (evaluated, unevaluated)."""
    s = text.strip()
    if not s:
        raise ParseError("Something is missing on one side of the equals sign")
    s = _transform_limits(s)
    s = _transform_integrals(s)
    s = _transform_derivatives(s)
    s = _unglue_functions(s)
    s = _explicit_function_args(s)
    if "±" in s or "∓" in s:
        raise ParseError("Unexpected ±")
    _check_safe(s)
    raw = _parse_expr_text(s, evaluate=False, natural_log=natural_log)
    if not isinstance(raw, Expr):
        raise ParseError("Couldn't read this as math")
    if not _magnitude_ok(raw):
        raise ParseError("A number here is too large to work with")
    raw = clean_raw(raw)
    ev = _parse_expr_text(s, evaluate=True, natural_log=natural_log)
    if not isinstance(ev, Expr):
        raise ParseError("Couldn't read this as math")
    return ev, raw


# --------------------------------------------------------------------------
# Lines
# --------------------------------------------------------------------------

@dataclass
class Label:
    name: str
    order: int
    var: str | None = None


@dataclass
class Side:
    text: str
    expr: Expr
    raw: Expr


@dataclass
class Part:
    sides: list
    ops: list
    label: Label | None = None

    @property
    def is_expression(self) -> bool:
        return not self.ops

    @property
    def is_equation(self) -> bool:
        return bool(self.ops) and all(op == "=" for op in self.ops)

    @property
    def is_inequality(self) -> bool:
        return any(op in ("<", ">", "<=", ">=") for op in self.ops)


@dataclass
class ParsedLine:
    text: str
    parts: list
    connective: str | None = None  # "and" (system) | "or" (alternatives) | None
    continuation: bool = False
    decimals: int = 0
    symbols: set = field(default_factory=set)

    @property
    def single(self) -> Part | None:
        return self.parts[0] if len(self.parts) == 1 else None


_LABEL_FUNC_RE = re.compile(r"^\s*([A-Za-z])\s*('*)\s*\(\s*([a-z])\s*\)\s*$")
_LABEL_PRIME_RE = re.compile(r"^\s*([A-Za-z])\s*('+)\s*$")
_LABEL_LEIBNIZ_RE = re.compile(r"^\s*d\s*(\^\s*\(?2\)?)?\s*([a-zA-Z])\s*/\s*d\s*([a-z])\s*(\^\s*\(?2\)?)?\s*$")
_LABEL_LETTER_RE = re.compile(r"^\s*([A-Za-z])\s*$")


def detect_label(lhs_text: str) -> Label | None:
    m = _LABEL_FUNC_RE.match(lhs_text)
    if m and m.group(1) not in ("d",):
        return Label(m.group(1), len(m.group(2)), m.group(3))
    m = _LABEL_PRIME_RE.match(lhs_text)
    if m:
        return Label(m.group(1), len(m.group(2)))
    m = _LABEL_LEIBNIZ_RE.match(lhs_text)
    if m:
        order = 2 if (m.group(1) or m.group(4)) else 1
        return Label(m.group(2), order, m.group(3))
    return None


def plain_letter(lhs_text: str) -> str | None:
    m = _LABEL_LETTER_RE.match(lhs_text)
    return m.group(1) if m else None


def _split_top_level(s: str, seps: list[str]) -> list[str]:
    parts, depth, i, start = [], 0, 0, 0
    while i < len(s):
        c = s[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0:
            for sep in seps:
                if s.startswith(sep, i):
                    parts.append(s[start:i])
                    i += len(sep)
                    start = i
                    break
            else:
                i += 1
                continue
            continue
        i += 1
    parts.append(s[start:])
    return parts


_REL_OPS = ["<=", ">=", "!=", "==", "=", "<", ">"]


def _split_relations(s: str):
    sides, ops, depth, i, start = [], [], 0, 0, 0
    while i < len(s):
        c = s[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0:
            for op in _REL_OPS:
                if s.startswith(op, i):
                    sides.append(s[start:i])
                    ops.append("=" if op == "==" else op)
                    i += len(op)
                    start = i
                    break
            else:
                i += 1
                continue
            continue
        i += 1
    sides.append(s[start:])
    if "!=" in ops:
        raise ParseError("'≠' can't be checked yet")
    return sides, ops


def _expand_pm(text: str) -> list[str]:
    n = text.count("±") + text.count("∓")
    if n == 0:
        return [text]
    if n > 1:
        raise ParseError("Only one ± per line is supported")
    plus = text.replace("±", "+").replace("∓", "-")
    minus = text.replace("±", "-").replace("∓", "+")
    return [plus, minus]


def _parse_part(text: str, allow_label: bool = True, natural_log: bool = False) -> Part:
    side_texts, ops = _split_relations(text)
    if any(not t.strip() for t in side_texts):
        raise ParseError("Something is missing on one side of a relation")
    label = None
    if ops and ops[0] == "=" and allow_label:
        label = detect_label(side_texts[0])
        if label is not None:
            side_texts = side_texts[1:]
            ops = ops[1:]
    sides = []
    for t in side_texts:
        ev, raw = parse_side(t, natural_log=natural_log)
        sides.append(Side(t.strip(), ev, raw))
    return Part(sides, ops, label)


def parse_line(text: str, natural_log: bool = False) -> ParsedLine:
    s = normalize_text(text)
    continuation = False
    if s.startswith("=") and not s.startswith("=="):
        continuation = True
        s = s[1:].strip()
        if not s:
            raise ParseError("Nothing after the equals sign")
    decimals = max((len(m.group(1)) for m in re.finditer(r"\d\.(\d+)", s)), default=0)

    connective = None
    chunks = _split_top_level(s, [";", " and "])
    if len(chunks) > 1:
        connective = "and"
    else:
        chunks = _split_top_level(s, [" or ", " OR "])
        if len(chunks) > 1:
            connective = "or"
        else:
            comma_chunks = _split_top_level(s, [","])
            if len(comma_chunks) > 1 and any(op in s for op in "=<>"):
                chunks = comma_chunks
                connective = "list"
    chunks = [c.strip() for c in chunks if c.strip()]
    if not chunks:
        raise ParseError("Empty line")

    # "x = 2, -3" / "x = 2 or -3": a bare value reuses the previous left-hand side.
    expanded = []
    prev_lhs = None
    for c in chunks:
        sides, ops = _split_relations(c)
        if not ops and prev_lhs is not None and connective in ("or", "list"):
            c = f"{prev_lhs} = {c}"
        elif ops:
            prev_lhs = sides[0].strip()
        expanded.extend(_expand_pm(c))
    if len(expanded) > len(chunks):
        connective = connective if connective in ("and",) else "or"
        if connective == "and":
            raise ParseError("± inside a system isn't supported")

    parts = [_parse_part(c, allow_label=(len(expanded) == 1), natural_log=natural_log) for c in expanded]

    if connective == "list":
        # Same single variable on every left side -> alternatives, else a system.
        lhs_syms = []
        for p in parts:
            if not p.is_equation or len(p.sides) != 2:
                lhs_syms = None
                break
            lhs = p.sides[0].expr
            lhs_syms.append(lhs if isinstance(lhs, Symbol) else None)
        if lhs_syms and all(v is not None for v in lhs_syms) and len(set(lhs_syms)) == 1:
            connective = "or"
        else:
            connective = "and"
    if connective is None and len(parts) > 1:
        connective = "or"

    if connective == "and" and any(not p.ops for p in parts):
        raise ParseError("Each part of a system needs an equals sign")
    if connective == "or" and any(not p.ops for p in parts):
        raise ParseError("Each alternative needs a relation")

    syms = set()
    for p in parts:
        for sd in p.sides:
            syms |= sd.expr.free_symbols
    return ParsedLine(text=str(text), parts=parts, connective=connective,
                      continuation=continuation, decimals=decimals, symbols=syms)


def try_parse_line(text: str, natural_log: bool = False):
    try:
        return parse_line(text, natural_log=natural_log), None
    except ParseError as exc:
        return None, str(exc)
    except RecursionError:
        return None, "Expression is too deeply nested"


def is_constant_symbol(sym) -> bool:
    return getattr(sym, "name", None) in CONSTANT_NAMES


_CALCULUS_HINT_RE = re.compile(r"(∫|\\int|\bd\s*/\s*d[a-z]|\bdiff\b|\bintegrate\b|\blim\b|\blimit\b|'|′|\bd[a-z]\s*/\s*d[a-z])")


def looks_like_calculus(texts) -> bool:
    """Calculus problems read a bare 'log' as the natural log."""
    return any(_CALCULUS_HINT_RE.search(t or "") for t in texts)
