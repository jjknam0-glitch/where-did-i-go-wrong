"""Evaluate the whole pipeline on a photographed test set (spec: "Testing and quality").

Each test case is a photo plus a JSON file with the true transcription of every
line and the index of the true error (or null):

    cases/
      problem-01.jpg
      problem-01.json   {"lines": [{"math": "2x + 3 = 7"}, ...], "error_line": 1}

Metrics:
  * line splitting       - photos split into the right number of lines
  * transcription        - lines read correctly before confirmation (needs an API key)
  * error localization   - circled line is the true error, on the confirmed (true) lines
  * false alarm rate     - correct lines wrongly flagged as errors (the most important number)
  * uncertain rate       - lines sent back to the user

Usage (from backend/):
  python -m eval.run_eval --cases path/to/cases
  python -m eval.run_eval --samples            # the bundled sample photos
  python -m eval.run_eval --synthetic 40       # randomized photos of the samples
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import io
import json
import os
import sys

from app.engine.checker import check_lines
from app.transcribe.providers import transcription_available
from app.transcribe.reader import read_lines
from app.transcribe.reconcile import readings_agree
from app.vision.pipeline import process_image

HERE = os.path.dirname(os.path.abspath(__file__))


def load_cases(args):
    cases = []
    if args.cases:
        for js in sorted(glob.glob(os.path.join(args.cases, "*.json"))):
            base = js[:-5]
            photo = next((base + ext for ext in (".jpg", ".jpeg", ".png", ".JPG", ".PNG") if os.path.exists(base + ext)), None)
            if not photo:
                print(f"skip {js}: no photo")
                continue
            with open(js) as f:
                truth = json.load(f)
            with open(photo, "rb") as f:
                cases.append((os.path.basename(base), f.read(), truth))
    samples_dir = os.path.join(HERE, "..", "app", "samples")
    with open(os.path.join(samples_dir, "samples.json")) as f:
        samples = [s for s in json.load(f) if not s.get("page")]
    if args.samples:
        for s in samples:
            with open(os.path.join(samples_dir, s["file"]), "rb") as f:
                cases.append((s["id"], f.read(), s))
    if args.synthetic:
        sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
        import make_samples
        by_id = {s["id"]: s for s in make_samples.SAMPLES}
        for k in range(args.synthetic):
            s = samples[k % len(samples)]
            img = make_samples.variant(by_id[s["id"]], 50_000 + k)
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=85)
            cases.append((f"{s['id']}-v{k}", buf.getvalue(), s))
    return cases


async def _sync(fn, *a):
    return fn(*a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases")
    ap.add_argument("--samples", action="store_true")
    ap.add_argument("--synthetic", type=int, default=0)
    args = ap.parse_args()
    cases = load_cases(args)
    if not cases:
        ap.error("no test cases (use --cases, --samples or --synthetic)")
    use_ai = transcription_available()

    split_ok = 0
    lines_total = lines_read_ok = 0
    located = with_error = 0
    correct_lines = false_alarms = 0
    uncertain = checked_lines = 0
    for name, photo, truth in cases:
        true_lines = [l for l in truth["lines"] if "gap" not in l]
        vision = process_image(photo)
        n_ok = len(vision.lines) == len(true_lines)
        split_ok += n_ok

        if use_ai and n_ok:
            readings = asyncio.run(read_lines([l.crop_png for l in vision.lines], _sync))
            for r, t in zip(readings, true_lines):
                lines_total += 1
                lines_read_ok += readings_agree({"type": t.get("type", "equation"), "math": t["math"], "latex": ""}, r)

        # Engine metrics on the confirmed (true) transcription.
        res = check_lines([{"index": i, "math": l["math"], "type": l.get("type", "equation")} for i, l in enumerate(true_lines)])
        err = truth.get("error_line")
        if err is not None:
            with_error += 1
            located += res["first_error"] == err
        for l in res["lines"]:
            if l["status"] in ("start", "skipped"):
                continue
            checked_lines += 1
            uncertain += l["status"] == "uncertain"
            is_true_error_or_after = err is not None and l["index"] >= err
            if not is_true_error_or_after:
                correct_lines += 1
                false_alarms += l["status"] == "error"
        mark = "ok " if n_ok else "BAD"
        print(f"{mark} {name:28s} lines {len(vision.lines)}/{len(true_lines)}  first_error {res['first_error']} (true {err})")

    print("\n=== Results ===")
    print(f"Line splitting:        {split_ok} of {len(cases)} photos")
    if use_ai:
        print(f"Transcription:         {lines_read_ok} of {lines_total} lines read correctly before confirmation")
    else:
        print("Transcription:         skipped (no API key configured)")
    print(f"Error localization:    {located} of {with_error} problems")
    print(f"False alarms:          {false_alarms} of {correct_lines} correct lines")
    print(f"Uncertain rate:        {uncertain} of {checked_lines} checked lines")
    print(f"\nFound the right error in {located} of {with_error} test problems, with {false_alarms} false alarm{'s' if false_alarms != 1 else ''}.")


if __name__ == "__main__":
    main()
