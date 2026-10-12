"""Computer vision: from a phone photo to a list of line crops.

Stage 1 - clean up the photo: fix rotation (EXIF), find the paper and warp it
flat, even out lighting (CLAHE + adaptive threshold) and remove notebook lines.
Stage 2 - split into lines with a horizontal projection profile, merging
fraction parts, dropping noise and falling back to connected-component
clustering when the profile is ambiguous.

Boxes are returned in the coordinates of the (EXIF-corrected) uploaded image,
mapped back through the inverse perspective warp.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageOps

MAX_WORK_SIDE = 2000      # downscale large photos before processing
WARP_MAX_SIDE = 1600      # size of the flattened page
CROP_MAX_WIDTH = 800      # crops sent for transcription
THUMB_HEIGHT = 96         # crops shown on the confirm screen
MAX_LINES = 40


class ImageError(ValueError):
    """The upload isn't a usable image."""


@dataclass
class LineBox:
    index: int
    box: list            # [left, top, right, bottom] in uploaded-image pixels
    quad: list           # 4 [x, y] corners in uploaded-image pixels
    crop_png: bytes      # crop for the vision model
    thumb: str           # data URL (JPEG) for display
    problem: int = 0
    warped_box: tuple = (0, 0, 0, 0)


@dataclass
class VisionResult:
    width: int
    height: int
    lines: list = field(default_factory=list)
    paper_found: bool = False
    warnings: list = field(default_factory=list)


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------

def load_image(data: bytes) -> np.ndarray:
    """Decode, fix EXIF rotation and return an RGB array."""
    if not data:
        raise ImageError("Empty upload")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        raise ImageError("That file isn't an image we can read") from exc
    if img.width * img.height > 60_000_000:
        raise ImageError("Image is too large")
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode in ("RGBA", "LA") or "transparency" in img.info:
            rgba = img.convert("RGBA")
            background.paste(rgba, mask=rgba.split()[-1])
            img = background
        else:
            img = img.convert("RGB")
    elif img.mode == "L":
        img = img.convert("RGB")
    arr = np.array(img)
    if arr.ndim != 3 or arr.shape[0] < 32 or arr.shape[1] < 32:
        raise ImageError("Image is too small")
    return arr


# --------------------------------------------------------------------------
# stage 1: clean up
# --------------------------------------------------------------------------

def order_points(pts: np.ndarray) -> np.ndarray:
    pts = pts.reshape(4, 2).astype(np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]],
                    dtype=np.float32)


def find_paper(rgb: np.ndarray):
    """Largest four-sided contour that looks like a page, in rgb's coordinates (or None)."""
    h, w = rgb.shape[:2]
    scale = 800.0 / max(h, w)
    small = cv2.resize(rgb, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    area_total = small.shape[0] * small.shape[1]
    candidates = []

    edges = cv2.Canny(blur, 40, 130)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
    cnts, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates += sorted(cnts, key=cv2.contourArea, reverse=True)[:8]

    _, bright = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    cnts2, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates += sorted(cnts2, key=cv2.contourArea, reverse=True)[:3]

    best = None
    for c in candidates:
        area = cv2.contourArea(c)
        if area < 0.07 * area_total:
            continue
        peri = cv2.arcLength(c, True)
        for eps in (0.02, 0.03, 0.045):
            approx = cv2.approxPolyDP(c, eps * peri, True)
            if len(approx) == 4 and cv2.isContourConvex(approx):
                a = cv2.contourArea(approx)
                if a > 0.97 * area_total:
                    break  # the page fills the frame; nothing to warp
                if best is None or a > best[0]:
                    best = (a, approx)
                break
    if best is None:
        # Wavy or partly shadowed edges: fall back to the bright region's rotated rectangle.
        for c in sorted(cnts2, key=cv2.contourArea, reverse=True)[:1]:
            area = cv2.contourArea(c)
            rect = cv2.minAreaRect(c)
            rect_area = rect[1][0] * rect[1][1]
            if 0.07 * area_total <= area <= 0.95 * area_total and rect_area > 0 and area / rect_area > 0.85:
                best = (area, cv2.boxPoints(rect).astype(np.float32))
    if best is None:
        return None
    quad = order_points(best[1]) / scale
    # Reject degenerate shapes (very skinny or bow-tied quads).
    tl, tr, br, bl = quad
    wtop, wbot = np.linalg.norm(tr - tl), np.linalg.norm(br - bl)
    hl, hr = np.linalg.norm(bl - tl), np.linalg.norm(br - tr)
    if min(wtop, wbot, hl, hr) < 0.1 * max(h, w):
        return None
    return quad


def warp_paper(rgb: np.ndarray, quad: np.ndarray):
    tl, tr, br, bl = quad
    width = max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl))
    height = max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl))
    s = min(1.0, WARP_MAX_SIDE / max(width, height))
    W, H = max(32, int(width * s)), max(32, int(height * s))
    dst = np.array([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(quad.astype(np.float32), dst)
    warped = cv2.warpPerspective(rgb, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return warped, M


def enhance(rgb: np.ndarray):
    """Grayscale -> CLAHE -> adaptive threshold. Returns (clahe_gray, ink_mask)."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    g = clahe.apply(gray)
    h, w = g.shape
    block = max(15, (min(h, w) // 25) | 1)
    ink = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block, 15)
    return g, ink


def page_extent(gray: np.ndarray) -> tuple[int, int]:
    """Width and height of the paper inside the image (the whole image after a warp)."""
    h, w = gray.shape
    _, bright = cv2.threshold(cv2.GaussianBlur(gray, (5, 5), 0), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    n, _lab, stats, _c = cv2.connectedComponentsWithStats(bright, connectivity=8)
    if n <= 1:
        return w, h
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    bw, bh = int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT])
    if bw < 0.2 * w or bh < 0.2 * h:
        return w, h
    return bw, bh


def remove_ruled_lines(ink: np.ndarray, page_w: int | None = None, page_h: int | None = None,
                       vertical: bool = True):
    """Remove notebook / grid lines. Returns (clean_ink, removed_mask)."""
    h, w = ink.shape
    pw = page_w or w
    ph = page_h or h
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, pw // 20), 1))
    horiz = cv2.morphologyEx(ink, cv2.MORPH_OPEN, hk)
    # Only rows where long segments cover a good part of the page are ruled lines
    # (this keeps long fraction bars and minus signs). Slightly slanted lines
    # spread over a few rows, so measure coverage on a vertically smeared copy.
    smeared = cv2.dilate(horiz, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 5)))
    coverage = (smeared > 0).sum(axis=1) / float(pw)
    rows = coverage > 0.3
    rows = np.convolve(rows.astype(np.uint8), np.ones(5, np.uint8), "same") > 0
    # Notebook paper has several parallel lines; a single long stroke (a stylus
    # drawing, a long fraction bar) is writing.
    if len(_runs(rows)) < 2:
        rows[:] = False
    horiz_mask = np.zeros_like(ink)
    horiz_mask[rows, :] = horiz[rows, :]
    horiz_mask = cv2.dilate(horiz_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3)))
    # Blur can break a ruled line into dashes that the long kernel misses. Inside
    # the ruled-line rows, also remove short horizontal dashes that have nothing
    # directly above or below them (so character strokes crossing the line stay).
    if rows.any():
        band = np.zeros_like(ink)
        band[rows, :] = ink[rows, :]
        dashes = cv2.morphologyEx(band, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 1)))
        shift = 4
        above = np.zeros_like(ink)
        below = np.zeros_like(ink)
        above[shift:, :] = ink[:-shift, :]
        below[:-shift, :] = ink[shift:, :]
        lonely = cv2.bitwise_and(dashes, cv2.bitwise_not(cv2.bitwise_or(above, below)))
        lonely = cv2.dilate(lonely, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
        lonely = cv2.bitwise_and(lonely, band)
        horiz_mask = cv2.bitwise_or(horiz_mask, lonely)

    # Margin lines and grid columns run most of the page height (possibly broken
    # into dashes by blur); a tall handwritten stroke doesn't.
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, ph // 30)))
    vbridged = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 15)))
    vert = cv2.bitwise_and(cv2.morphologyEx(vbridged, cv2.MORPH_OPEN, vk), ink)
    vsmeared = cv2.dilate(vert, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 1)))
    vcov = (vsmeared > 0).sum(axis=0) / float(ph)
    cols = vcov > (0.6 if vertical else 2.0)
    cols = np.convolve(cols.astype(np.uint8), np.ones(5, np.uint8), "same") > 0
    vert_mask = np.zeros_like(ink)
    if cols.any():
        vband = np.zeros_like(ink)
        vband[:, cols] = ink[:, cols]
        vdash = cv2.morphologyEx(vband, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 5)))
        shift = 4
        left = np.zeros_like(ink)
        right = np.zeros_like(ink)
        left[:, shift:] = ink[:, :-shift]
        right[:, :-shift] = ink[:, shift:]
        lonely_v = cv2.bitwise_and(vdash, cv2.bitwise_not(cv2.bitwise_or(left, right)))
        vert_mask = cv2.bitwise_or(cv2.bitwise_and(vert, vband), lonely_v)
        vert_mask = cv2.dilate(vert_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
        vert_mask = cv2.bitwise_and(vert_mask, vband)

    removed = cv2.bitwise_or(horiz_mask, vert_mask)
    clean = cv2.bitwise_and(ink, cv2.bitwise_not(removed))
    # Re-join strokes that crossed a removed line.
    clean = cv2.morphologyEx(clean, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 5)))
    return clean, removed


def remove_noise(ink: np.ndarray):
    """Drop tiny blobs and marks touching the page border. Returns (clean, component stats)."""
    h, w = ink.shape
    # Paper edges and shadows hug the border.
    band = max(3, int(0.012 * min(h, w)))
    ink = ink.copy()
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    min_area = max(8, int(h * w * 4e-6))
    keep = np.zeros(n, dtype=bool)
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < min_area:
            continue
        touches = x <= band or y <= band or x + bw >= w - band or y + bh >= h - band
        if touches and (bw > 0.5 * w or bh > 0.5 * h or area < 6 * min_area):
            continue
        if bw > 0.9 * w and bh < 0.02 * h:
            continue  # a leftover ruled line
        keep[i] = True
    clean = np.where(keep[labels], 255, 0).astype(np.uint8)
    kept_stats = stats[keep]
    return clean, kept_stats


# --------------------------------------------------------------------------
# stage 2: split into lines
# --------------------------------------------------------------------------

def _char_height(stats) -> float:
    if len(stats) == 0:
        return 20.0
    heights = stats[:, cv2.CC_STAT_HEIGHT]
    areas = stats[:, cv2.CC_STAT_AREA]
    big = heights[areas >= np.percentile(areas, 30)] if len(areas) > 3 else heights
    return float(max(8.0, np.median(big)))


def _runs(mask: np.ndarray):
    spans, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            spans.append([start, i - 1])
            start = None
    if start is not None:
        spans.append([start, len(mask) - 1])
    return spans


def _split_at_valleys(spans, smooth, ch):
    """Split a run where two lines touch (exponents, descenders) at a deep valley."""
    out = []
    min_part = max(4, int(ch))
    for a, b in spans:
        stack = [(a, b)]
        while stack:
            s0, s1 = stack.pop()
            if s1 - s0 + 1 < 2 * min_part + 1:
                out.append([s0, s1])
                continue
            seg = smooth[s0:s1 + 1]
            peak = seg.max()
            best, best_i = None, None
            for i in range(min_part, len(seg) - min_part):
                left = seg[:i].max()
                right = seg[i + 1:].max()
                # Both sides must look like real lines, not a row of exponents.
                if min(left, right) < 0.4 * peak:
                    continue
                depth = seg[i] / max(min(left, right), 1e-6)
                if depth < 0.18 and (best is None or depth < best):
                    best, best_i = depth, i
            if best_i is None:
                out.append([s0, s1])
            else:
                stack.append((s0 + best_i + 1, s1))
                stack.append((s0, s0 + best_i))
    return sorted(out)


def _merge_spans(spans, prof, ch):
    """Merge fraction parts, exponents and tiny fragments into their lines."""
    if not spans:
        return spans
    changed = True
    while changed and len(spans) > 1:
        changed = False
        heights = [b - a + 1 for a, b in spans]
        med = float(np.median(heights))
        for i in range(len(spans) - 1):
            a0, b0 = spans[i]
            a1, b1 = spans[i + 1]
            gap = a1 - b0 - 1
            h0, h1 = b0 - a0 + 1, b1 - a1 + 1
            # Fraction parts sit very close together; a thin span (a fraction bar,
            # a row of exponents, a dot) belongs to its neighbour. Ordinary lines,
            # even tightly spaced ones, are separated by a clear gap.
            small = min(h0, h1) < 0.3 * med
            if gap < 0.25 * med or (small and gap < 0.6 * med):
                spans[i] = [a0, b1]
                del spans[i + 1]
                changed = True
                break
    return spans


def _cluster_components(ink_region: np.ndarray, ch: float, y_offset: int):
    """Fallback: group connected components by vertical center."""
    n, labels, stats, cents = cv2.connectedComponentsWithStats(ink_region, connectivity=8)
    comps = [(cents[i][1], stats[i]) for i in range(1, n) if stats[i][cv2.CC_STAT_AREA] >= 6]
    if not comps:
        return []
    big = sorted([c for c in comps if c[1][cv2.CC_STAT_HEIGHT] >= 0.5 * ch], key=lambda c: c[0])
    clusters: list = []
    for cy, st in big:
        for cl in clusters:
            if abs(cy - cl["cy"]) < 0.7 * ch:
                cl["items"].append((cy, st))
                cl["cy"] = float(np.mean([c[0] for c in cl["items"]]))
                break
        else:
            clusters.append({"cy": cy, "items": [(cy, st)]})
    if not clusters:
        return []
    for cy, st in comps:
        if st[cv2.CC_STAT_HEIGHT] < 0.5 * ch:
            nearest = min(clusters, key=lambda cl: abs(cl["cy"] - cy))
            nearest["items"].append((cy, st))
    spans = []
    for cl in clusters:
        top = min(st[1] for _, st in cl["items"])
        bot = max(st[1] + st[3] for _, st in cl["items"])
        spans.append([top + y_offset, bot + y_offset - 1])
    spans.sort()
    merged = []
    for s in spans:
        if merged and s[0] <= merged[-1][1] - 0.5 * min(s[1] - s[0], merged[-1][1] - merged[-1][0]):
            merged[-1][1] = max(merged[-1][1], s[1])
        else:
            merged.append(list(s))
    return merged


def split_lines(ink: np.ndarray, stats) -> list:
    """Line boxes (left, top, right, bottom) in the coordinates of ``ink``."""
    h, w = ink.shape
    if not ink.any():
        return []
    ch = _char_height(stats)
    prof = (ink > 0).sum(axis=1).astype(float)
    k = max(3, int(ch // 6) | 1)
    smooth = np.convolve(prof, np.ones(k) / k, "same")
    thresh = max(1.5, 0.02 * float(np.percentile(smooth[smooth > 0], 95))) if (smooth > 0).any() else 1.5
    spans = _runs(smooth > thresh)
    total = prof.sum()
    spans = [s for s in spans if prof[s[0]:s[1] + 1].sum() > 0.002 * total]
    spans = _merge_spans(spans, prof, ch)
    spans = _split_at_valleys(spans, smooth, ch)

    # Very tall spans mean slanted or touching lines: split them by components.
    est_line = 1.7 * ch
    final = []
    for a, b in spans:
        if b - a + 1 > 2.6 * est_line:
            sub = _cluster_components(ink[a:b + 1], ch, a)
            final.extend(sub if len(sub) > 1 else [[a, b]])
        else:
            final.append([a, b])

    pad = max(4, int(0.18 * ch))
    boxes = []
    for a, b in final:
        rows = ink[a:b + 1]
        cols = np.where(rows.any(axis=0))[0]
        if len(cols) == 0:
            continue
        mass = (rows > 0).sum()
        if mass < max(30, 0.15 * ch * ch):
            continue  # a stray mark
        # A line of writing always has some character-height marks; leftover
        # fragments of ruled lines and smudges don't.
        n_cc, _lab, cc_stats, _c = cv2.connectedComponentsWithStats(rows, connectivity=8)
        if n_cc <= 1 or max(cc_stats[i][cv2.CC_STAT_HEIGHT] for i in range(1, n_cc)) < 0.45 * ch:
            continue
        if cols[-1] - cols[0] < 0.5 * ch:
            continue  # a sliver (e.g. a piece of a margin line), too narrow to be math
        left, right = int(cols[0]), int(cols[-1])
        boxes.append((max(0, left - pad), max(0, a - pad), min(w - 1, right + pad), min(h - 1, b + pad)))
    return boxes[:MAX_LINES]


def group_problems(boxes) -> list:
    """Whole-page mode: start a new problem at unusually large vertical gaps."""
    if len(boxes) < 2:
        return [0] * len(boxes)
    gaps = [boxes[i + 1][1] - boxes[i][3] for i in range(len(boxes) - 1)]
    heights = [b[3] - b[1] for b in boxes]
    med_gap = float(np.median(gaps))
    med_h = float(np.median(heights))
    limit = max(2.2 * max(med_gap, 1), 1.2 * med_h)
    groups, g = [0], 0
    for gap in gaps:
        if gap > limit:
            g += 1
        groups.append(g)
    return groups


# --------------------------------------------------------------------------
# outputs
# --------------------------------------------------------------------------

def _encode_png(gray: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", gray)
    if not ok:
        raise ImageError("Couldn't encode a crop")
    return buf.tobytes()


def _thumb_data_url(gray: np.ndarray) -> str:
    h, w = gray.shape
    if h > THUMB_HEIGHT:
        s = THUMB_HEIGHT / h
        gray = cv2.resize(gray, (max(1, int(w * s)), THUMB_HEIGHT), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", gray, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def _transcription_crop(gray: np.ndarray) -> np.ndarray:
    h, w = gray.shape
    if w > CROP_MAX_WIDTH:
        s = CROP_MAX_WIDTH / w
        gray = cv2.resize(gray, (CROP_MAX_WIDTH, max(1, int(h * s))), interpolation=cv2.INTER_AREA)
    if gray.shape[0] < 32:
        s = 32 / gray.shape[0]
        gray = cv2.resize(gray, (max(1, int(gray.shape[1] * s)), 32), interpolation=cv2.INTER_CUBIC)
    return gray


def process_image(data: bytes, mode: str = "problem") -> VisionResult:
    """Run stages 1 and 2. ``mode`` is "problem", "page" or "line"."""
    rgb_full = load_image(data)
    H0, W0 = rgb_full.shape[:2]
    s = min(1.0, MAX_WORK_SIDE / max(H0, W0))
    rgb = cv2.resize(rgb_full, (int(W0 * s), int(H0 * s)), interpolation=cv2.INTER_AREA) if s < 1 else rgb_full

    result = VisionResult(width=W0, height=H0)
    quad = find_paper(rgb)
    if quad is not None:
        warped, M = warp_paper(rgb, quad)
        result.paper_found = True
    else:
        h, w = rgb.shape[:2]
        f = min(1.0, WARP_MAX_SIDE / max(h, w))
        M = np.array([[f, 0, 0], [0, f, 0], [0, 0, 1]], dtype=np.float64)
        warped = cv2.resize(rgb, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA) if f < 1 else rgb
    Minv = np.linalg.inv(M)

    gray, ink = enhance(warped)
    pw, ph = (warped.shape[1], warped.shape[0]) if quad is not None else page_extent(gray)
    # A drawing pad (line mode, no paper) has no margin line; tall strokes there are writing.
    ink, removed = remove_ruled_lines(ink, pw, ph, vertical=not (mode == "line" and quad is None))
    ink, stats = remove_noise(ink)

    # The crop the model sees: enhanced grayscale with ruled lines painted out.
    display = gray.copy()
    if removed.any():
        bg = cv2.medianBlur(gray, 21)
        display[removed > 0] = np.maximum(bg[removed > 0], 200)

    boxes = split_lines(ink, stats)
    if mode == "line" and boxes:
        boxes = [(min(b[0] for b in boxes), min(b[1] for b in boxes),
                  max(b[2] for b in boxes), max(b[3] for b in boxes))]
    if not boxes:
        result.warnings.append("no_lines")
        return result
    groups = group_problems(boxes) if mode == "page" else [0] * len(boxes)

    for i, (l, t, r, b) in enumerate(boxes):
        corners = np.array([[[l, t], [r, t], [r, b], [l, b]]], dtype=np.float64)
        orig = cv2.perspectiveTransform(corners, Minv)[0] / s
        orig[:, 0] = np.clip(orig[:, 0], 0, W0 - 1)
        orig[:, 1] = np.clip(orig[:, 1], 0, H0 - 1)
        box = [int(orig[:, 0].min()), int(orig[:, 1].min()), int(orig[:, 0].max()), int(orig[:, 1].max())]
        crop = display[t:b + 1, l:r + 1]
        result.lines.append(LineBox(
            index=i, box=box, quad=[[int(round(px)), int(round(py))] for px, py in orig],
            crop_png=_encode_png(_transcription_crop(crop)), thumb=_thumb_data_url(crop),
            problem=groups[i], warped_box=(l, t, r, b)))
    return result
