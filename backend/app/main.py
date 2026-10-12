"""Where Did I Go Wrong? - API.

Three core endpoints (spec): read a photo, check confirmed lines, check a
single fixed step. Splitting reading from checking lets the student confirm
the transcription in between. Everything else supports the learning
features: practice, lessons, parent sharing, optional accounts.
"""

from __future__ import annotations

import base64
import contextlib
import datetime as dt
import hashlib
import json
import logging
import os

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, storage, tasks, worker
from .cache import RateLimiter, TTLCache
from .engine import checker, lessons, practice
from .explain_ai import ai_hints_available, phrase_hints
from .transcribe.providers import resolve_models
from .transcribe.reader import read_lines
from .vision.pipeline import ImageError

log = logging.getLogger("wdigw")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

VERSION = "1.0.0"
read_cache = TTLCache(config.CACHE_SIZE, config.CACHE_TTL)
limiter = RateLimiter()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, worker.warm_up)
    yield
    worker.shutdown()


app = FastAPI(title="Where Did I Go Wrong? API", version=VERSION, lifespan=lifespan,
              docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"],
                   allow_headers=["*"], allow_credentials=False)


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) > config.MAX_UPLOAD_BYTES + 1024 * 1024:
                return JSONResponse({"detail": "Upload is too large"}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "Bad Content-Length"}, status_code=400)
    return await call_next(request)


@app.exception_handler(storage.StorageError)
async def storage_error(request: Request, exc: storage.StorageError):
    return JSONResponse({"detail": str(exc)}, status_code=exc.status)


@app.exception_handler(worker.EngineBusy)
async def engine_busy(request: Request, exc: worker.EngineBusy):
    return JSONResponse({"detail": "The math engine took too long. Please try again."}, status_code=503)


def client_id(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str, limit: int, window: float):
    def dep(request: Request):
        if not limiter.allow(bucket, client_id(request), limit, window):
            raise HTTPException(429, "Too many requests. Please wait a few minutes and try again.")
    return dep


# --------------------------------------------------------------------------
# models
# --------------------------------------------------------------------------

class LineIn(BaseModel):
    index: int = Field(ge=0, le=1000)
    math: str = Field(default="", max_length=300)
    type: str = Field(default="equation", pattern="^(equation|expression|note)$")


class CheckIn(BaseModel):
    lines: list[LineIn] = Field(min_length=1, max_length=config.MAX_LINES)
    acknowledge_sanity: bool = False


class FixIn(BaseModel):
    lines: list[LineIn] = Field(min_length=1, max_length=config.MAX_LINES)
    index: int
    math: str = Field(min_length=1, max_length=300)


class ParseIn(BaseModel):
    lines: list[str] = Field(max_length=config.MAX_LINES)


class AnswerIn(BaseModel):
    lines: list[LineIn] = Field(min_length=1, max_length=config.MAX_LINES)


class ExplainIn(BaseModel):
    previous: str = Field(default="", max_length=300)
    student: str = Field(default="", max_length=300)
    corrected: str | None = Field(default=None, max_length=400)
    error_type: str | None = Field(default=None, max_length=40)
    hints: list[str] = Field(default_factory=list, max_length=3)
    variable: str = Field(default="x", max_length=10)


class ProblemIn(BaseModel):
    kind: str = Field(max_length=20)
    math: str = Field(max_length=300)


class PracticeCheckIn(BaseModel):
    problem: ProblemIn
    answer: str = Field(max_length=200)


class DrillIn(BaseModel):
    skills: list[str] = Field(min_length=1, max_length=5)
    count: int = Field(default=8, ge=1, le=15)
    level: int = Field(default=2, ge=1, le=3)
    seed: int | None = None


class SignupIn(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=200)
    birth_date: str = Field(max_length=10)
    corrections_opt_in: bool = False


class LoginIn(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=200)


class SettingsIn(BaseModel):
    plan: str | None = None
    corrections_opt_in: bool | None = None


class SyncIn(BaseModel):
    data: dict


class ShareIn(BaseModel):
    snapshot: dict


class CorrectionIn(BaseModel):
    original: str = Field(max_length=300)
    corrected: str = Field(max_length=300)
    type: str | None = Field(default=None, max_length=20)


# --------------------------------------------------------------------------
# status
# --------------------------------------------------------------------------

def _samples() -> list[dict]:
    path = os.path.join(config.SAMPLES_DIR, "samples.json")
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []


@app.get("/api/health")
def health():
    reads, tiebreak = resolve_models()
    return {
        "ok": True,
        "version": VERSION,
        "transcription": bool(reads),
        "read_models": [f"{p.name}:{m}" for p, m in reads],
        "tiebreak_model": f"{tiebreak[0].name}:{tiebreak[1]}" if tiebreak else None,
        "ai_hints": config.AI_HINTS and ai_hints_available(),
    }


@app.get("/api/samples")
def samples():
    return [{"id": s["id"], "title": s["title"], "description": s["description"],
             "page": s.get("page", False), "image": f"/api/samples/{s['id']}.jpg"} for s in _samples()]


@app.get("/api/samples/{sample_id}.jpg")
def sample_image(sample_id: str):
    s = next((s for s in _samples() if s["id"] == sample_id), None)
    if s is None:
        raise HTTPException(404, "No such sample")
    return FileResponse(os.path.join(config.SAMPLES_DIR, s["file"]), media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})


# --------------------------------------------------------------------------
# POST /read
# --------------------------------------------------------------------------

def _manual_lines(vision_lines):
    return [{"type": "equation", "math": "", "latex": "", "confidence": "low", "alternatives": [],
             "needs_typing": True} for _ in vision_lines]


@app.post("/api/read", dependencies=[Depends(rate_limit("read", config.RATE_READ, 600))])
async def read(image: UploadFile | None = File(default=None), mode: str = Form(default="problem"),
               sample: str | None = Form(default=None)):
    if mode not in ("problem", "page", "line"):
        raise HTTPException(400, "mode must be problem, page or line")
    truth = None
    if sample:
        s = next((s for s in _samples() if s["id"] == sample), None)
        if s is None:
            raise HTTPException(404, "No such sample")
        with open(os.path.join(config.SAMPLES_DIR, s["file"]), "rb") as f:
            data = f.read()
        truth = s["lines"]
        if s.get("page") and mode == "problem":
            mode = "page"
    else:
        if image is None:
            raise HTTPException(400, "Attach a photo in the 'image' field")
        data = await image.read(config.MAX_UPLOAD_BYTES + 1)
        if len(data) > config.MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Photo is too large")
        if not data:
            raise HTTPException(400, "The photo is empty")

    key = hashlib.sha256(data + mode.encode() + (b"sample" if truth else b"")).hexdigest()
    cached = read_cache.get(key)
    if cached is not None:
        return cached

    try:
        vision = await worker.run(tasks.vision_to_dict, data, mode, timeout=60)
    except ImageError as exc:
        raise HTTPException(400, str(exc))
    del data  # the photo is not kept

    vlines = vision["lines"]
    source = "ai"
    warnings = list(vision["warnings"])
    if not vlines:
        transcribed = []
    elif truth is not None and len(truth) == len(vlines):
        source = "sample"
        transcribed = []
        for t in truth:
            alts = t.get("alternatives") or []
            transcribed.append({"type": t.get("type", "equation"), "math": t["math"], "latex": t["latex"],
                                "confidence": "low" if alts else "high", "alternatives": alts})
    else:
        crops = [base64.b64decode(l["png"]) for l in vlines]
        result = await read_lines(crops, lambda fn, *a: worker.run(fn, *a, timeout=60))
        if result is None:
            source = "manual"
            transcribed = _manual_lines(vlines)
            warnings.append("no_transcription")
        else:
            transcribed = result

    lines = []
    for v, t in zip(vlines, transcribed):
        line = {"index": v["index"], "box": v["box"], "quad": v["quad"], "crop": v["crop"],
                "problem": v["problem"], **t}
        lines.append(line)
    response = {
        "problem_id": key[:12],
        "width": vision["width"], "height": vision["height"],
        "paper_found": vision["paper_found"],
        "mode": mode, "source": source, "warnings": warnings,
        "lines": lines,
    }
    if source != "manual" or not lines:
        read_cache.set(key, response)
    return response


# --------------------------------------------------------------------------
# POST /check, /fix, /parse, /answer, /explain
# --------------------------------------------------------------------------

def _lines_payload(lines: list[LineIn]) -> list[dict]:
    seen = set()
    out = []
    for l in lines:
        if l.index in seen:
            raise HTTPException(400, "Line indexes must be unique")
        seen.add(l.index)
        out.append({"index": l.index, "math": l.math, "type": l.type})
    return out


@app.post("/api/check", dependencies=[Depends(rate_limit("check", config.RATE_CHECK, 600))])
async def check(body: CheckIn):
    return await worker.run(checker.check_lines, _lines_payload(body.lines),
                            acknowledge_sanity=body.acknowledge_sanity)


@app.post("/api/fix", dependencies=[Depends(rate_limit("check", config.RATE_CHECK, 600))])
async def fix(body: FixIn):
    lines = _lines_payload(body.lines)
    if body.index not in {l["index"] for l in lines}:
        raise HTTPException(400, "No line with that index")
    return await worker.run(checker.check_fix, lines, body.index, body.math)


@app.post("/api/parse", dependencies=[Depends(rate_limit("check", config.RATE_CHECK * 5, 600))])
async def parse(body: ParseIn):
    if any(len(t) > 300 for t in body.lines):
        raise HTTPException(400, "Line is too long")
    return {"lines": await worker.run(tasks.parse_many, body.lines, timeout=20)}


@app.post("/api/answer", dependencies=[Depends(rate_limit("check", config.RATE_CHECK, 600))])
async def answer(body: AnswerIn):
    return await worker.run(checker.final_answer, _lines_payload(body.lines))


@app.post("/api/explain", dependencies=[Depends(rate_limit("check", config.RATE_CHECK, 600))])
async def explain(body: ExplainIn):
    if not config.AI_HINTS:
        return {"hints": body.hints, "source": "template"}
    return await phrase_hints(body.model_dump(), lambda fn, *a: worker.run(fn, *a, timeout=30))


# --------------------------------------------------------------------------
# practice, test prep, lessons
# --------------------------------------------------------------------------

@app.get("/api/practice")
async def get_practice(skill: str = "general", count: int = 3, level: int = 1, seed: int | None = None):
    count = max(1, min(10, count))
    level = max(1, min(3, level))
    return {"skill": skill, "title": practice.SKILL_INFO.get(skill, ("Practice", ""))[0],
            "problems": await worker.run(practice.make_problems, skill, count, level, seed)}


@app.get("/api/practice/harder")
async def harder(topic: str = "linear", level: int = 2, seed: int | None = None):
    skill = practice.TOPIC_TO_SKILL.get(topic, "linear")
    probs = await worker.run(practice.make_problems, skill, 1, max(1, min(3, level)), seed)
    return {"problems": probs}


@app.post("/api/practice/drill")
async def drill(body: DrillIn):
    per = max(1, -(-body.count // len(body.skills)))
    problems = []
    for i, skill in enumerate(body.skills):
        seed = None if body.seed is None else body.seed + i
        problems += await worker.run(practice.make_problems, skill, per, body.level, seed)
    import random
    rng = random.Random(body.seed)
    rng.shuffle(problems)
    return {"problems": problems[:body.count]}


@app.post("/api/practice/check")
async def practice_check(body: PracticeCheckIn):
    return await worker.run(practice.check_answer, body.problem.model_dump(), body.answer, timeout=30)


@app.post("/api/practice/answer")
async def practice_answer(body: ProblemIn):
    return await worker.run(practice.compute_answer, body.model_dump(), timeout=30)


@app.get("/api/lessons")
def get_lessons():
    return lessons.list_lessons()


@app.get("/api/lessons/{lesson_id}")
async def get_lesson(lesson_id: str):
    if lesson_id not in lessons.LESSONS:
        raise HTTPException(404, "No such lesson")
    return await worker.run(lessons.get_lesson, lesson_id, timeout=30)


# --------------------------------------------------------------------------
# accounts (optional, 13+) and sync
# --------------------------------------------------------------------------

def _age(birth: dt.date, today: dt.date) -> int:
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def current_user(authorization: str | None = Header(default=None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = storage.user_for_token(token)
    if user is None:
        raise HTTPException(401, "Please sign in again")
    user["token"] = token
    return user


@app.post("/api/auth/signup", dependencies=[Depends(rate_limit("auth", config.RATE_AUTH, 600))])
def signup(body: SignupIn):
    try:
        birth = dt.date.fromisoformat(body.birth_date)
    except ValueError:
        raise HTTPException(400, "Enter your date of birth")
    today = dt.date.today()
    if birth > today or birth.year < 1900:
        raise HTTPException(400, "Enter a real date of birth")
    if _age(birth, today) < 13:
        # The birth date is never stored.
        raise HTTPException(403, "Accounts are for ages 13 and up. You can keep using the app without one — "
                                 "your progress stays on this device.")
    uid = storage.create_user(body.email, body.password, body.corrections_opt_in)
    token = storage.create_session(uid)
    return {"token": token, "user": storage.user_for_token(token)}


@app.post("/api/auth/login", dependencies=[Depends(rate_limit("auth", config.RATE_AUTH, 600))])
def login(body: LoginIn):
    uid = storage.verify_user(body.email, body.password)
    token = storage.create_session(uid)
    return {"token": token, "user": storage.user_for_token(token)}


@app.post("/api/auth/logout")
def logout(user: dict = Depends(current_user)):
    storage.delete_session(user["token"])
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)):
    return {k: v for k, v in user.items() if k != "token"}


@app.patch("/api/auth/me")
def update_me(body: SettingsIn, user: dict = Depends(current_user)):
    storage.update_user(user["id"], plan=body.plan, corrections_opt_in=body.corrections_opt_in)
    return {k: v for k, v in storage.user_for_token(user["token"]).items()}


@app.delete("/api/auth/me")
def delete_me(user: dict = Depends(current_user)):
    storage.delete_user(user["id"])
    return {"ok": True}


@app.get("/api/sync")
def get_sync(user: dict = Depends(current_user)):
    return storage.get_user_data(user["id"]) or {"data": None, "updated_at": None}


@app.put("/api/sync")
def put_sync(body: SyncIn, user: dict = Depends(current_user)):
    return {"updated_at": storage.put_user_data(user["id"], body.data)}


# --------------------------------------------------------------------------
# parent / tutor sharing
# --------------------------------------------------------------------------

@app.post("/api/share", dependencies=[Depends(rate_limit("share", config.RATE_SHARE, 3600))])
def create_share(body: ShareIn):
    share_id, secret = storage.create_share(body.snapshot)
    return {"id": share_id, "secret": secret}


@app.get("/api/share/{share_id}")
def read_share(share_id: str):
    s = storage.get_share(share_id)
    if s is None:
        raise HTTPException(404, "This link was turned off or doesn't exist")
    return s


@app.put("/api/share/{share_id}")
def update_share(share_id: str, body: ShareIn, x_share_secret: str = Header(default="")):
    storage.update_share(share_id, x_share_secret, body.snapshot)
    return {"ok": True}


@app.delete("/api/share/{share_id}")
def revoke_share(share_id: str, x_share_secret: str = Header(default="")):
    storage.delete_share(share_id, x_share_secret)
    return {"ok": True}


# --------------------------------------------------------------------------
# opt-in transcription corrections
# --------------------------------------------------------------------------

@app.post("/api/corrections", dependencies=[Depends(rate_limit("check", config.RATE_CHECK, 600))])
def corrections(body: CorrectionIn):
    storage.add_correction(body.original, body.corrected, body.type)
    return {"ok": True}


# --------------------------------------------------------------------------
# optional: serve the built frontend from the same origin
# --------------------------------------------------------------------------

if os.path.isdir(config.FRONTEND_DIST):
    assets = os.path.join(config.FRONTEND_DIST, "assets")
    if os.path.isdir(assets):
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        full = os.path.realpath(os.path.join(config.FRONTEND_DIST, path))
        root = os.path.realpath(config.FRONTEND_DIST)
        if path and full.startswith(root + os.sep) and os.path.isfile(full):
            return FileResponse(full)
        return FileResponse(os.path.join(config.FRONTEND_DIST, "index.html"))
