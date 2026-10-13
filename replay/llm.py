"""NVIDIA Nemotron models on Nebius Token Factory (OpenAI-compatible API)."""

import json
import os
import re

from openai import AsyncOpenAI

from replay.agent import Matcher, Policy, build_prompt

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
# Free, card-less NVIDIA endpoint for development. The submission must use Token Factory.
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def make_client() -> AsyncOpenAI:
    if os.getenv("NEBIUS_API_KEY"):
        return AsyncOpenAI(base_url=os.getenv("NEBIUS_BASE_URL") or DEFAULT_BASE_URL,
                           api_key=os.environ["NEBIUS_API_KEY"])
    if os.getenv("NVIDIA_API_KEY"):
        return AsyncOpenAI(base_url=NVIDIA_BASE_URL, api_key=os.environ["NVIDIA_API_KEY"])
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


class TokenBudgetExceeded(RuntimeError):
    pass


class Chat:
    """One model plus a hard token budget, so a looping agent can never run up a bill."""

    def __init__(self, client: AsyncOpenAI, model: str):
        self.client, self.model = client, model
        self.budget = int(os.getenv("REPLAY_TOKEN_BUDGET", "2000000"))
        self.used = 0

    async def __call__(self, messages: list[dict]) -> str:
        if self.used >= self.budget:
            raise TokenBudgetExceeded(f"used {self.used} tokens, budget is {self.budget} (REPLAY_TOKEN_BUDGET)")
        # Thinking off: one step at a time doesn't need it, and long thinking used up
        # max_tokens before any answer (empty replies in the first risk test).
        resp = await self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=0.2, max_tokens=1500,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        self.used += resp.usage.total_tokens if resp.usage else 0
        return resp.choices[0].message.content or ""


MATCH_SYSTEM = """You decide whether machine evidence from a real browser proves a user's complaint.
Reply with ONE JSON object and nothing else: {"evidence": ["E1", ...], "summary": "<two sentences>"}
List only ids whose detail clearly shows the problem the user complained about.
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
