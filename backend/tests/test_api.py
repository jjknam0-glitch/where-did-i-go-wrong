"""API tests through the real worker pool."""

import io
import os
import tempfile

import pytest

os.environ.setdefault("ENGINE_WORKERS", "2")
_tmp = tempfile.mkdtemp()
os.environ["DATA_DIR"] = _tmp
os.environ["DB_PATH"] = os.path.join(_tmp, "test.db")
for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
    os.environ.pop(k, None)

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from app import config, storage  # noqa: E402
from app.main import app, limiter, read_cache  # noqa: E402

config.DB_PATH = os.environ["DB_PATH"]
storage.reset_for_tests()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset():
    limiter.reset()
    yield


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["transcription"] is False


def test_samples_list_and_image(client):
    r = client.get("/api/samples")
    assert r.status_code == 200
    samples = r.json()
    assert len(samples) >= 6
    img = client.get(samples[0]["image"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    assert client.get("/api/samples/nope.jpg").status_code == 404


def test_full_flow_on_sample(client):
    r = client.post("/api/read", data={"sample": "sign-error"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "sample"
    lines = body["lines"]
    assert [l["math"] for l in lines] == ["2x + 3 = 7", "2x = 10", "x = 5"]
    assert lines[2]["confidence"] == "low" and lines[2]["alternatives"]
    for l in lines:
        left, top, right, bottom = l["box"]
        assert 0 <= left < right <= body["width"] and 0 <= top < bottom <= body["height"]
        assert l["crop"].startswith("data:image/jpeg;base64,")

    payload = {"lines": [{"index": l["index"], "math": l["math"], "type": l["type"]} for l in lines]}
    chk = client.post("/api/check", json=payload).json()
    assert chk["first_error"] == 1
    assert chk["lines"][1]["error_type"] == "sign_error"
    assert len(chk["lines"][1]["hints"]) == 3

    fx = client.post("/api/fix", json={**payload, "index": 1, "math": "2x = 4"}).json()
    assert fx["valid"] is True
    assert fx["check"]["first_error"] == 2
    lines2 = [{"index": l["index"], "math": l["math"], "type": l.get("type", "equation")} for l in fx["lines"]]
    fx2 = client.post("/api/fix", json={"lines": lines2, "index": 2, "math": "x = 2"}).json()
    assert fx2["valid"] and fx2["check"]["all_correct"]


def test_read_is_cached(client):
    a = client.post("/api/read", data={"sample": "all-correct"}).json()
    b = client.post("/api/read", data={"sample": "all-correct"}).json()
    assert a == b


def test_page_mode_sample(client):
    body = client.post("/api/read", data={"sample": "homework-page"}).json()
    assert body["mode"] == "page"
    assert sorted({l["problem"] for l in body["lines"]}) == [0, 1]


def _photo_bytes():
    img = Image.new("RGB", (900, 600), (250, 250, 248))
    d = ImageDraw.Draw(img)
    for i, y in enumerate((120, 260, 400)):
        d.rectangle([100, y, 600 - i * 80, y + 40], fill=(20, 20, 30))
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


def test_read_upload_without_transcription_falls_back_to_typing(client):
    r = client.post("/api/read", files={"image": ("p.jpg", _photo_bytes(), "image/jpeg")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "manual"
    assert "no_transcription" in body["warnings"]
    assert len(body["lines"]) == 3
    assert all(l["needs_typing"] for l in body["lines"])


def test_read_rejects_non_images(client):
    r = client.post("/api/read", files={"image": ("x.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 400
    r = client.post("/api/read", data={"mode": "weird"}, files={"image": ("p.jpg", _photo_bytes(), "image/jpeg")})
    assert r.status_code == 400
    assert client.post("/api/read").status_code == 400


def test_check_validation(client):
    assert client.post("/api/check", json={"lines": []}).status_code == 422
    r = client.post("/api/check", json={"lines": [{"index": 0, "math": "x"}, {"index": 0, "math": "x"}]})
    assert r.status_code == 400
    r = client.post("/api/check", json={"lines": [{"index": 0, "math": "a" * 301}]})
    assert r.status_code == 422


def test_parse_and_answer(client):
    r = client.post("/api/parse", json={"lines": ["2x + 3 = 7", "2x = (4", ""]}).json()
    assert r["lines"][0]["latex"] == "2 x + 3 = 7"
    assert r["lines"][1]["error"]
    assert r["lines"][2] == {"latex": "", "error": None}
    a = client.post("/api/answer", json={"lines": [{"index": 0, "math": "2x + 3 = 7"}]}).json()
    assert a == {"available": True, "latex": "x = 2"}


def test_explain_without_ai_returns_template(client):
    hints = ["a", "b", "c"]
    r = client.post("/api/explain", json={"hints": hints, "previous": "2x+3=7", "student": "2x=10"}).json()
    assert r == {"hints": hints, "source": "template"}


def test_practice_endpoints(client):
    r = client.get("/api/practice", params={"skill": "sign_error", "count": 3, "seed": 5}).json()
    assert len(r["problems"]) == 3
    p = r["problems"][0]
    ans = client.post("/api/practice/answer", json={"kind": p["kind"], "math": p["math"]}).json()
    assert ans["available"]
    chk = client.post("/api/practice/check", json={"problem": {"kind": "solve", "math": "2x + 3 = 7"},
                                                   "answer": "x = 2"}).json()
    assert chk["correct"]
    d = client.post("/api/practice/drill", json={"skills": ["sign_error", "inequality_flip"], "count": 6,
                                                 "seed": 3}).json()
    assert len(d["problems"]) == 6
    h = client.get("/api/practice/harder", params={"topic": "quadratics"}).json()
    assert len(h["problems"]) == 1


def test_lessons(client):
    lst = client.get("/api/lessons").json()
    assert len(lst) >= 10
    one = client.get(f"/api/lessons/{lst[0]['id']}").json()
    assert one["example"][0]["status"] == "start"
    assert client.get("/api/lessons/nope").status_code == 404


def test_accounts_and_sync(client):
    r = client.post("/api/auth/signup", json={"email": "kid@example.com", "password": "longpassword",
                                              "birth_date": "2020-01-01"})
    assert r.status_code == 403
    r = client.post("/api/auth/signup", json={"email": "teen@example.com", "password": "longpassword",
                                              "birth_date": "2008-05-05"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=h).json()["email"] == "teen@example.com"
    assert client.post("/api/auth/signup", json={"email": "teen@example.com", "password": "longpassword",
                                                 "birth_date": "2008-05-05"}).status_code == 409
    assert client.post("/api/auth/login", json={"email": "teen@example.com", "password": "wrong-pass"}).status_code == 401
    assert client.get("/api/sync", headers=h).json()["data"] is None
    assert client.put("/api/sync", headers=h, json={"data": {"history": [1, 2]}}).status_code == 200
    assert client.get("/api/sync", headers=h).json()["data"] == {"history": [1, 2]}
    bad = client.put("/api/sync", headers=h, json={"data": {"photo": "data:image/png;base64,AAAA"}})
    assert bad.status_code == 400
    assert client.patch("/api/auth/me", headers=h, json={"plan": "plus"}).json()["plan"] == "plus"
    assert client.patch("/api/auth/me", headers=h, json={"plan": "gold"}).status_code == 400
    assert client.post("/api/auth/logout", headers=h).status_code == 200
    assert client.get("/api/auth/me", headers=h).status_code == 401
    tok2 = client.post("/api/auth/login", json={"email": "teen@example.com", "password": "longpassword"}).json()["token"]
    h2 = {"Authorization": f"Bearer {tok2}"}
    assert client.delete("/api/auth/me", headers=h2).status_code == 200
    assert client.post("/api/auth/login", json={"email": "teen@example.com", "password": "longpassword"}).status_code == 401


def test_share_links(client):
    snap = {"name": "Sam", "stats": {"checks": 4}}
    r = client.post("/api/share", json={"snapshot": snap}).json()
    sid, secret = r["id"], r["secret"]
    assert client.get(f"/api/share/{sid}").json()["snapshot"] == snap
    assert client.put(f"/api/share/{sid}", json={"snapshot": {"x": 1}}, headers={"X-Share-Secret": "nope"}).status_code == 403
    assert client.put(f"/api/share/{sid}", json={"snapshot": {"x": 1}}, headers={"X-Share-Secret": secret}).status_code == 200
    assert client.get(f"/api/share/{sid}").json()["snapshot"] == {"x": 1}
    assert client.post("/api/share", json={"snapshot": {"p": "data:image/jpeg;base64,xx"}}).status_code == 400
    assert client.delete(f"/api/share/{sid}", headers={"X-Share-Secret": secret}).status_code == 200
    assert client.get(f"/api/share/{sid}").status_code == 404


def test_rate_limit(client):
    old = config.RATE_AUTH
    try:
        codes = [client.post("/api/auth/login", json={"email": "a@b.co", "password": "x" * 8}).status_code
                 for _ in range(config.RATE_AUTH + 2)]
        assert 429 in codes
    finally:
        limiter.reset()


def test_corrections(client):
    assert client.post("/api/corrections", json={"original": "x = s", "corrected": "x = 5"}).json() == {"ok": True}
