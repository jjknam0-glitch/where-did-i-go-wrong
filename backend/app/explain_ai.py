"""AI-phrased hints, with every equation verified by the engine.

The engine decides what went wrong; a language model only rewords hints 2
and 3 in friendlier language using the student's own numbers. Every equation
in the model's text is checked with SymPy; after two failed attempts the
template hints are kept.
"""

from __future__ import annotations

import json

from .engine.explain import verify_explanation
from .transcribe.providers import resolve_models

SYSTEM = """You are a patient math tutor. You rewrite two hints about ONE mistake in a student's work.

Rules:
- Use only the facts given. Do not add new math, and never solve the whole problem.
- Hint 2 says what KIND of mistake it is, without giving the fix.
- Hint 3 shows the corrected step, using exactly the corrected line given.
- Use the student's own numbers. Keep each hint to one or two short sentences, friendly and encouraging.
- Write every piece of math inside $...$ using LaTeX.
Return JSON: {"hint2": "...", "hint3": "..."}"""

SCHEMA = {
    "type": "object",
    "properties": {"hint2": {"type": "string"}, "hint3": {"type": "string"}},
    "required": ["hint2", "hint3"],
    "additionalProperties": False,
}


def ai_hints_available() -> bool:
    reads, _ = resolve_models()
    return bool(reads)


async def phrase_hints(payload: dict, run_sync) -> dict:
    """payload: previous, student, corrected, error_type, hints (template), variable."""
    template = payload.get("hints") or []
    reads, _ = resolve_models()
    if not reads or len(template) < 3:
        return {"hints": template, "source": "template"}
    provider, model = reads[0]
    facts = {
        "error_type": payload.get("error_type"),
        "line_before": payload.get("previous"),
        "student_line": payload.get("student"),
        "corrected_line": payload.get("corrected"),
        "template_hint2": template[1],
        "template_hint3": template[2],
    }
    user = "Facts about the mistake:\n" + json.dumps(facts, ensure_ascii=False)
    for _attempt in range(2):
        data = await provider.complete_json(SYSTEM, user, model, SCHEMA)
        if not data or not isinstance(data.get("hint2"), str) or not isinstance(data.get("hint3"), str):
            continue
        h2, h3 = data["hint2"].strip()[:400], data["hint3"].strip()[:400]
        ok = await run_sync(_verify_both, h2, h3, payload.get("previous") or "",
                            payload.get("student") or "", payload.get("corrected"),
                            payload.get("variable") or "x")
        if ok:
            return {"hints": [template[0], h2, h3], "source": "ai"}
    return {"hints": template, "source": "template"}


def _verify_both(h2, h3, previous, student, corrected, var):
    return (verify_explanation(h2, previous, student, corrected, var)
            and verify_explanation(h3, previous, student, corrected, var))
