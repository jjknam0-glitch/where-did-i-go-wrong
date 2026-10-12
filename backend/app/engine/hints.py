"""The hint ladder: where, what kind, the fix.

Hints are generated from the classifier's facts using the student's own
numbers. Math is wrapped in $...$ so the frontend can render it with KaTeX.
"""

from __future__ import annotations

from .classify import Classification

# Which mini-lesson explains each mistake.
LESSON_FOR = {
    ("sign_error", "moved"): "moving-terms",
    ("sign_error", "distribution"): "distributing-negatives",
    ("sign_error", "term"): "moving-terms",
    ("one_side_only", None): "both-sides",
    ("distribution_error", None): "distributing-negatives",
    ("arithmetic_slip", None): "checking-arithmetic",
    ("exponent_rule", "power_of_sum"): "squaring-a-sum",
    ("exponent_rule", None): "exponent-rules",
    ("inequality_flip", None): "inequality-flip",
    ("derivative_rule", "chain_rule"): "chain-rule",
    ("derivative_rule", "product_rule"): "product-rule",
    ("derivative_rule", "quotient_rule"): "quotient-rule",
    ("derivative_rule", "power_rule"): "power-rule",
    ("derivative_rule", None): "power-rule",
    ("antiderivative_error", None): "checking-antiderivatives",
    ("lost_solution", "divide"): "dividing-by-variables",
    ("lost_solution", "square_root"): "square-roots",
    ("lost_solution", None): "dividing-by-variables",
    ("extra_solution", None): "extraneous-solutions",
    ("general", None): "checking-arithmetic",
}

ERROR_NAMES = {
    "sign_error": "Sign error",
    "one_side_only": "One side only",
    "distribution_error": "Distribution error",
    "arithmetic_slip": "Arithmetic slip",
    "exponent_rule": "Exponent rule",
    "inequality_flip": "Inequality flip",
    "derivative_rule": "Derivative rule",
    "antiderivative_error": "Antiderivative",
    "lost_solution": "Lost solution",
    "extra_solution": "Extra solution",
    "general": "Changed step",
}


def lesson_for(c: Classification) -> str:
    return LESSON_FOR.get((c.error_type, c.subtype)) or LESSON_FOR.get((c.error_type, None), "checking-arithmetic")


def _should_be(c: Classification, lead: str = "so the line should be") -> str:
    if c.corrected:
        return f"{lead} ${c.corrected}$."
    return ""


def build_hints(c: Classification, from_line: int, to_line: int) -> list[str]:
    """Three hints. Line numbers are 1-based as shown to the student."""
    f = c.facts
    if c.warning:
        where = (f"Careful with the step from line {from_line} to line {to_line}."
                 if from_line != to_line else f"Careful with line {to_line}.")
    elif from_line == to_line:
        where = f"Something's off inside line {to_line}."
    else:
        where = f"Something's off between lines {from_line} and {to_line}."
    t, s = c.error_type, c.subtype

    what, fix = None, None
    if t == "sign_error" and s == "moved":
        what = f"Look at what happened to the ${f['term']}$ when it moved sides."
        fix = (f"Moving ${f['term']}$ to the {f['to']} side makes it ${f['fixed_term']}$, "
               + _should_be(c))
    elif t == "sign_error" and s == "distribution":
        what = f"The ${f['multiplier']}$ multiplies every term in the parentheses — check the sign of each product."
        fix = (f"${f['multiplier']}\\left({f['group']}\\right) = {f['expanded']}$, " + _should_be(c))
    elif t == "sign_error":
        what = f"Check the sign of the ${f['term']}$ term."
        fix = f"That term should be ${f['fixed_term']}$, " + _should_be(c)
    elif t == "one_side_only":
        what = f"You {f['action']} but not the {f['other']} side."
        fix = "Whatever you do to one side, do to the other: " + _should_be(c, "the line should be")
    elif t == "distribution_error":
        what = f"The ${f['multiplier']}$ needs to multiply every term in the parentheses."
        fix = f"${f['multiplier']}\\left({f['group']}\\right) = {f['expanded']}$, " + _should_be(c)
    elif t == "arithmetic_slip":
        if f.get("origin"):
            what = f"Double-check ${f['origin']}$."
            fix = f"${f['origin']} = {f['right']}$, " + _should_be(c)
        else:
            what = f"Double-check the ${f['wrong']}$ in this line."
            fix = f"That ${f['wrong']}$ should be ${f['right']}$, " + _should_be(c)
    elif t == "exponent_rule":
        if s == "power_of_sum":
            what = "Squaring a sum gives a middle term." if f.get("n") == "2" else \
                "A power of a sum isn't the sum of the powers."
            fix = f"${f['power']} = {f['expanded']}$, " + _should_be(c)
        elif s == "power_of_product":
            what = f"The exponent applies to the ${f['coeff']}$ too."
            fix = f"${f['power']} = {f['expanded']}$, " + _should_be(c)
        elif s == "power_of_power":
            what = "A power of a power multiplies the exponents."
            fix = f"${f['power']} = {f['expanded']}$, " + _should_be(c)
        elif s == "product_of_powers":
            what = "Multiplying powers with the same base adds the exponents."
            fix = f"${f['power']} = {f['expanded']}$, " + _should_be(c)
        elif s == "root_of_sum":
            what = "The square root of a sum isn't the sum of the square roots."
            fix = _should_be(c, "Keep the root over the whole sum:")
        elif s == "negative_exponent":
            what = "A negative exponent means a reciprocal, not a negative number."
            fix = _should_be(c, "Keep it as a reciprocal:")
    elif t == "inequality_flip":
        what = "Dividing by a negative flips the inequality."
        if f.get("divisor"):
            fix = f"Dividing by ${f['divisor']}$ reverses the sign, " + _should_be(c)
        else:
            fix = "Multiplying or dividing by a negative reverses the sign, " + _should_be(c)
    elif t == "derivative_rule":
        what = {
            "chain_rule": "Did you multiply by the derivative of the inside?",
            "product_rule": "The product rule has two terms: $u'v + uv'$.",
            "quotient_rule": "Quotient rule: $\\frac{u'v - uv'}{v^2}$ — check the order, the minus sign and the square.",
            "power_rule": "Power rule: bring the exponent down, then subtract 1 from it.",
            "trig_derivative": "Check the sign: $\\frac{d}{dx}\\cos x = -\\sin x$ and $\\frac{d}{dx}\\sin x = \\cos x$.",
            "exponential": "$a^x$ is an exponential, not a power: $\\frac{d}{dx}a^x = a^x \\ln a$.",
            "constant_term": "The derivative of a constant is $0$.",
        }.get(s, "Differentiate one term at a time and compare with what you wrote.")
        fix = _should_be(c, "The derivative should be")
    elif t == "antiderivative_error":
        sd = f.get("student_derivative")
        if s == "sign" and sd:
            what = f"Differentiate your answer: you get ${sd}$, which has the opposite sign of ${f['integrand']}$."
        elif s == "coefficient" and sd:
            what = f"Differentiate your answer: you get ${sd}$ — off by a factor of ${f['factor']}$ from ${f['integrand']}$."
        elif sd:
            what = f"Differentiate your answer: you get ${sd}$, but the integrand is ${f['integrand']}$."
        else:
            what = "Differentiate your answer and compare it with the integrand."
        fix = _should_be(c, "A correct antiderivative is")
    elif t == "lost_solution":
        if s == "divide":
            vals = ", ".join(f"${f['var']} = {v}$" for v in f.get("values", []))
            what = f"Dividing by ${f['divisor']}$ can lose {vals}. Check it."
            fix = f"{vals} also works in the line before. Factor instead of dividing to keep it."
        elif s == "square_root":
            what = "Taking a square root gives two answers: $\\pm$."
            fix = _should_be(c, "The line should be")
        else:
            what = "This step lost a solution that the line before had."
            fix = _should_be(c)
    elif t == "extra_solution":
        vals = ", ".join(f"${f.get('var', 'x')} = {v}$" for v in f.get("values", []))
        if s == "square":
            what = "Squaring both sides can add solutions that don't work in the original."
            fix = f"Check {vals} in the line before — it doesn't satisfy it." if vals else \
                "Check each answer in the original equation."
        elif s == "multiply":
            what = f"Multiplying by ${f['factor']}$ can add a solution where it equals zero."
            fix = f"Check {vals} in the line before — it isn't allowed there." if vals else \
                "Check each answer in the original equation."
        else:
            what = "This step added a solution that the line before didn't have."
            fix = _should_be(c)
    if not what:
        what = "Something changed between these two lines. Check each term."
    if not fix:
        fix = _should_be(c, "A correct version of this step is") or \
            f"Redo the step from line {from_line} one operation at a time, and compare each term."
    return [where, what, fix.strip()]


def build_warning_hints(c: Classification, from_line: int, to_line: int) -> list[str]:
    return build_hints(c, from_line, to_line)
