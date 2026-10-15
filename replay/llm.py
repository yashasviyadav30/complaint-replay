"""NVIDIA Nemotron models on Nebius Token Factory (OpenAI-compatible API)."""

import asyncio
import json
import time
from collections import deque
import os
import re

from openai import AsyncOpenAI

from replay.agent import Matcher, Policy, build_prompt

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
# Free, card-less NVIDIA endpoint for development. The submission must use Token Factory.
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


# Retries back off and respect Retry-After; the default (2) was not enough for a long benchmark on a
# rate-limited endpoint (HTTP 429 mid-run).
MAX_RETRIES = 8


def make_client() -> AsyncOpenAI:
    """Nebius Token Factory first. Teams that must keep data in-house can point at any OpenAI-compatible
    server instead (their own vLLM, NIM or Ollama) with REPLAY_BASE_URL and REPLAY_API_KEY."""
    if os.getenv("REPLAY_BASE_URL"):
        return AsyncOpenAI(base_url=os.environ["REPLAY_BASE_URL"], api_key=os.getenv("REPLAY_API_KEY") or "none",
                           max_retries=MAX_RETRIES)
    if os.getenv("NEBIUS_API_KEY"):
        return AsyncOpenAI(base_url=os.getenv("NEBIUS_BASE_URL") or DEFAULT_BASE_URL,
                           api_key=os.environ["NEBIUS_API_KEY"], max_retries=MAX_RETRIES)
    if os.getenv("NVIDIA_API_KEY"):
        return AsyncOpenAI(base_url=NVIDIA_BASE_URL, api_key=os.environ["NVIDIA_API_KEY"], max_retries=MAX_RETRIES)
    raise RuntimeError("set NEBIUS_API_KEY (Token Factory) or NVIDIA_API_KEY (build.nvidia.com) in .env")


def parse_json(text: str) -> dict:
    """Pull the JSON object out of a reply, ignoring reasoning blocks and stray prose."""
    text = THINK_BLOCK.sub("", text)
    start = text.find("{")
    if start == -1:
        raise ValueError(f"no JSON object in model reply: {text[:200]!r}")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])  # first object only; models sometimes add a second
    return obj


async def nemotron_models(client: AsyncOpenAI) -> list[str]:
    page = await client.models.list()
    return sorted(m.id for m in page.data if "nemotron" in m.id.lower())


async def pick_model(client: AsyncOpenAI) -> str:
    if os.getenv("REPLAY_MODEL"):
        return os.environ["REPLAY_MODEL"]
    models = await nemotron_models(client)
    if not models:
        raise RuntimeError("no Nemotron model in the Token Factory catalog; set REPLAY_MODEL")
    # Prefer a fast tier for step-by-step browsing.
    return next((m for m in models if "nano" in m.lower()), models[0])


_calls: deque[float] = deque()  # start times of recent model requests, process-wide
FREE_TIER_RPM = 30  # NVIDIA's free endpoint allows about 40 requests a minute; stay under it


def max_rpm() -> int:
    if os.getenv("REPLAY_MAX_RPM"):
        return int(os.environ["REPLAY_MAX_RPM"])
    return FREE_TIER_RPM if not os.getenv("NEBIUS_API_KEY") and os.getenv("NVIDIA_API_KEY") else 0


async def throttle(now=time.monotonic, sleep=asyncio.sleep) -> None:
    """Keep under the endpoint's per-minute limit instead of hitting it: retries alone all land in the same minute."""
    rpm = max_rpm()
    while rpm:
        t = now()
        while _calls and t - _calls[0] >= 60:
            _calls.popleft()
        if len(_calls) < rpm:
            _calls.append(t)
            return
        await sleep(60 - (t - _calls[0]) + 0.05)


class TokenBudgetExceeded(RuntimeError):
    pass


class Chat:
    """One model plus a hard token budget, so a looping agent can never run up a bill."""

    def __init__(self, client: AsyncOpenAI, model: str):
        self.client, self.model = client, model
        self.budget = int(os.getenv("REPLAY_TOKEN_BUDGET", "2000000"))
        self.used = 0

    async def __call__(self, messages: list[dict], max_tokens: int = 1500) -> str:
        if self.used >= self.budget:
            raise TokenBudgetExceeded(f"used {self.used} tokens, budget is {self.budget} (REPLAY_TOKEN_BUDGET)")
        # Thinking off: one step at a time doesn't need it, and long thinking used up
        # max_tokens before any answer (empty replies in the first risk test).
        await throttle()
        resp = await self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=0.2, max_tokens=max_tokens,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        self.used += resp.usage.total_tokens if resp.usage else 0
        return resp.choices[0].message.content or ""


MATCH_SYSTEM = """You decide whether machine evidence from a real browser proves a user's complaint.
Reply with ONE JSON object and nothing else: {"evidence": ["E1", ...], "summary": "<two sentences>"}
List only ids whose detail clearly shows the problem the user complained about.
Real apps have several bugs at once: if an item shows a different problem than the one described (another
control, another page, another kind of failure), leave it out even if it is a real bug.
Unrelated errors do not count, and neither do errors the replay caused itself by doing something the user
never described (for example typing a wrong code). If nothing matches, reply {"evidence": [], "summary": ""}."""


def llm_matcher(chat: Chat) -> Matcher:
    async def matcher(complaint: str, evidence: list) -> dict:
        lines = "\n".join(f"{e.id} [{e.kind}] {e.detail}" for e in evidence)
        reply = await chat([{"role": "system", "content": MATCH_SYSTEM},
                            {"role": "user", "content": f"Complaint: {complaint}\n\nEvidence:\n{lines}"}])
        try:
            data = parse_json(reply)
        except ValueError:
            return {"evidence": []}
        return {"evidence": list(data.get("evidence") or []), "summary": str(data.get("summary", ""))}

    return matcher


NEEDS_SYSTEM = """A user complained about a website. Some needs no device can report: a screen reader, using only
a keyboard, or text made larger. Did THIS user say (in any language) that they rely on one of these?
Reply with ONE JSON object and nothing else: {"screen_reader": false, "keyboard_only": false, "text_zoom": 1.0}
Set a value only when the complaint says so; text_zoom is 2.0 for "bigger letters" or "zoomed in"."""


async def stated_needs(chat: Chat, complaint: str) -> dict:
    """What the widget cannot see but the user told us: screen reader, keyboard only, larger text."""
    try:
        data = parse_json(await chat([{"role": "system", "content": NEEDS_SYSTEM},
                                      {"role": "user", "content": complaint}]))
    except ValueError:
        return {}
    zoom = data.get("text_zoom")
    return {"screen_reader": data.get("screen_reader") is True, "keyboard_only": data.get("keyboard_only") is True,
            "zoom": float(zoom) if isinstance(zoom, (int, float)) and 1 <= zoom <= 3 else 1.0}


def llm_policy(chat: Chat, retries: int = 2) -> Policy:
    async def policy(ctx: dict) -> dict:
        system, user = build_prompt(ctx)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        for attempt in range(retries + 1):
            reply = await chat(messages)
            try:
                data = parse_json(reply)
                # Models sometimes drop the {"action": ...} wrapper; accept the bare action too.
                action = data.get("action") if isinstance(data.get("action"), dict) else data
                if "type" not in action:
                    raise ValueError("reply has no action type")
                return {**action, "why": str(data.get("thought", ""))[:200]}
            except ValueError as e:
                if attempt == retries:
                    # An unreadable reply must never decide the verdict: wait and let the next step retry.
                    return {"type": "wait", "ms": 500, "why": f"model reply unreadable: {e}"}
                messages += [
                    {"role": "assistant", "content": reply},
                    {"role": "user", "content": "Reply with only the JSON object described in the rules."},
                ]
        raise AssertionError("unreachable")

    return policy
