"""Fix step: a larger Nemotron model reads the evidence and the source, then writes a minimal patch."""

import difflib
import os
from dataclasses import dataclass
from pathlib import Path

from openai import AsyncOpenAI

from replay.agent import ReplayResult
from replay.conditions import Condition
from replay.llm import parse_json

SOURCE_SUFFIXES = (".py", ".js", ".html", ".css")
FIX_SYSTEM = """You fix one bug in a small web app.
You get a user's complaint, the user's real conditions, machine evidence of the failure, and the app's source files.
Reply with ONE JSON object and nothing else:
{"explanation": "<two sentences: the root cause and why it hits this user>",
 "edits": [{"file": "<path as given>", "find": "<exact text copied from that file>", "replace": "<new text>"}]}
Rules:
- Make the smallest change that fixes the root cause for this user. Do not touch unrelated code.
- "find" must be copied exactly from the file and appear exactly once in it.
- Fix the cause, not the symptom: do not hide error messages or delete checks."""


@dataclass(frozen=True)
class Patch:
    explanation: str
    edits: tuple[dict, ...]


def read_sources(shop: Path) -> str:
    files = sorted(p for p in shop.rglob("*") if p.suffix in SOURCE_SUFFIXES and "__pycache__" not in p.parts)
    return "\n\n".join(f"=== {p.relative_to(shop).as_posix()} ===\n{p.read_text(encoding='utf-8')}" for p in files)


async def pick_fix_model(client: AsyncOpenAI) -> str:
    if os.getenv("FIX_MODEL"):
        return os.environ["FIX_MODEL"]
    ids = [m.id for m in (await client.models.list()).data]
    return next((m for m in ids if "nemotron" in m.lower() and "super" in m.lower()), os.getenv("REPLAY_MODEL", ""))


async def propose_fix(client: AsyncOpenAI, model: str, complaint: str, condition: Condition,
                      result: ReplayResult, shop: Path) -> Patch:
    cited = [e for e in result.evidence if e.id in result.cited] or list(result.evidence)
    user = (
        f"Complaint: {complaint}\nUser conditions: {condition.persona}\n"
        f"Replay summary: {result.summary}\n"
        "Evidence:\n" + "\n".join(f"- [{e.kind}] {e.detail}" for e in cited) +
        f"\n\nSource files:\n{read_sources(shop)}"
    )
    resp = await client.chat.completions.create(
        model=model, temperature=0.1, max_tokens=12000,
        messages=[{"role": "system", "content": FIX_SYSTEM}, {"role": "user", "content": user}],
    )
    data = parse_json(resp.choices[0].message.content or "")
    return Patch(str(data.get("explanation", "")), tuple(data.get("edits", [])))


def apply_patch(patch: Patch, shop: Path) -> str:
    """Apply all edits or none. Returns a unified diff; raises ValueError on an unsafe or ambiguous edit."""
    root = shop.resolve()
    original: dict[Path, str] = {}
    current: dict[Path, str] = {}
    for edit in patch.edits:
        path = (root / str(edit.get("file", ""))).resolve()
        if root not in path.parents or not path.is_file():
            raise ValueError(f"edit points outside the app or to a missing file: {edit.get('file')!r}")
        if path not in current:
            original[path] = current[path] = path.read_text(encoding="utf-8")
        find, replace = str(edit.get("find", "")), str(edit.get("replace", ""))
        if not find or current[path].count(find) != 1:
            raise ValueError(f"'find' text must appear exactly once in {edit.get('file')}")
        current[path] = current[path].replace(find, replace)
    diff = []
    for path, after in current.items():
        rel = path.relative_to(root).as_posix()
        diff += difflib.unified_diff(original[path].splitlines(True), after.splitlines(True), f"a/{rel}", f"b/{rel}")
        path.write_text(after, encoding="utf-8")
    return "".join(diff)
