import pytest

from app.engine.practice import GENERATORS, check_answer, compute_answer, make_problems


@pytest.mark.parametrize("skill", sorted(GENERATORS))
def test_generators_make_verified_problems(skill):
    for level in (1, 2, 3):
        probs = make_problems(skill, count=3, level=level, seed=level * 7)
        assert len(probs) == 3, (skill, level)
        for p in probs:
            ans = compute_answer(p)
            assert ans["available"], p
            assert "answer" not in p and "solution" not in p  # never leaked up front


def test_check_answer_solve():
    p = {"kind": "solve", "math": "2x + 3 = 7"}
    assert check_answer(p, "x = 2")["correct"]
    assert check_answer(p, "2")["correct"]
    assert not check_answer(p, "x = 3")["correct"]
    r = check_answer(p, "2x = 4")
    assert not r["correct"] and r.get("equivalent")


def test_check_answer_quadratic_and_inequality():
    assert check_answer({"kind": "solve", "math": "x^2 - 5x + 6 = 0"}, "x = 2 or x = 3")["correct"]
    assert check_answer({"kind": "solve", "math": "x^2 - 5x + 6 = 0"}, "2, 3")["correct"]
    assert not check_answer({"kind": "solve", "math": "x^2 - 5x + 6 = 0"}, "x = 2")["correct"]
    assert check_answer({"kind": "solve", "math": "-2x + 1 > 7"}, "x < -3")["correct"]
    assert not check_answer({"kind": "solve", "math": "-2x + 1 > 7"}, "x > -3")["correct"]


def test_check_answer_calculus():
    assert check_answer({"kind": "differentiate", "math": "x^2 sin(x)"}, "2x sin(x) + x^2 cos(x)")["correct"]
    assert not check_answer({"kind": "differentiate", "math": "x^2 sin(x)"}, "2x cos(x)")["correct"]
    r = check_answer({"kind": "integrate", "math": "cos(2x)"}, "sin(2x)/2 + C")
    assert r["correct"] and "+ C" not in r["message"]
    r = check_answer({"kind": "integrate", "math": "cos(2x)"}, "sin(2x)/2")
    assert r["correct"] and "+ C" in r["message"]


def test_check_answer_forms():
    assert check_answer({"kind": "expand", "math": "(x + 3)^2"}, "x^2 + 6x + 9")["correct"]
    assert not check_answer({"kind": "expand", "math": "(x + 3)^2"}, "(x+3)(x+3)")["correct"]
    assert check_answer({"kind": "factor", "math": "x^2 + 5x + 6"}, "(x+2)(x+3)")["correct"]
    assert not check_answer({"kind": "factor", "math": "x^2 + 5x + 6"}, "x^2 + 5x + 6")["correct"]
    assert check_answer({"kind": "solve_system", "math": "x + y = 5; x - y = 1"}, "x = 3, y = 2")["correct"]
    assert check_answer({"kind": "limit", "math": "lim_(x->1) (x^2 - 1)/(x - 1)"}, "2")["correct"]
