"""Fix step: a larger Nemotron model reads the evidence and the source, then writes a minimal patch."""

import difflib
import fnmatch
import os
import re
from dataclasses import dataclass
from pathlib import Path

from openai import AsyncOpenAI

from replay.agent import ReplayResult
from replay.conditions import Condition
from replay import sources as src
from replay.llm import parse_json, patiently, throttle

FIX_SYSTEM = """You fix one bug in a web app.
You get a user's complaint, the user's real conditions, machine evidence of the failure, the steps that triggered it,
and the source files most related to the evidence (in a big app, only some files are shown).
Reply with ONE JSON object and nothing else:
{"explanation": "<two sentences: the root cause and why it hits this user>",
 "edits": [{"file": "<path as given>", "find": "<exact text copied from that file>", "replace": "<new text>"}]}
Rules:
- Make the smallest change that fixes the root cause for this user. Do not touch unrelated code.
- "find" must be copied exactly from the file and appear exactly once in it.
- Fix the cause, not the symptom: do not hide error messages or delete checks."""


# Reasoning is on for the fixer, and on a big repo it used all of 12k tokens before writing a patch (Actual,
# case 8926). The NVIDIA endpoint accepts 32k.
FIX_MAX_TOKENS = 32000


@dataclass(frozen=True)
class Patch:
    explanation: str
    edits: tuple[dict, ...]


def fix_clues(result: ReplayResult) -> list[str]:
    """Text to search the code for: the evidence and the names of the controls the twin used."""
    steps = [f"'{s['target']}'" for s in result.steps if s.get("target")]
    return [e.detail for e in result.evidence if e.id in result.cited] + steps


def steps_text(result: ReplayResult) -> str:
    return "\n".join(f"{i + 1}. {s['action'].get('type')} '{s.get('target') or ''}' -> {s['result']}"
                     for i, s in enumerate(result.steps[-12:]))


async def pick_fix_model(client: AsyncOpenAI) -> str:
    if os.getenv("FIX_MODEL"):
        return os.environ["FIX_MODEL"]
    ids = [m.id for m in (await client.models.list()).data]
    return next((m for m in ids if "nemotron" in m.lower() and "super" in m.lower()), os.getenv("REPLAY_MODEL", ""))


def background(sources: list[dict]) -> str:
    """Web research (Tavily) about the evidence; the model cites a URL only if it actually relied on it."""
    if not sources:
        return ""
    lines = "\n".join(f"- {s['title']} ({s['url']}): {s['content']}" for s in sources)
    return ("\n\nBackground found on the web. Use it only if relevant; if you rely on one, name its URL in the "
            f"explanation:\n{lines}")


async def propose_fix(client: AsyncOpenAI, model: str, complaint: str, condition: Condition,
                      result: ReplayResult, root: Path, sources: list[dict] | None = None,
                      rejected: str | None = None, allowed: tuple[str, ...] = (),
                      also: tuple[str, ...] = ()) -> Patch:
    cited = [e for e in result.evidence if e.id in result.cited] or list(result.evidence)
    files = src.pick(root, fix_clues(result), allowed)
    # On a retry, the files the last attempt tried to edit are shown in full: it may have guessed their text.
    files += [f for f in also if f not in files and (root / f).is_file() and root.resolve() in (root / f).resolve().parents]
    if not files:
        raise ValueError("no source files to fix: check `edit` in complaint-replay.toml")
    user = (
        f"Complaint: {complaint}\nUser conditions: {condition.persona}\n"
        f"Replay summary: {result.summary}\n"
        "Evidence:\n" + "\n".join(f"- [{e.kind}] {e.detail}" for e in cited) +
        f"\nSteps that triggered it:\n{steps_text(result)}" +
        background(sources or []) +
        f"\n\nSource files:\n{src.read(root, files)}" +
        (f"\n\nYour previous patch was rejected: {rejected}. Copy each 'find' text exactly from the file and include "
         "enough surrounding lines that it appears exactly once." if rejected else "")
    )
    await throttle()
    resp = await patiently(lambda: client.chat.completions.create(
        model=model, temperature=0.1, max_tokens=FIX_MAX_TOKENS,
        messages=[{"role": "system", "content": FIX_SYSTEM}, {"role": "user", "content": user}],
    ))
    choice = resp.choices[0]
    if not choice.message.content and choice.finish_reason == "length":
        raise ValueError(f"the reply ran out of tokens ({FIX_MAX_TOKENS}) while reasoning, before writing the patch")
    data = parse_json(choice.message.content or "")
    return Patch(str(data.get("explanation", "")), tuple(data.get("edits", [])))


# Files a fix may never change, whatever the model says: they control what runs in CI and with which secrets.
# A complaint is untrusted text; without this, a prompt-injected "fix" could rewrite the start command.
PROTECTED = ("complaint-replay.toml", ".github/*", "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
             "pyproject.toml", "uv.lock", "requirements*.txt", "Dockerfile", "docker-compose*", "Makefile", "*.sh",
             "*.ps1", ".env*", "*/.env*", ".npmrc", ".git/*", "vite.config.*", "webpack.config.*", "next.config.*",
             # Tests and guards judge the fix, so the fix may not change them: on Actual the fixer once "fixed" a bug
             # by changing a test's mock (cloud case 8926).
             "*.test.*", "*.spec.*", "test_*.py", "*_test.py", "*_test.go", "__tests__/*", "*/__tests__/*",
             "e2e/*", "*/e2e/*", ".complaint-replay/*")


def protected(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(name, g) for g in PROTECTED)


def loose_match(text: str, find: str) -> tuple[int, int] | None:
    """Where `find` appears once if spacing and indentation are ignored, else None.

    Models copy code with changed indentation or line breaks; on Actual both fix attempts for case 9071 failed
    on that alone, in the right file.
    """
    pattern = r"\s+".join(re.escape(word) for word in find.split())
    found = list(re.finditer(pattern, text))
    return found[0].span() if len(found) == 1 else None


def apply_patch(patch: Patch, root: Path, allowed: tuple[str, ...] = ()) -> str:
    """Apply all edits or none. Returns a unified diff; raises ValueError on an unsafe or ambiguous edit.

    Line endings are kept as they are in each file (a Windows checkout has CRLF; the model writes LF).
    """
    root = root.resolve()
    original: dict[Path, str] = {}
    current: dict[Path, str] = {}
    for edit in patch.edits:
        path = (root / str(edit.get("file", ""))).resolve()
        if root not in path.parents or not path.is_file():
            raise ValueError(f"edit points outside the app or to a missing file: {edit.get('file')!r}")
        rel = path.relative_to(root).as_posix()
        if protected(rel):
            raise ValueError(f"{rel} is a test, or controls builds or secrets; a fix must change the app itself")
        if allowed and not any(fnmatch.fnmatch(rel, g) for g in allowed):
            raise ValueError(f"{rel} is not in the files this project lets the fixer change ({', '.join(allowed)})")
        if path not in current:
            original[path] = current[path] = path.read_text(encoding="utf-8", newline="")
        find, replace = str(edit.get("find", "")), str(edit.get("replace", ""))
        if "\r\n" in current[path]:
            find, replace = (t.replace("\r\n", "\n").replace("\n", "\r\n") for t in (find, replace))
        count = current[path].count(find) if find else 0
        if count == 1:
            current[path] = current[path].replace(find, replace)
            continue
        span = loose_match(current[path], find) if count == 0 and find.strip() else None
        if not span:
            raise ValueError(f"'find' text must appear exactly once in {edit.get('file')}, but it appears {count} times")
        current[path] = current[path][:span[0]] + replace + current[path][span[1]:]
    diff = []
    for path, after in current.items():
        rel = path.relative_to(root).as_posix()
        diff += difflib.unified_diff(original[path].splitlines(True), after.splitlines(True), f"a/{rel}", f"b/{rel}")
        path.write_text(after, encoding="utf-8", newline="")
    return "".join(diff)
