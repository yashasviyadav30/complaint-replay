"""NVIDIA Nemotron models on Nebius Token Factory (OpenAI-compatible API)."""

import json
import os
import re

from openai import AsyncOpenAI

from replay.agent import Policy, build_prompt

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def make_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=os.getenv("NEBIUS_BASE_URL") or DEFAULT_BASE_URL,
        api_key=os.environ["NEBIUS_API_KEY"],
    )


def parse_json(text: str) -> dict:
    """Pull the JSON object out of a reply, ignoring reasoning blocks and stray prose."""
    text = THINK_BLOCK.sub("", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"no JSON object in model reply: {text[:200]!r}")
    return json.loads(text[start : end + 1])


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


def llm_policy(client: AsyncOpenAI, model: str, retries: int = 2) -> Policy:
    async def policy(ctx: dict) -> dict:
        system, user = build_prompt(ctx)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        for attempt in range(retries + 1):
            resp = await client.chat.completions.create(
                model=model, messages=messages, temperature=0.2, max_tokens=1500
            )
            reply = resp.choices[0].message.content or ""
            try:
                return parse_json(reply)["action"]
            except (ValueError, KeyError) as e:
                if attempt == retries:
                    return {"type": "verdict", "verdict": "not_reproduced", "summary": f"Model reply unreadable: {e}"}
                messages += [
                    {"role": "assistant", "content": reply},
                    {"role": "user", "content": "Reply with only the JSON object described in the rules."},
                ]
        raise AssertionError("unreachable")

    return policy
