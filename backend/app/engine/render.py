"""LaTeX for a typed or transcribed line, for live previews."""

from __future__ import annotations

from .items import REL_TEX, tex
from .parsing import looks_like_calculus, try_parse_line


def _label_tex(label) -> str:
    primes = "'" * label.order
    if label.var:
        return f"{label.name}{primes}({label.var})"
    return f"{label.name}{primes}"


def line_to_latex(text: str, natural_log: bool | None = None) -> tuple[str | None, str | None]:
    """(latex, error) for one line of math."""
    if natural_log is None:
        natural_log = looks_like_calculus([text])
    pl, err = try_parse_line(text, natural_log=natural_log)
    if pl is None:
        return None, err
    pieces = []
    for p in pl.parts:
        out = ""
        if p.label is not None:
            out = _label_tex(p.label) + " = "
        out += tex(p.sides[0].raw)
        for op, s in zip(p.ops, p.sides[1:]):
            out += f" {REL_TEX[op]} {tex(s.raw)}"
        pieces.append(out)
    joiner = r" \;\text{ or }\; " if pl.connective == "or" else r",\quad "
    result = joiner.join(pieces)
    if pl.continuation:
        result = "= " + result
    return result, None
