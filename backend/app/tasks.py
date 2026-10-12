"""Plain functions run inside the engine worker processes."""

from __future__ import annotations

import base64

from .engine.parsing import looks_like_calculus
from .engine.render import line_to_latex
from .vision.pipeline import process_image


def vision_to_dict(data: bytes, mode: str) -> dict:
    """The CV pipeline, returning plain picklable data."""
    res = process_image(data, mode)
    return {
        "width": res.width, "height": res.height, "paper_found": res.paper_found,
        "warnings": res.warnings,
        "lines": [{"index": l.index, "box": l.box, "quad": l.quad, "crop": l.thumb,
                   "problem": l.problem, "png": base64.b64encode(l.crop_png).decode("ascii")}
                  for l in res.lines],
    }


def parse_many(lines: list[str]) -> list[dict]:
    natural = looks_like_calculus(lines)
    out = []
    for text in lines:
        if not (text or "").strip():
            out.append({"latex": "", "error": None})
            continue
        ltx, err = line_to_latex(text, natural)
        out.append({"latex": ltx, "error": err})
    return out
