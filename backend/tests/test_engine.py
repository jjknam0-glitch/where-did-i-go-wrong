"""Unit tests for the math engine (no photos needed).

The most important property is the false-alarm policy: correct work must
never be flagged. Many tricky *valid* pairs are included for that reason.
"""

import pytest

from app.engine.checker import check_fix, check_lines, final_answer


def run(*lines, **kw):
    return check_lines([{"index": i, "math": m} for i, m in enumerate(lines)], **kw)


def statuses(res):
    return [l["status"] for l in res["lines"]]


# --------------------------------------------------------------------------
# valid work is never flagged
# --------------------------------------------------------------------------

VALID_PROBLEMS = [
    ["2x + 3 = 7", "2x = 4", "x = 2"],
    ["2x + 3 = 7", "2x = 7 - 3", "2x = 4", "x = 4/2", "x = 2"],
    ["3(x - 2) = 2x + 5", "3x - 6 = 2x + 5", "x - 6 = 5", "x = 11"],
    ["-2(x - 3) + 4 = 10", "-2x + 6 + 4 = 10", "-2x + 10 = 10", "-2x = 0", "x = 0"],
    ["x/3 + 2 = 5", "x/3 = 3", "x = 9"],
    ["5 - 2x = 9", "-2x = 4", "x = -2"],
    ["x^2 - 5x + 6 = 0", "(x - 2)(x - 3) = 0", "x = 2 or x = 3"],
    ["x^2 = 9", "x = ±3"],
    ["x^2 = 9", "x = 3 or x = -3"],
    ["x^2 - 4 = 0", "x^2 = 4", "x = 2, x = -2"],
    ["0.5x + 1 = 2", "0.5x = 1", "x = 2"],
    ["-2x < 6", "x > -3"],
    ["3x + 1 >= 10", "3x >= 9", "x >= 3"],
    ["x + y = 5; x - y = 1", "2x = 6", "x = 3", "y = 2"],
    ["(x+1)^2", "x^2 + 2x + 1"],
    ["2(x + 3) - 4", "2x + 6 - 4", "2x + 2"],
    ["x^2 + 5x + 6", "(x + 2)(x + 3)"],
    ["(x^2 - 1)/(x - 1)", "x + 1"],
    ["sin(x)^2 + cos(x)^2", "1"],
    ["2 sin x cos x", "sin(2x)"],
    ["log(x^2)", "2 log(x)"],
    ["d/dx (x^2 sin x)", "= 2x sin x + x^2 cos x"],
    ["f(x) = x^3 sin(x)", "f'(x) = 3x^2 sin(x) + x^3 cos(x)"],
    ["f(x) = (x^2 + 1)^5", "f'(x) = 5(x^2 + 1)^4 * 2x", "f'(x) = 10x(x^2+1)^4"],
    ["y = e^(3x)", "dy/dx = 3e^(3x)"],
    ["∫ 2x dx", "= x^2 + C"],
    ["∫ 2 sin(x) cos(x) dx", "= sin(x)^2 + C"],
    ["∫ 2 sin(x) cos(x) dx", "= -cos(x)^2 + C"],
    ["∫ (3x^2 + 2x) dx", "= ∫ 3x^2 dx + ∫ 2x dx", "= x^3 + x^2 + C"],
    ["∫_0^2 x dx", "= 2"],
    ["lim_{x->1} (x^2 - 1)/(x - 1)", "= lim_{x->1} (x + 1)", "= 2"],
    ["2x + 3 = 7", "÷2 both sides", "x + 3/2 = 7/2"],
    ["4x = 2x + 10", "2x = 10", "x = 5"],
    ["(x + 2)/3 = 4", "x + 2 = 12", "x = 10"],
    ["7x + 12 = 3x - 8", "4x + 12 = -8", "4x = -20", "x = -5"],
]


@pytest.mark.parametrize("lines", VALID_PROBLEMS, ids=[" | ".join(p) for p in VALID_PROBLEMS])
def test_valid_work_is_not_flagged(lines):
    payload = [{"index": i, "math": m, "type": "note" if "both sides" in m else "equation"}
               for i, m in enumerate(lines)]
    res = check_lines(payload)
    st = statuses(res)
    assert "error" not in st, res
    assert "uncertain" not in st, res
    assert res["first_error"] is None


def test_all_correct_flag_and_tiers():
    res = run("2x + 3 = 7", "2x = 4", "x = 2")
    assert res["all_correct"] is True
    assert statuses(res) == ["start", "ok", "ok"]
    assert all(l.get("tier") == "verified" for l in res["lines"][1:])
    assert res["sanity_check"] == "consistent"
    assert res["topic"] == "linear"


def test_note_is_skipped():
    res = check_lines([{"index": 0, "math": "2x = 4"}, {"index": 1, "math": "divide by 2", "type": "note"},
                       {"index": 2, "math": "x = 2"}])
    assert statuses(res) == ["start", "skipped", "ok"]


# --------------------------------------------------------------------------
# planted errors: located and classified
# --------------------------------------------------------------------------

ERROR_CASES = [
    # (lines, error line, error type, subtype)
    (["2x + 3 = 7", "2x = 10", "x = 5"], 1, "sign_error", "moved"),
    (["2x + 3 = 7", "2x = 7", "x = 7/2"], 1, "one_side_only", "shift"),
    (["3x = 12", "x = 12"], 1, "one_side_only", "scale"),
    (["-2(x - 3) = 4", "-2x - 6 = 4"], 1, "sign_error", "distribution"),
    (["-2(x - 3) = 4", "-2x - 3 = 4"], 1, "distribution_error", "missed_term"),
    (["2x + 3 = 7", "2x = 5"], 1, "arithmetic_slip", None),
    (["2x = 4", "x = 3"], 1, "arithmetic_slip", None),
    (["(x + 3)^2", "x^2 + 9"], 1, "exponent_rule", "power_of_sum"),
    (["-2x < 6", "x < -3"], 1, "inequality_flip", None),
    (["f(x) = sin(3x)", "f'(x) = cos(3x)"], 1, "derivative_rule", "chain_rule"),
    (["f(x) = x^2 sin(x)", "f'(x) = 2x cos(x)"], 1, "derivative_rule", "product_rule"),
    (["f(x) = x^5", "f'(x) = 5x^5"], 1, "derivative_rule", "power_rule"),
    (["∫ sin(x) dx", "= cos(x) + C"], 1, "antiderivative_error", "sign"),
    (["∫ x^2 dx", "= x^3 + C"], 1, "antiderivative_error", "coefficient"),
    (["x^2 = 9", "x = 3"], 1, "lost_solution", "square_root"),
    (["3x + 2x = 20", "6x = 20"], 1, "arithmetic_slip", None),
]


@pytest.mark.parametrize("lines,err,etype,sub", ERROR_CASES, ids=[" | ".join(c[0]) for c in ERROR_CASES])
def test_planted_errors(lines, err, etype, sub):
    res = run(*lines)
    assert res["first_error"] == err, res
    line = res["lines"][err]
    assert line["status"] == "error"
    assert line["error_type"] == etype, line
    if sub is not None:
        assert line.get("subtype") == sub, line
    assert len(line["hints"]) == 3
    assert line["hints"][0].startswith("Something's off")


def test_sign_error_hints_use_student_numbers():
    res = run("2x + 3 = 7", "2x = 10", "x = 5")
    line = res["lines"][1]
    assert "+3" in line["hints"][1]
    assert "2 x = 4" in line["hints"][2].replace("x=", "x =") or "2x = 4" in line["hints"][2].replace(" ", "") \
        or "2 x = 4" in line["hints"][2]
    assert res["lines"][2]["status"] == "follows_from_error"


def test_only_first_break_counts():
    res = run("2x + 3 = 7", "2x = 10", "x = 5")
    assert statuses(res) == ["start", "error", "follows_from_error"]


def test_arithmetic_origin_hint():
    res = run("2x + 3 = 7", "2x = 5")
    hint = res["lines"][1]["hints"][1]
    assert "7 - 3" in hint


def test_dividing_by_variable_is_warning():
    res = run("x^2 = 5x", "x = 5")
    line = res["lines"][1]
    assert line["status"] == "warning"
    assert line["error_type"] == "lost_solution"
    assert res["first_error"] is None


def test_squaring_both_sides_is_warning():
    res = run("sqrt(x) = x - 2", "x = (x - 2)^2", "x = x^2 - 4x + 4", "x^2 - 5x + 4 = 0",
              "(x - 1)(x - 4) = 0", "x = 1 or x = 4")
    assert res["lines"][1]["status"] == "warning"
    assert res["lines"][1]["error_type"] == "extra_solution"
    assert res["first_error"] is None


def test_missing_constant_gentle_note():
    res = run("∫ 2x dx", "= x^2")
    line = res["lines"][1]
    assert line["status"] == "ok"
    assert "constant" in line.get("note", "")


def test_rounded_answer_accepted():
    res = run("3x = 8", "x = 2.67")
    assert res["lines"][1]["status"] == "ok"
    assert "Rounded" in res["lines"][1].get("note", "")


def test_unparseable_line_is_uncertain():
    res = run("2x + 3 = 7", "2x = (4", "x = 2")
    assert res["lines"][1]["status"] == "uncertain"
    assert res["lines"][1]["reason"] == "parse_error"
    # The next line can't be blamed for a step it may not have made.
    assert res["lines"][2]["status"] in ("ok", "uncertain")


def test_gap_does_not_produce_false_alarm():
    res = run("2x + 3 = 7", "2x = (4", "x = 9")
    assert res["lines"][2]["status"] == "uncertain"
    assert res["first_error"] is None


def test_sanity_conflict_marks_uncertain_then_acknowledged():
    lines = ["2x + 3 = 7", "2x = 6", "x = 2"]  # 7-3 slip then a second slip that cancels
    res = run(*lines)
    assert res["sanity_check"] == "conflict"
    assert res["first_error"] is None
    assert any(l["status"] == "uncertain" and l.get("reason") == "sanity_conflict" for l in res["lines"])
    res2 = run(*lines, acknowledge_sanity=True)
    assert res2["sanity_check"] == "acknowledged"
    assert res2["first_error"] == 1


def test_trig_identity_numeric_or_verified():
    res = run("tan(x) cos(x)", "sin(x)")
    assert res["lines"][1]["status"] == "ok"
    assert res["lines"][1]["tier"] in ("verified", "numeric")


def test_domain_restricted_step_is_warning():
    res = run("sqrt(x^2)", "x")
    assert res["lines"][1]["status"] == "warning"


def test_system_error_detected():
    res = run("x + y = 5; x - y = 1", "2x = 8")
    assert res["first_error"] == 1


def test_chain_inside_one_line():
    res = run("2(x + 3) - 4 = 2x + 6 - 4 = 2x + 3")
    assert res["lines"][0]["status"] == "error"
    assert res["first_error"] == 0


def test_function_mode_second_derivative():
    res = run("f(x) = x^4", "f'(x) = 4x^3", "f''(x) = 12x^2")
    assert statuses(res) == ["start", "ok", "ok"]
    res = run("f(x) = x^4", "f'(x) = 4x^3", "f''(x) = 12x^3")
    assert res["first_error"] == 2


def test_derivative_then_solve():
    res = run("f(x) = x^2 + 3x", "f'(x) = 2x + 3", "2x + 3 = 0", "x = -3/2")
    assert "error" not in statuses(res)
    assert "uncertain" not in statuses(res)


def test_topics():
    assert run("x^2 - 4 = 0", "x = 2 or x = -2")["topic"] == "quadratics"
    assert run("∫ 2x dx", "= x^2 + C")["topic"] == "integrals"
    assert run("f(x) = x^2", "f'(x) = 2x")["topic"] == "derivatives"
    assert run("-2x < 6", "x > -3")["topic"] == "inequalities"
    r = run("f(x) = x^2", "f'(x) = 2x")
    assert r["advanced"] is True


# --------------------------------------------------------------------------
# fix it yourself
# --------------------------------------------------------------------------

def test_fix_correct_then_recheck_later_lines():
    lines = [{"index": i, "math": m} for i, m in enumerate(["2x + 3 = 7", "2x = 10", "x = 5"])]
    out = check_fix(lines, 1, "2x = 4")
    assert out["valid"] is True
    # Line 3 was derived from the old mistake, so it is now the first error.
    assert out["check"]["first_error"] == 2
    out2 = check_fix(out["lines"], 2, "x = 2")
    assert out2["valid"] is True
    assert out2["check"]["first_error"] is None
    assert out2["check"]["all_correct"] is True


def test_fix_wrong_attempt():
    lines = [{"index": i, "math": m} for i, m in enumerate(["2x + 3 = 7", "2x = 10"])]
    out = check_fix(lines, 1, "2x = 3")
    assert out["valid"] is False
    assert out["fix"]["status"] == "error"
    assert out["check"] is None


# --------------------------------------------------------------------------
# final answer only on request
# --------------------------------------------------------------------------

def test_final_answer():
    assert final_answer([{"math": "2x + 3 = 7"}])["latex"] == "x = 2"
    a = final_answer([{"math": "x^2 = 9"}])
    assert a["available"] and "3" in a["latex"]
    a = final_answer([{"math": "f(x) = x^3"}])
    assert a["available"] and "3 x^{2}" in a["latex"]
    a = final_answer([{"math": "x + y = 5; x - y = 1"}])
    assert "x = 3" in a["latex"] and "y = 2" in a["latex"]


# --------------------------------------------------------------------------
# parser safety
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    "__import__('os').system('ls')", "x.__class__", "().__class__", "9^9^9^9", "lambda: 1",
    "exec(1)", "1000000!",
])
def test_hostile_input_is_rejected(bad):
    res = run(bad)
    assert res["lines"][0]["status"] == "uncertain"
