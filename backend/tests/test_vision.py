import io
import json
import os

import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.vision.pipeline import ImageError, group_problems, process_image

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "app", "samples")


def _load_samples():
    with open(os.path.join(SAMPLES, "samples.json")) as f:
        return json.load(f)


@pytest.mark.parametrize("sample", _load_samples(), ids=lambda s: s["id"])
def test_samples_segment_into_the_right_lines(sample):
    with open(os.path.join(SAMPLES, sample["file"]), "rb") as f:
        data = f.read()
    res = process_image(data, "page" if sample["page"] else "problem")
    assert res.paper_found
    assert len(res.lines) == len(sample["lines"])
    tops = [l.box[1] for l in res.lines]
    assert tops == sorted(tops)
    if sample["page"]:
        assert [l.problem for l in res.lines] == [l["problem"] for l in sample["lines"]]


def _png(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_plain_white_image_with_strokes_no_paper():
    img = Image.new("RGB", (800, 300), "white")
    d = ImageDraw.Draw(img)
    d.line([(50, 150), (700, 160)], fill="black", width=6)
    d.line([(100, 100), (120, 200)], fill="black", width=6)
    res = process_image(_png(img), "line")
    assert not res.paper_found
    assert len(res.lines) == 1


def test_transparent_png_stylus_drawing():
    img = Image.new("RGBA", (600, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(40, 100), (500, 110)], fill=(0, 0, 0, 255), width=5)
    d.line([(200, 50), (210, 160)], fill=(0, 0, 0, 255), width=5)
    res = process_image(_png(img), "line")
    assert len(res.lines) == 1


def test_blank_image_has_no_lines():
    res = process_image(_png(Image.new("RGB", (640, 480), (240, 240, 240))))
    assert res.lines == [] and "no_lines" in res.warnings


def test_exif_rotation_is_applied():
    img = Image.new("RGB", (400, 200), "white")
    exif = img.getexif()
    exif[0x0112] = 6  # rotate 90
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    res = process_image(buf.getvalue())
    assert (res.width, res.height) == (200, 400)


@pytest.mark.parametrize("data", [b"", b"hello", b"\x89PNG\r\n\x1a\n" + b"\x00" * 10])
def test_bad_inputs(data):
    with pytest.raises(ImageError):
        process_image(data)


def test_tiny_image_rejected():
    with pytest.raises(ImageError):
        process_image(_png(Image.new("RGB", (10, 10), "white")))


def test_group_problems():
    boxes = [(0, 0, 10, 40), (0, 60, 10, 100), (0, 300, 10, 340), (0, 360, 10, 400)]
    assert group_problems(boxes) == [0, 0, 1, 1]
    assert group_problems([(0, 0, 1, 1)]) == [0]


def _variants():
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import make_samples
    out = []
    for i, sample in enumerate(make_samples.SAMPLES):
        for k in range(4):
            out.append((sample, 7000 + i * 10 + k))
    return out, make_samples


VARIANTS, MS = _variants()


@pytest.mark.parametrize("sample,seed", VARIANTS, ids=[f"{s['id']}-{seed}" for s, seed in VARIANTS])
def test_randomized_photos_split_correctly(sample, seed):
    img = MS.variant(sample, seed)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    expected = len([l for l in sample["lines"] if "gap" not in l])
    res = process_image(buf.getvalue(), "page" if sample.get("page") else "problem")
    assert len(res.lines) == expected
