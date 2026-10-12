"""Generate the sample "phone photos" of handwritten work used for demos and tests.

Each sample is rendered with a handwriting font on ruled paper, then placed on
a desk with a perspective tilt, uneven lighting, blur and sensor noise, so the
real computer-vision pipeline (paper detection, warp, ruled-line removal,
line splitting) has something realistic to work on.

The ground-truth transcription of every line is stored next to the images.
Those truths stand in for the vision model when no API key is configured,
so the full app can be tried end to end. They are never used for user photos.

Run from backend/:  python scripts/make_samples.py
"""

from __future__ import annotations

import json
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "app", "samples")
FONTS = {"caveat": os.path.join(HERE, "fonts", "caveat.woff"),
         "kalam": os.path.join(HERE, "fonts", "kalam.woff")}
SYMBOL_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# display: what's written (^ marks a superscript, {..} groups it)
SAMPLES = [
    {
        "id": "sign-error",
        "title": "Solving a linear equation",
        "description": "A dropped sign when a term moves across the equals sign.",
        "font": "caveat",
        "lines": [
            {"display": "2x + 3 = 7", "math": "2x + 3 = 7", "latex": "2x+3=7"},
            {"display": "2x = 10", "math": "2x = 10", "latex": "2x=10"},
            {"display": "x = 5", "math": "x = 5", "latex": "x=5",
             "alternatives": ["x = 5", "x = s"]},
        ],
    },
    {
        "id": "distribution",
        "title": "Distributing a negative",
        "description": "The -2 doesn't get multiplied through correctly.",
        "font": "kalam",
        "lines": [
            {"display": "-2(x - 3) + 4 = 10", "math": "-2(x - 3) + 4 = 10", "latex": "-2(x-3)+4=10"},
            {"display": "-2x - 6 + 4 = 10", "math": "-2x - 6 + 4 = 10", "latex": "-2x-6+4=10"},
            {"display": "-2x - 2 = 10", "math": "-2x - 2 = 10", "latex": "-2x-2=10"},
            {"display": "-2x = 12", "math": "-2x = 12", "latex": "-2x=12"},
            {"display": "x = -6", "math": "x = -6", "latex": "x=-6"},
        ],
    },
    {
        "id": "all-correct",
        "title": "A fully correct solution",
        "description": "Every step checks out.",
        "font": "caveat",
        "lines": [
            {"display": "3(x - 2) = 2x + 5", "math": "3(x - 2) = 2x + 5", "latex": "3(x-2)=2x+5"},
            {"display": "3x - 6 = 2x + 5", "math": "3x - 6 = 2x + 5", "latex": "3x-6=2x+5"},
            {"display": "x - 6 = 5", "math": "x - 6 = 5", "latex": "x-6=5"},
            {"display": "x = 11", "math": "x = 11", "latex": "x=11"},
        ],
    },
    {
        "id": "quadratic",
        "title": "Factoring a quadratic",
        "description": "A correct factoring solution.",
        "font": "kalam",
        "lines": [
            {"display": "x^2 - 5x + 6 = 0", "math": "x^2 - 5x + 6 = 0", "latex": "x^2-5x+6=0"},
            {"display": "(x - 2)(x - 3) = 0", "math": "(x - 2)(x - 3) = 0", "latex": "(x-2)(x-3)=0"},
            {"display": "x = 2 or x = 3", "math": "x = 2 or x = 3", "latex": "x=2 \\text{ or } x=3"},
        ],
    },
    {
        "id": "chain-rule",
        "title": "A derivative (calculus)",
        "description": "The chain rule's inner derivative goes missing.",
        "font": "caveat",
        "lines": [
            {"display": "f(x) = (x^2 + 1)^5", "math": "f(x) = (x^2 + 1)^5", "latex": "f(x)=(x^2+1)^5"},
            {"display": "f'(x) = 5(x^2 + 1)^4", "math": "f'(x) = 5(x^2 + 1)^4", "latex": "f'(x)=5(x^2+1)^4"},
        ],
    },
    {
        "id": "integral",
        "title": "An integral (calculus)",
        "description": "Checked by differentiating the answer.",
        "font": "kalam",
        "lines": [
            {"display": "∫ 2x cos(x^2) dx", "math": "∫ 2x cos(x^2) dx", "latex": "\\int 2x\\cos(x^2)\\,dx"},
            {"display": "= sin(x^2) + C", "math": "= sin(x^2) + C", "latex": "=\\sin(x^2)+C"},
        ],
    },
    {
        "id": "inequality",
        "title": "An inequality",
        "description": "Dividing by a negative without flipping the sign.",
        "font": "caveat",
        "lines": [
            {"display": "-3x + 4 > 10", "math": "-3x + 4 > 10", "latex": "-3x+4>10"},
            {"display": "-3x > 6", "math": "-3x > 6", "latex": "-3x>6"},
            {"display": "x > -2", "math": "x > -2", "latex": "x>-2"},
        ],
    },
    {
        "id": "homework-page",
        "title": "A whole homework page",
        "description": "Two problems on one page (whole-page mode).",
        "font": "kalam",
        "page": True,
        "lines": [
            {"display": "5x - 4 = 11", "math": "5x - 4 = 11", "latex": "5x-4=11", "problem": 0},
            {"display": "5x = 15", "math": "5x = 15", "latex": "5x=15", "problem": 0},
            {"display": "x = 3", "math": "x = 3", "latex": "x=3", "problem": 0},
            {"gap": 2},
            {"display": "4(x + 1) = 20", "math": "4(x + 1) = 20", "latex": "4(x+1)=20", "problem": 1},
            {"display": "4x + 1 = 20", "math": "4x + 1 = 20", "latex": "4x+1=20", "problem": 1},
            {"display": "4x = 19", "math": "4x = 19", "latex": "4x=19", "problem": 1},
        ],
    },
]


def parse_display(s):
    """[(text, is_superscript)] from 'x^2 + (x+1)^{10}'."""
    out, i = [], 0
    while i < len(s):
        if s[i] == "^" and i + 1 < len(s):
            if s[i + 1] == "{":
                j = s.index("}", i)
                out.append((s[i + 2:j], True))
                i = j + 1
            else:
                out.append((s[i + 1], True))
                i += 2
        else:
            out.append((s[i], False))
            i += 1
    return out


def draw_line(draw, x, baseline, text, font, sup_font, sym_font, rng, ink):
    for chunk, sup in parse_display(text):
        for ch in chunk:
            f = sup_font if sup else font
            if ch == "∫":
                f = sym_font
            jitter = rng.uniform(-2.5, 2.5)
            y = baseline - (f.size * (1.25 if sup else 0.85)) + jitter
            if ch == "∫":
                y = baseline - f.size * 0.95
            if ch == " ":
                x += font.size * 0.28
                continue
            draw.text((x, y), ch, font=f, fill=ink)
            bbox = draw.textbbox((x, y), ch, font=f)
            x = bbox[2] + rng.uniform(1.0, 4.0)
    return x


def render_page(sample, rng):
    W, H = 1100, 1450
    page = Image.new("RGB", (W, H), (247, 245, 238))
    d = ImageDraw.Draw(page)
    spacing = 74
    top = 170
    for y in range(top, H - 40, spacing):
        d.line([(0, y), (W, y)], fill=(150, 185, 225), width=2)
    d.line([(120, 0), (120, H)], fill=(230, 150, 150), width=2)

    font = ImageFont.truetype(FONTS[sample["font"]], 66)
    sup_font = ImageFont.truetype(FONTS[sample["font"]], 42)
    sym_font = ImageFont.truetype(SYMBOL_FONT, 70)
    ink = rng.choice([(28, 38, 92), (30, 30, 34), (22, 40, 110)])
    row = 1
    for line in sample["lines"]:
        if "gap" in line:
            row += line["gap"]
            continue
        baseline = top + row * spacing * 1.25 - 8
        x0 = 160 + rng.uniform(-8, 20)
        draw_line(d, x0, baseline, line["display"], font, sup_font, sym_font, rng, ink)
        row += 1
    return page


def photograph(page, rng):
    """Place the page on a desk with a perspective tilt, light falloff, blur and noise."""
    PW, PH = 1500, 1950
    desk = np.zeros((PH, PW, 3), np.float32)
    base = np.array(rng.choice([(110, 78, 52), (70, 72, 78), (130, 112, 92)]), np.float32)
    yy, xx = np.mgrid[0:PH, 0:PW]
    desk[:] = base
    desk += (np.sin(xx / 37.0 + yy / 400.0) * 6)[..., None]
    desk = np.clip(desk, 0, 255).astype(np.uint8)
    desk_img = Image.fromarray(desk)

    import cv2
    w, h = page.size
    margin = 140
    dst = np.array([
        [margin + rng.uniform(-40, 60), margin + rng.uniform(-30, 60)],
        [PW - margin + rng.uniform(-60, 40), margin + rng.uniform(-30, 60)],
        [PW - margin + rng.uniform(-60, 30), PH - margin + rng.uniform(-60, 30)],
        [margin + rng.uniform(-30, 60), PH - margin + rng.uniform(-60, 30)],
    ], np.float32)
    src = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    page_arr = np.array(page)
    warped = cv2.warpPerspective(page_arr, M, (PW, PH), borderValue=(0, 0, 0))
    mask = cv2.warpPerspective(np.full((h, w), 255, np.uint8), M, (PW, PH))
    out = np.array(desk_img).copy()
    out[mask > 0] = warped[mask > 0]

    # Uneven light: a soft gradient plus a vignette.
    cx, cy = rng.uniform(0.3, 0.7) * PW, rng.uniform(0.2, 0.6) * PH
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / math.hypot(PW, PH)
    light = 1.08 - 0.45 * dist
    out = np.clip(out.astype(np.float32) * light[..., None], 0, 255)
    out += rng.uniform(2, 5) * np.random.default_rng(rng.randint(0, 10 ** 6)).standard_normal(out.shape)
    out = np.clip(out, 0, 255).astype(np.uint8)
    img = Image.fromarray(out).filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.6, 1.1)))
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    index = []
    for i, sample in enumerate(SAMPLES):
        rng = random.Random(1000 + i)
        page = render_page(sample, rng)
        photo = photograph(page, rng)
        fname = f"{sample['id']}.jpg"
        photo.save(os.path.join(OUT, fname), quality=86)
        lines = [{k: v for k, v in l.items() if k != "display"} for l in sample["lines"] if "gap" not in l]
        for l in lines:
            l.setdefault("type", "equation")
        index.append({
            "id": sample["id"], "title": sample["title"], "description": sample["description"],
            "file": fname, "page": bool(sample.get("page")), "lines": lines,
        })
        print("wrote", fname)
    with open(os.path.join(OUT, "samples.json"), "w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    print("wrote samples.json")


if __name__ == "__main__":
    sys.exit(main())
