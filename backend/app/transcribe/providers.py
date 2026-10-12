"""Vision-model adapters. Only transcription uses an AI model.

Each provider turns one line crop into ``{"type", "math", "latex"}``. Providers
are swappable (spec: keep the transcription step swappable), and a read can
name its provider explicitly ("gemini:gemini-2.5-flash") so the two reads of
a line can come from two different companies' models.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You transcribe ONE line of a student's handwritten math from an image.

Transcribe exactly what is written, character for character, even if it is mathematically wrong. \
Do not fix, simplify, complete or reorder anything. If the student made a mistake, keep the mistake.

Return JSON with:
- "type": "equation" (has =, <, >, <= or >=), "expression" (math with no relation) or "note" (words such as "divide both sides by 2").
- "math": the line in plain calculator syntax for a computer algebra system:
  * ^ for powers, * or implicit multiplication (2x, 3(x+1)), / for fractions with parentheses: (x+1)/2
  * sqrt(), abs(), ln(), log(), sin(), cos(), tan(), e^x, pi
  * derivatives: f'(x) = ..., dy/dx = ..., or d/dx(...)
  * integrals: ∫ ... dx  (definite: ∫_a^b ... dx)
  * limits: lim_(x->a) ...
  * several answers: x = 2 or x = -3; a system of equations on one line: x + y = 5; x - y = 1
  * if the line starts with "=", keep the leading "="
  * for notes, put the words in "math"
- "latex": the same line as LaTeX, for display.

If part of the line is unreadable, give your best reading of exactly what is visible."""

USER_PROMPT = "Transcribe this line exactly as written."

SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["equation", "expression", "note"]},
        "math": {"type": "string"},
        "latex": {"type": "string"},
    },
    "required": ["type", "math", "latex"],
    "additionalProperties": False,
}

DEFAULT_MODELS = {
    "anthropic": {"reads": ["claude-haiku-5-5", "claude-sonnet-5-5"], "tiebreak": "claude-opus-5-5"},
    "gemini": {"reads": ["gemini-2.5-flash", "gemini-2.5-flash-lite"], "tiebreak": "gemini-2.5-pro"},
    "openai": {"reads": ["gpt-4.1-mini", "gpt-4o-mini"], "tiebreak": "gpt-4.1"},
}

KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}


def parse_reading(text: str | None) -> dict | None:
    """Validate a model's JSON answer."""
    if not text:
        return None
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.S)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    t = data.get("type")
    math = data.get("math")
    latex = data.get("latex")
    if t not in ("equation", "expression", "note") or not isinstance(math, str):
        return None
    if not isinstance(latex, str):
        latex = math
    return {"type": t, "math": math.strip()[:300], "latex": latex.strip()[:400]}


class Provider:
    name = "base"

    def available(self) -> bool:
        raise NotImplementedError

    async def transcribe(self, png: bytes, model: str) -> dict | None:
        raise NotImplementedError


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self):
        self._client = None

    def available(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))

    def client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(timeout=45.0, max_retries=2)
        return self._client

    async def transcribe(self, png: bytes, model: str) -> dict | None:
        import anthropic
        b64 = base64.standard_b64encode(png).decode("ascii")
        params = dict(
            model=model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                    {"type": "text", "text": USER_PROMPT},
                ],
            }],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        )
        client = self.client()
        try:
            if _supports_fallbacks(model):
                try:
                    resp = await client.beta.messages.create(
                        **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
                except anthropic.BadRequestError:
                    resp = await client.messages.create(**params)
            else:
                resp = await client.messages.create(**params)
        except anthropic.RateLimitError:
            log.warning("anthropic rate limited")
            return None
        except anthropic.APIStatusError as exc:
            log.warning("anthropic error %s", exc.status_code)
            return None
        except anthropic.APIConnectionError:
            log.warning("anthropic connection error")
            return None
        if getattr(resp, "stop_reason", None) == "refusal":
            return None
        text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), None)
        return parse_reading(text)


async def _anthropic_complete(self, system: str, user: str, model: str, schema: dict) -> dict | None:
    import anthropic
    params = dict(model=model, max_tokens=2048, system=system,
                  messages=[{"role": "user", "content": user}],
                  output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}})
    client = self.client()
    try:
        if _supports_fallbacks(model):
            try:
                resp = await client.beta.messages.create(
                    **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
            except anthropic.BadRequestError:
                resp = await client.messages.create(**params)
        else:
            resp = await client.messages.create(**params)
    except (anthropic.APIStatusError, anthropic.APIConnectionError):
        return None
    if getattr(resp, "stop_reason", None) == "refusal":
        return None
    text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), None)
    return _loads(text)


AnthropicProvider.complete_json = _anthropic_complete


def _loads(text):
    if not text:
        return None
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _supports_fallbacks(model: str) -> bool:
    return model.startswith(("claude-opus-5", "claude-sonnet-5-5", "claude-fable-5"))


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self):
        self._client = None

    def available(self) -> bool:
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            return False
        try:
            import google.genai  # noqa: F401
            return True
        except ImportError:
            return False

    def client(self):
        if self._client is None:
            from google import genai
            from google.genai import types
            key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            base = os.environ.get("GEMINI_BASE_URL")
            opts = types.HttpOptions(base_url=base) if base else None
            self._client = genai.Client(api_key=key, http_options=opts)
        return self._client

    async def transcribe(self, png: bytes, model: str) -> dict | None:
        from google.genai import types
        try:
            resp = await self.client().aio.models.generate_content(
                model=model,
                contents=[types.Part.from_bytes(data=png, mime_type="image/png"), USER_PROMPT],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0,
                    response_mime_type="application/json",
                    response_json_schema=SCHEMA,
                ),
            )
        except Exception as exc:  # the SDK raises several error families
            log.warning("gemini error: %s", type(exc).__name__)
            return None
        try:
            return parse_reading(resp.text)
        except Exception:
            return None


async def _gemini_complete(self, system: str, user: str, model: str, schema: dict) -> dict | None:
    from google.genai import types
    try:
        resp = await self.client().aio.models.generate_content(
            model=model, contents=[user],
            config=types.GenerateContentConfig(system_instruction=system, temperature=0.3,
                                               response_mime_type="application/json",
                                               response_json_schema=schema))
        return _loads(resp.text)
    except Exception:
        return None


GeminiProvider.complete_json = _gemini_complete


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(self):
        self._client = None

    def available(self) -> bool:
        if not os.environ.get("OPENAI_API_KEY"):
            return False
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            return False

    def client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(timeout=45.0, max_retries=2)
        return self._client

    async def transcribe(self, png: bytes, model: str) -> dict | None:
        b64 = base64.standard_b64encode(png).decode("ascii")
        try:
            resp = await self.client().chat.completions.create(
                model=model,
                temperature=0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": [
                        {"type": "text", "text": USER_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ]},
                ],
                response_format={"type": "json_schema",
                                 "json_schema": {"name": "line", "schema": SCHEMA, "strict": True}},
            )
        except Exception as exc:
            log.warning("openai error: %s", type(exc).__name__)
            return None
        try:
            return parse_reading(resp.choices[0].message.content)
        except Exception:
            return None


async def _openai_complete(self, system: str, user: str, model: str, schema: dict) -> dict | None:
    try:
        resp = await self.client().chat.completions.create(
            model=model, temperature=0.3,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_schema",
                             "json_schema": {"name": "hints", "schema": schema, "strict": True}})
        return _loads(resp.choices[0].message.content)
    except Exception:
        return None


OpenAIProvider.complete_json = _openai_complete


PROVIDERS = {"anthropic": AnthropicProvider(), "gemini": GeminiProvider(), "openai": OpenAIProvider()}


def resolve_models() -> tuple[list[tuple[Provider, str]], tuple[Provider, str] | None]:
    """The two read models and the tiebreak model, from the environment.

    TRANSCRIBE_PROVIDER: anthropic | gemini | openai | auto (default)
    READ_MODELS: comma list, entries "model" or "provider:model"
    TIEBREAK_MODEL: "model" or "provider:model" ("none" to disable)
    """
    choice = os.environ.get("TRANSCRIBE_PROVIDER", "auto").strip().lower()
    default_provider = None
    if choice in PROVIDERS:
        default_provider = PROVIDERS[choice] if PROVIDERS[choice].available() else None
    else:
        default_provider = next((p for p in PROVIDERS.values() if p.available()), None)

    def spec(entry: str):
        entry = entry.strip()
        if not entry:
            return None
        if ":" in entry:
            pname, model = entry.split(":", 1)
            p = PROVIDERS.get(pname.strip().lower())
            return (p, model.strip()) if p is not None and p.available() else None
        return (default_provider, entry) if default_provider is not None else None

    reads_env = os.environ.get("READ_MODELS", "")
    if reads_env.strip():
        reads = [s for s in (spec(e) for e in reads_env.split(",")) if s]
    elif default_provider is not None:
        reads = [(default_provider, m) for m in DEFAULT_MODELS[default_provider.name]["reads"]]
    else:
        reads = []
    tb_env = os.environ.get("TIEBREAK_MODEL")
    if tb_env is not None:
        tiebreak = None if tb_env.strip().lower() in ("", "none") else spec(tb_env)
    elif default_provider is not None:
        tiebreak = (default_provider, DEFAULT_MODELS[default_provider.name]["tiebreak"])
    else:
        tiebreak = None
    return reads[:2], tiebreak


def transcription_available() -> bool:
    reads, _ = resolve_models()
    return bool(reads)
