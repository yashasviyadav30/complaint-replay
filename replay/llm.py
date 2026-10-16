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
    # strict=False: models often put raw line breaks inside strings (code in a "find" text); accept them.
    obj, _ = json.JSONDecoder(strict=False).raw_decode(text[start:])  # first object only; models may add a second
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
    # Nemotron 3 Super, as the docs say. The old "prefer nano" default picked a small multimodal reasoning model
    # in CI and in every customer's Action (no REPLAY_MODEL there), and the twin wandered on a real app.
    return next((m for m in models if "nemotron-3-super" in m.lower()),
                next((m for m in models if "super" in m.lower()), models[0]))


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


BUSY_WAITS_S = (30, 60, 120, 240)  # a shared free endpoint can be full for minutes ("503 ResourceExhausted")


async def patiently(call, sleep=asyncio.sleep):
    """Run a model call; when the server is busy or overloaded, wait and try again before giving up."""
    from openai import APIConnectionError, InternalServerError, RateLimitError

    for wait in BUSY_WAITS_S:
        try:
            return await call()
        except (InternalServerError, RateLimitError, APIConnectionError):
            await sleep(wait)
    return await call()


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
        resp = await patiently(lambda: self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=0.2, max_tokens=max_tokens,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        ))
        self.used += resp.usage.total_tokens if resp.usage else 0
        return resp.choices[0].message.content or ""


MATCH_SYSTEM = """You decide whether machine evidence from a real browser proves a user's complaint.
Reply with ONE JSON object and nothing else: {"evidence": ["E1", ...], "summary": "<two sentences>"}
List only ids whose detail clearly shows the problem the user complained about.
Real apps have several bugs at once: if an item shows a different problem than the one described (another
control, another page, another kind of failure), leave it out even if it is a real bug.
An item that only stopped the replay from reaching the screen or control the user talks about is NOT proof of
their problem: if the user complains about a switch, a date picker or a field, the item must be about that
switch, picker or field. When in doubt, cite nothing.
Unrelated errors do not count, and neither do errors the replay caused itself by doing something the user
never described (for example typing a wrong code). If nothing matches, reply {"evidence": [], "summary": ""}."""


LOAD_KINDS = {"slow_page", "slow_request", "layout_shift"}
SLOWNESS_SYSTEM = """A user complained about a website. Is the complaint about speed: something slow, loading forever,
timing out, or the page jumping while it loads? Any language.
Reply with ONE JSON object and nothing else: {"about_speed": true} or {"about_speed": false}"""


async def about_speed(chat: Chat, complaint: str) -> bool:
    try:
        return parse_json(await chat([{"role": "system", "content": SLOWNESS_SYSTEM},
                                      {"role": "user", "content": complaint}])).get("about_speed") is True
    except ValueError:
        return True  # unreadable: keep the evidence and let the judge decide, as before


def llm_matcher(chat: Chat) -> Matcher:
    speed: dict[str, bool] = {}  # asked once per complaint

    async def matcher(complaint: str, evidence: list) -> dict:
        # Load-speed evidence proves only complaints about speed. A prompt rule alone did not hold: the judge cited
        # "page appeared after 28 s" for a date picker that never opens (cloud case 9071, runs 6 and 7).
        if any(e.kind in LOAD_KINDS for e in evidence):
            if complaint not in speed:
                speed[complaint] = await about_speed(chat, complaint)
            if not speed[complaint]:
                evidence = [e for e in evidence if e.kind not in LOAD_KINDS]
        if not evidence:
            return {"evidence": []}
        lines ="\n".join(f"{e.id} [{e.kind}] {e.detail}" for e in evidence)
        reply = await chat([{"role": "system", "content": MATCH_SYSTEM},
                            {"role": "user", "content": f"Complaint: {complaint}\n\nEvidence:\n{lines}"}])
        try:
            data = parse_json(reply)
        except ValueError:
            return {"evidence": []}
        by_id = {e.id: e for e in evidence}
        cited = [i for i in data.get("evidence") or [] if i in by_id]
        # A second, narrower question per item: the judge alone kept citing obstacles on the way as proof.
        kept = [i for i in cited if await is_the_problem(chat, complaint, by_id[i])]
        return {"evidence": kept, "summary": str(data.get("summary", "")) if kept else ""}

    return matcher


SKEPTIC_SYSTEM = """A user complained about a website. One piece of machine evidence from a replay is shown.
Does it show THE PROBLEM THE USER DESCRIBES, in the place they describe it? Or is it something else: a different
control, a different screen, or an obstacle that only got in the way of reaching what they talk about?
Evidence about how fast the page loaded (slow_page, slow_request, layout_shift) proves only complaints about
slowness or jumping pages, never a control that does nothing or a value that is wrong.
Reply with ONE JSON object and nothing else: {"answer": "problem"} or {"answer": "other"}"""


async def is_the_problem(chat: Chat, complaint: str, item) -> bool:
    reply = await chat([{"role": "system", "content": SKEPTIC_SYSTEM},
                        {"role": "user", "content": f"Complaint: {complaint}\n\nEvidence: [{item.kind}] {item.detail}"}])
    try:
        return parse_json(reply).get("answer") == "problem"
    except ValueError:
        return False  # unreadable means unproven: never call a bug proven on a guess


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
