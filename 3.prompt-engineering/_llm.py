"""
_llm.py — one shared place to build the LLM client for every lesson.

WHY THIS FILE EXISTS
    We use the OpenAI SDK for EVERY provider, because both GitHub Models and
    Google Gemini speak the OpenAI API "shape". So switching provider is only a
    change of three things: base_url, api_key, and the model name. Nothing else
    in any lesson changes. That is the whole "provider-agnostic" idea (Phase 5),
    arriving early — forced on us by GitHub Models' tight free rate limits.

WHICH PROVIDER GETS USED (in order)
    1. LLM_PROVIDER=radar | arc | gemini | github      -> forces that one
    2. else if RADAR_OPEN_MODEL_KEY is set             -> RADAR qwen3-30b (unlimited)
    3. else if KCL_AI_MODEL_API_KEY is set             -> KCL ARC-AI (needs VPN)
    4. else if AGENTIC_AI_LEARNING_GEMINI_KEY is set    -> Google Gemini
    5. else                                             -> GitHub Models

Four providers, one code path — RADAR (qwen3-30b), GitHub Models, Google Gemini,
and KCL ARC-AI all speak the OpenAI API "shape". Switching is only base_url +
api_key + model. RADAR is the default: unlimited for us and reachable without VPN.

Every lesson does:
    from _llm import build_client, ask, MODEL, PROVIDER
"""

import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import (
    OpenAI,
    BadRequestError,
    RateLimitError,
    InternalServerError,
    APITimeoutError,
    APIConnectionError,
)

# Load the .env sitting next to this file (same folder as the lessons).
load_dotenv(Path(__file__).with_name(".env"))

# Matches a full <think>...</think> reasoning block from "thinking" models.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

# Each provider needs just these three fields. Gemini exposes an
# OpenAI-compatible endpoint at the /v1beta/openai/ path.
# NOTE on model choice: on the free tier, gemini-2.0-flash* return HTTP 429
# ("quota limit: 0" — not free for this account), and the bigger "thinking"
# models (gemini-2.5-flash) can spend a small max_tokens budget on hidden
# reasoning and return EMPTY text. gemini-2.5-flash-lite has free quota and
# returns text directly, so it is the reliable default for these lessons.
_GEMINI = {
    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "key_env": "AGENTIC_AI_LEARNING_GEMINI_KEY",
    "model": "gemini-2.5-flash-lite",
}
_GITHUB = {
    "base_url": "https://models.github.ai/inference",
    "key_env": "AGENTIC_AI_LEARNING_GH_TOKEN",
    "model": "openai/gpt-4o-mini",
}

_ARC = {
    "base_url": "https://api.ai.create.kcl.ac.uk/v1",
    "key_env": "KCL_AI_MODEL_API_KEY",
    "model": "arc:lite",
}
# RADAR inference (KCL): OpenAI-compatible, effectively unlimited for us, and
# (unlike ARC) reachable without the VPN. qwen3-30b is a "thinking" model, so
# ask() strips any <think>...</think> block it emits.
_RADAR = {
    "base_url": "https://radar-inference.sites.er.kcl.ac.uk/v1",
    "key_env": "RADAR_OPEN_MODEL_KEY",
    "model": "qwen3-30b",
}

_PROVIDERS = {"radar": _RADAR, "arc": _ARC, "gemini": _GEMINI, "github": _GITHUB}


def _resolve() -> tuple[str, dict]:
    forced = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if forced in _PROVIDERS:
        return forced, _PROVIDERS[forced]
    # Auto-pick, best-for-us first: RADAR (unlimited, no VPN), then ARC (VPN),
    # then Gemini, then GitHub Models.
    if os.environ.get(_RADAR["key_env"]):
        return "radar", _RADAR
    if os.environ.get(_ARC["key_env"]):
        return "arc", _ARC
    if os.environ.get(_GEMINI["key_env"]):
        return "gemini", _GEMINI
    return "github", _GITHUB


PROVIDER, _CFG = _resolve()
MODEL = _CFG["model"]


def build_client(http_client=None) -> OpenAI:
    key = os.environ.get(_CFG["key_env"])
    if not key:
        raise SystemExit(
            f"No API key for provider '{PROVIDER}'.\n"
            f"Set {_CFG['key_env']} in the .env file next to the lessons."
        )
    kwargs = {"base_url": _CFG["base_url"], "api_key": key}
    if http_client is not None:                # p0001 passes a client to see the wire
        kwargs["http_client"] = http_client
    return OpenAI(**kwargs)


def ask(client: OpenAI, messages: list, show_thinking: bool = False, **kw) -> str:
    """Send messages, return the reply text. Survives rate limits and filters.

    show_thinking=False (default): strip any <think>...</think> block.
    show_thinking=True:            keep it, so you can see the raw reasoning.
    """
    kw.setdefault("temperature", 0)
    for attempt in range(4):
        try:
            resp = client.chat.completions.create(model=MODEL, messages=messages, **kw)
            content = resp.choices[0].message.content
            # "Thinking" models can use the whole max_tokens budget on hidden
            # reasoning and return no text. Never hand back None (it would crash
            # a lesson's .strip()); return a clear marker instead.
            if content is None:
                return "<<no text — model spent the token budget on reasoning; raise max_tokens>>"
            if show_thinking:
                return content.strip()          # keep the <think>...</think> block
            # Otherwise strip it so lessons see only the final answer.
            return _THINK_RE.sub("", content).strip()
        except (RateLimitError, InternalServerError,
                APITimeoutError, APIConnectionError) as e:
            # Transient: free-tier rate limit (429), server busy (503/500), or a
            # network blip. Wait and retry a few times (5s, 10s, 15s) instead of
            # crashing the whole lesson.
            if attempt == 3:
                return f"<<temporary provider error ({type(e).__name__}); wait a moment and re-run>>"
            time.sleep(5 * (attempt + 1))
        except BadRequestError:
            # Providers filter obvious "ignore your instructions" attacks and
            # return a 400. Catch it so a demo never crashes the lesson.
            return "<<blocked by the provider's content filter>>"
    return "<<unreachable>>"
