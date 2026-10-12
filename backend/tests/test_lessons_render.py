import pytest

from app.engine.lessons import LESSONS, get_lesson, list_lessons
from app.engine.hints import LESSON_FOR
from app.engine.render import line_to_latex


@pytest.mark.parametrize("lesson_id", sorted(LESSONS))
def test_lesson_examples_verify(lesson_id):
    lesson = get_lesson(lesson_id)
    statuses = [l["status"] for l in lesson["example"]]
    assert statuses[0] == "start"
    assert all(s in ("ok", "start", "warning") for s in statuses), lesson
    assert all(l["latex"] for l in lesson["example"])


def test_every_hint_lesson_exists():
    for lesson_id in LESSON_FOR.values():
        assert lesson_id in LESSONS
    assert len(list_lessons()) == len(LESSONS)


@pytest.mark.parametrize("text,expected", [
    ("2x + 3 = 7", "2 x + 3 = 7"),
    ("f'(x) = 2x", "f'(x) = 2 x"),
    ("x = 2 or x = -3", r"x = 2 \;\text{ or }\; x = -3"),
    ("= x^2", "= x^{2}"),
    ("x <= 4", r"x \le 4"),
])
def test_line_to_latex(text, expected):
    ltx, err = line_to_latex(text)
    assert err is None
    assert ltx == expected


def test_line_to_latex_error():
    ltx, err = line_to_latex("2x + (3")
    assert ltx is None and err
