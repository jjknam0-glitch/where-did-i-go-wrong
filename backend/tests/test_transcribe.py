"""Transcription: provider adapters (against a local fake API server), read-twice
reconciliation and lookalike flagging."""

import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.transcribe import providers as P
from app.transcribe.reader import read_lines
from app.transcribe.reconcile import finalize, flag_lookalikes, readings_agree


class FakeAPI(BaseHTTPRequestHandler):
    requests = []
    answers = {}  # model -> list of reading dicts (consumed in order) or a single dict

    def log_message(self, *a):
        pass

    def _answer_for(self, model):
        a = FakeAPI.answers.get(model, {"type": "equation", "math": "x = 1", "latex": "x=1"})
        if isinstance(a, list):
            return a.pop(0) if a else {"type": "equation", "math": "x = 1", "latex": "x=1"}
        return a

    def do_POST(self):
        length = int(self.headers.get("content-length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        FakeAPI.requests.append((self.path, body, dict(self.headers)))
        if "/v1/messages" in self.path:
            model = body["model"]
            text = json.dumps(self._answer_for(model))
            out = {"id": "msg_1", "type": "message", "role": "assistant", "model": model,
                   "content": [{"type": "text", "text": text}], "stop_reason": "end_turn",
                   "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 10}}
        elif "/chat/completions" in self.path:
            model = body["model"]
            out = {"id": "c1", "object": "chat.completion", "created": 1, "model": model,
                   "choices": [{"index": 0, "finish_reason": "stop",
                                "message": {"role": "assistant", "content": json.dumps(self._answer_for(model))}}]}
        elif ":generateContent" in self.path:
            model = self.path.split("/models/")[1].split(":")[0]
            out = {"candidates": [{"index": 0, "finishReason": "STOP",
                                   "content": {"role": "model",
                                               "parts": [{"text": json.dumps(self._answer_for(model))}]}}]}
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture()
def fake_server(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeAPI)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    FakeAPI.requests = []
    FakeAPI.answers = {}
    for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY",
              "READ_MODELS", "TIEBREAK_MODEL", "TRANSCRIBE_PROVIDER", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", url)
    monkeypatch.setenv("OPENAI_BASE_URL", url + "/v1")
    monkeypatch.setenv("GEMINI_BASE_URL", url)
    # fresh clients pick up the env
    for p in P.PROVIDERS.values():
        p._client = None
    yield url
    server.shutdown()
    for p in P.PROVIDERS.values():
        p._client = None


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


def _sync(fn, *a):
    async def inner():
        return fn(*a)
    return inner()


def test_no_provider_means_no_transcription(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    assert P.resolve_models() == ([], None)
    assert asyncio.run(read_lines([PNG], _sync)) is None


def test_anthropic_request_shape(fake_server, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    reads, tb = P.resolve_models()
    assert [m for _, m in reads] == ["claude-haiku-5-5", "claude-sonnet-5-5"]
    assert tb[1] == "claude-opus-5-5"
    FakeAPI.answers = {"claude-haiku-5-5": {"type": "equation", "math": "2x + 3 = 7", "latex": "2x+3=7"}}
    out = asyncio.run(P.PROVIDERS["anthropic"].transcribe(PNG, "claude-haiku-5-5"))
    assert out == {"type": "equation", "math": "2x + 3 = 7", "latex": "2x+3=7"}
    path, body, headers = FakeAPI.requests[-1]
    assert "/v1/messages" in path
    content = body["messages"][0]["content"]
    assert content[0]["type"] == "image" and content[0]["source"]["media_type"] == "image/png"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert "character for character" in body["system"]
    assert "temperature" not in body


def test_anthropic_strong_models_request_fallbacks(fake_server, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    asyncio.run(P.PROVIDERS["anthropic"].transcribe(PNG, "claude-sonnet-5-5"))
    path, body, headers = FakeAPI.requests[-1]
    assert body.get("fallbacks") == "default"
    assert "server-side-fallback-2026-07-01" in headers.get("anthropic-beta", "")


def test_openai_request_shape(fake_server, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("TRANSCRIBE_PROVIDER", "openai")
    FakeAPI.answers = {"gpt-4.1-mini": {"type": "note", "math": "divide by 2", "latex": "\\text{divide by 2}"}}
    out = asyncio.run(P.PROVIDERS["openai"].transcribe(PNG, "gpt-4.1-mini"))
    assert out["type"] == "note"
    path, body, _ = FakeAPI.requests[-1]
    assert body["temperature"] == 0
    assert body["response_format"]["type"] == "json_schema"
    assert body["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_gemini_request_shape(fake_server, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    FakeAPI.answers = {"gemini-2.5-flash": {"type": "equation", "math": "x = 5", "latex": "x=5"}}
    out = asyncio.run(P.PROVIDERS["gemini"].transcribe(PNG, "gemini-2.5-flash"))
    assert out == {"type": "equation", "math": "x = 5", "latex": "x=5"}
    path, body, _ = FakeAPI.requests[-1]
    assert body["generationConfig"]["temperature"] == 0
    assert body["generationConfig"]["responseMimeType"] == "application/json"


def test_read_twice_with_tiebreak(fake_server, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    FakeAPI.answers = {
        "claude-haiku-5-5": [{"type": "equation", "math": "2x + 3 = 7", "latex": ""},
                             {"type": "equation", "math": "x^2 - 4 = 0", "latex": ""}],
        "claude-sonnet-5-5": [{"type": "equation", "math": "2*x+3=7", "latex": ""},
                              {"type": "equation", "math": "x^2 + 4 = 0", "latex": ""}],
        "claude-opus-5-5": [{"type": "equation", "math": "x^2 - 4 = 0", "latex": ""}],
    }
    # Gather order is per-line, per-read; answers are consumed in request order per model.
    lines = asyncio.run(read_lines([PNG, PNG], _sync))
    assert lines[0]["confidence"] == "high"
    assert lines[1]["confidence"] == "low"
    assert set(lines[1]["alternatives"]) == {"x^2 - 4 = 0", "x^2 + 4 = 0"}
    assert lines[1]["math"] == "x^2 - 4 = 0"  # the read the strong model agreed with
    models = [b["model"] for p, b, h in FakeAPI.requests]
    assert models.count("claude-opus-5-5") == 1


def test_cross_provider_reads(fake_server, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("READ_MODELS", "anthropic:claude-haiku-5-5, gemini:gemini-2.5-flash")
    monkeypatch.setenv("TIEBREAK_MODEL", "none")
    reads, tb = P.resolve_models()
    assert [(p.name, m) for p, m in reads] == [("anthropic", "claude-haiku-5-5"), ("gemini", "gemini-2.5-flash")]
    assert tb is None


# --------------------------------------------------------------------------
# reconciliation
# --------------------------------------------------------------------------

def r(math, t="equation"):
    return {"type": t, "math": math, "latex": math}


def test_readings_agree_on_meaning():
    assert readings_agree(r("x*2 = 6"), r("2x = 6"))
    assert readings_agree(r("2(x+1)"), r("2 (x + 1)"))
    assert not readings_agree(r("x = 5"), r("x = s"))
    assert not readings_agree(r("x^2 - 4"), r("x^2 + 4"))
    assert not readings_agree(r("x = 5"), r("5 = x"))
    assert readings_agree(r("divide by 2", "note"), r("Divide by 2", "note"))
    assert not readings_agree(r("x = 1"), None)


def test_finalize_marks_parse_failures_low():
    out = finalize([[r("2x = (4"), r("2x = (4")]])
    assert out[0]["confidence"] == "low" and out[0].get("parse_error")


def test_finalize_unreadable_line():
    out = finalize([[None, None]])
    assert out[0]["unreadable"] and out[0]["math"] == ""


def test_lookalike_flagging():
    lines = [{"type": "equation", "math": "2x + 3 = 7", "latex": "", "confidence": "high", "alternatives": []},
             {"type": "equation", "math": "2x = 4", "latex": "", "confidence": "high", "alternatives": []},
             {"type": "equation", "math": "x = s", "latex": "", "confidence": "high", "alternatives": []}]
    flag_lookalikes(lines)
    assert lines[2]["confidence"] == "low"
    assert lines[2]["alternatives"] == ["x = s", "x = 5"]
    assert lines[0]["confidence"] == "high"


def test_lookalike_ignores_real_second_variable():
    lines = [{"type": "equation", "math": "x + y = 5; x - y = 1", "latex": "", "confidence": "high"},
             {"type": "equation", "math": "2x = 6", "latex": "", "confidence": "high"},
             {"type": "equation", "math": "y = 2", "latex": "", "confidence": "high"}]
    flag_lookalikes(lines)
    assert all(l["confidence"] == "high" for l in lines)


# --------------------------------------------------------------------------
# AI-phrased hints are verified by the engine
# --------------------------------------------------------------------------

def test_ai_hints_verified_and_used(fake_server, monkeypatch):
    from app.explain_ai import phrase_hints
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    FakeAPI.answers = {"claude-haiku-5-5": {
        "hint2": "When the $+3$ crossed the equals sign, its sign should have changed.",
        "hint3": "Subtracting 3 from both sides gives $2x = 4$, since $7 - 3 = 4$."}}
    payload = {"previous": "2x + 3 = 7", "student": "2x = 10", "corrected": "2 x = 4",
               "hints": ["h1", "h2", "h3"], "variable": "x"}
    out = asyncio.run(phrase_hints(payload, _sync))
    assert out["source"] == "ai"
    assert out["hints"][0] == "h1" and "$2x = 4$" in out["hints"][2]


def test_ai_hints_with_wrong_math_fall_back(fake_server, monkeypatch):
    from app.explain_ai import phrase_hints
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    bad = {"hint2": "Check the sign.", "hint3": "The line should be $2x = 5$ because $7 - 3 = 5$."}
    FakeAPI.answers = {"claude-haiku-5-5": [dict(bad), dict(bad)]}
    payload = {"previous": "2x + 3 = 7", "student": "2x = 10", "corrected": "2 x = 4",
               "hints": ["h1", "h2", "h3"], "variable": "x"}
    out = asyncio.run(phrase_hints(payload, _sync))
    assert out == {"hints": ["h1", "h2", "h3"], "source": "template"}
