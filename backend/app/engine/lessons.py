"""Concept mini-lessons ("Why does this rule work?").

Each lesson explains one idea and walks through one worked example. The
example's steps are run through the same checker as student work, so the
lesson can show that every step is verified by the engine.
"""

from __future__ import annotations

from functools import lru_cache

from .checker import check_lines
from .render import line_to_latex

LESSONS = {
    "moving-terms": {
        "title": "Moving a term across the equals sign",
        "topic": "Algebra",
        "summary": "When a term moves to the other side, its sign flips.",
        "body": [
            "An equation is a balance: both sides are equal. You can do anything you like to it, "
            "as long as you do the same thing to both sides.",
            "\"Moving $+3$ to the other side\" is really a shortcut for *subtracting 3 from both sides*. "
            "On the left, $+3 - 3$ cancels. On the right, the $-3$ is still there. That's why the term shows "
            "up on the other side with the opposite sign.",
            "Say the full operation to yourself — \"subtract 3 from both sides\" — and the sign takes care of itself.",
        ],
        "example": ["2x + 3 = 7", "2x + 3 - 3 = 7 - 3", "2x = 4", "x = 2"],
        "practice": "sign_error",
    },
    "both-sides": {
        "title": "Do the same thing to both sides",
        "topic": "Algebra",
        "summary": "Any operation has to happen to the whole of each side.",
        "body": [
            "If two quantities are equal and you divide just one of them by 3, they won't be equal anymore.",
            "So every operation — adding, subtracting, multiplying, dividing — must be applied to the *entire* left "
            "side and the *entire* right side. When dividing, divide every term on each side.",
        ],
        "example": ["3x + 6 = 21", "(3x + 6)/3 = 21/3", "x + 2 = 7", "x = 5"],
        "practice": "one_side_only",
    },
    "distributing-negatives": {
        "title": "Distributing a negative",
        "topic": "Algebra",
        "summary": "The number outside the parentheses multiplies every term inside — sign included.",
        "body": [
            "$a(b + c) = ab + ac$: the outside factor multiplies each term inside the parentheses.",
            "With a negative factor, every product picks up a sign change: $-2(x - 3)$ is $-2 \\cdot x$ plus "
            "$-2 \\cdot (-3)$, which is $-2x + 6$. A negative times a negative is positive.",
            "A common slip is to multiply only the first term, or to forget that the second sign changes.",
        ],
        "example": ["-2(x - 3) + 4 = 10", "-2x + 6 + 4 = 10", "-2x + 10 = 10", "-2x = 0", "x = 0"],
        "practice": "distribution_error",
    },
    "checking-arithmetic": {
        "title": "Catching arithmetic slips",
        "topic": "Algebra",
        "summary": "Small number mistakes are the most common error of all — check each one.",
        "body": [
            "Most wrong answers come from one small arithmetic slip, not from misunderstanding the method.",
            "After each step, check the numbers that changed. A quick way: substitute your final answer back into "
            "the original equation. If both sides match, the arithmetic is right.",
        ],
        "example": ["7x + 12 = 3x - 8", "4x + 12 = -8", "4x = -20", "x = -5"],
        "practice": "arithmetic_slip",
    },
    "squaring-a-sum": {
        "title": "Squaring a sum",
        "topic": "Algebra",
        "summary": "$(a + b)^2 = a^2 + 2ab + b^2$ — there's always a middle term.",
        "body": [
            "$(a + b)^2$ means $(a + b)(a + b)$. Multiplying it out gives four products: $a^2 + ab + ba + b^2$.",
            "The two middle products combine into $2ab$. Writing $a^2 + b^2$ forgets them.",
            "Check with numbers: $(1 + 2)^2 = 9$, but $1^2 + 2^2 = 5$.",
        ],
        "example": ["(x + 3)^2", "(x + 3)(x + 3)", "x^2 + 3x + 3x + 9", "x^2 + 6x + 9"],
        "practice": "exponent_rule",
    },
    "exponent-rules": {
        "title": "Exponent rules",
        "topic": "Algebra",
        "summary": "Multiply powers: add exponents. Power of a power: multiply them.",
        "body": [
            "$x^2 \\cdot x^3$ is $(x \\cdot x)(x \\cdot x \\cdot x) = x^5$: same base, so the exponents add.",
            "$(x^2)^3$ is $x^2 \\cdot x^2 \\cdot x^2 = x^6$: a power of a power multiplies the exponents.",
            "$(2x)^3 = 2^3 x^3 = 8x^3$: the exponent applies to every factor inside the parentheses.",
        ],
        "example": ["(2x^2)^3 * x", "8x^6 * x", "8x^7"],
        "practice": "exponent_rule",
    },
    "inequality-flip": {
        "title": "Why dividing by a negative flips an inequality",
        "topic": "Algebra",
        "summary": "Multiplying or dividing by a negative number reverses the order of numbers.",
        "body": [
            "$2 < 5$ is true. Multiply both sides by $-1$ and you get $-2$ and $-5$ — but now $-2$ is the larger one.",
            "Multiplying or dividing by a negative mirrors the number line, so the inequality has to flip "
            "to stay true.",
        ],
        "example": ["-2x + 1 > 7", "-2x > 6", "x < -3"],
        "practice": "inequality_flip",
    },
    "power-rule": {
        "title": "The power rule",
        "topic": "Calculus",
        "summary": "$\\frac{d}{dx}x^n = n x^{n-1}$: bring the exponent down, then subtract one.",
        "body": [
            "The exponent comes down in front as a coefficient, and the new exponent is one less.",
            "It works for any real $n$: $\\frac{d}{dx}\\sqrt{x} = \\frac{d}{dx}x^{1/2} = \\frac{1}{2}x^{-1/2}$.",
            "Constants disappear: the derivative of a constant is $0$.",
        ],
        "example": ["f(x) = 4x^3 - 5x + 2", "f'(x) = 12x^2 - 5"],
        "practice": "derivative_rule",
    },
    "chain-rule": {
        "title": "The chain rule",
        "topic": "Calculus",
        "summary": "Derivative of the outside, times the derivative of the inside.",
        "body": [
            "For a function inside another function, $f(g(x))$, the rate of change multiplies: "
            "$\\frac{d}{dx}f(g(x)) = f'(g(x)) \\cdot g'(x)$.",
            "Think of gears: if the inside turns 3 times as fast as $x$, everything built on it speeds up by 3 too. "
            "Forgetting the inner derivative is the most common calculus mistake.",
        ],
        "example": ["f(x) = sin(3x^2)", "f'(x) = cos(3x^2) * 6x"],
        "practice": "derivative_rule",
    },
    "product-rule": {
        "title": "The product rule",
        "topic": "Calculus",
        "summary": "$(uv)' = u'v + uv'$ — two terms, not one.",
        "body": [
            "When two changing quantities multiply, both changes contribute. Picture a rectangle with sides $u$ and $v$: "
            "growing $u$ adds a strip $u' v$, growing $v$ adds a strip $u v'$.",
            "So the derivative of a product is not the product of the derivatives.",
        ],
        "example": ["f(x) = x^2 sin(x)", "f'(x) = 2x sin(x) + x^2 cos(x)"],
        "practice": "derivative_rule",
    },
    "quotient-rule": {
        "title": "The quotient rule",
        "topic": "Calculus",
        "summary": "$\\left(\\frac{u}{v}\\right)' = \\frac{u'v - uv'}{v^2}$",
        "body": [
            "Order matters because of the minus sign: start with the derivative of the top.",
            "A memory trick: \"low d-high minus high d-low, over the square of what's below.\"",
        ],
        "example": ["f(x) = x/(x + 1)", "f'(x) = ((x + 1) - x)/(x + 1)^2", "f'(x) = 1/(x + 1)^2"],
        "practice": "derivative_rule",
    },
    "checking-antiderivatives": {
        "title": "Checking an antiderivative by differentiating",
        "topic": "Calculus",
        "summary": "If the derivative of your answer is the integrand, your answer is right.",
        "body": [
            "Integrating is hard, but checking is easy: differentiate your answer. If you get back the integrand, "
            "you're right — whatever form your answer takes.",
            "That's why $\\sin^2 x + C$ and $-\\cos^2 x + C$ are both correct for $\\int 2\\sin x\\cos x\\,dx$: "
            "they differ by a constant, and constants vanish when you differentiate.",
            "That's also why every antiderivative gets a $+\\,C$.",
        ],
        "example": ["∫ 2 sin(x) cos(x) dx", "= sin(x)^2 + C"],
        "practice": "antiderivative_error",
    },
    "dividing-by-variables": {
        "title": "Why dividing by a variable can lose a solution",
        "topic": "Algebra",
        "summary": "You can't divide by zero, so dividing by $x$ silently assumes $x \\ne 0$.",
        "body": [
            "In $x^2 = 5x$, dividing both sides by $x$ gives $x = 5$ — but $x = 0$ also works in the original.",
            "Dividing by $x$ is only allowed when $x \\ne 0$, so that solution gets thrown away. "
            "Instead, move everything to one side and factor.",
        ],
        "example": ["x^2 = 5x", "x^2 - 5x = 0", "x(x - 5) = 0", "x = 0 or x = 5"],
        "practice": "lost_solution",
    },
    "square-roots": {
        "title": "Square roots give two answers",
        "topic": "Algebra",
        "summary": "If $x^2 = 9$, then $x = 3$ or $x = -3$.",
        "body": [
            "Both $3^2$ and $(-3)^2$ equal $9$, so taking the square root of both sides gives $x = \\pm 3$.",
        ],
        "example": ["x^2 = 9", "x = ±3"],
        "practice": "lost_solution",
    },
    "extraneous-solutions": {
        "title": "Extra solutions from squaring",
        "topic": "Algebra",
        "summary": "Squaring both sides can create answers that don't work in the original.",
        "body": [
            "$-2 \\ne 2$, but $(-2)^2 = 2^2$. Squaring erases signs, so the squared equation can have more solutions.",
            "Always check each answer in the original equation and discard the ones that fail.",
        ],
        "example": ["sqrt(x + 2) = x", "x + 2 = x^2", "x^2 - x - 2 = 0", "(x - 2)(x + 1) = 0", "x = 2 or x = -1"],
        "practice": "extra_solution",
    },
}


def list_lessons() -> list[dict]:
    return [{"id": k, "title": v["title"], "topic": v["topic"], "summary": v["summary"]}
            for k, v in LESSONS.items()]


@lru_cache(maxsize=64)
def get_lesson(lesson_id: str) -> dict | None:
    lesson = LESSONS.get(lesson_id)
    if lesson is None:
        return None
    lines = [{"index": i, "math": m} for i, m in enumerate(lesson["example"])]
    res = check_lines(lines)
    return {"id": lesson_id, **{k: v for k, v in lesson.items() if k != "example"},
            "example": [{"math": m, "latex": line_to_latex(m)[0] or m, "status": r["status"],
                         "tier": r.get("tier"), "note": r.get("note")}
                        for m, r in zip(lesson["example"], res["lines"])]}
