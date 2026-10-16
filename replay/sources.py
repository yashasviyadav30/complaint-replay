"""Which source files the fixer should read, in a repo far too big to send whole.

Clues come from the machine evidence and the replay: control names the user tapped, URL paths, error
text, CSS ids from accessibility reports. Files that contain rare clues rank first.
ponytail: plain text search; add embedding search over the repo when grep misses real bugs.
"""

import fnmatch
import math
import re
import subprocess
from pathlib import Path

SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".vue", ".svelte", ".astro", ".html", ".htm",
                   ".css", ".scss", ".sass", ".less", ".json", ".yml", ".yaml", ".php", ".rb", ".erb", ".go",
                   ".java", ".kt", ".cs", ".cshtml", ".razor", ".jinja", ".j2", ".hbs", ".ejs", ".liquid", ".twig"}
SKIP_PARTS = {"node_modules", ".git", "dist", "build", ".next", ".nuxt", ".svelte-kit", "coverage", "vendor",
              "__pycache__", ".venv", "venv", ".complaint-replay", "out", "target", ".turbo", ".cache"}
SKIP_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "composer.lock", "Gemfile.lock", "poetry.lock",
              "complaint-replay.toml"}
MAX_FILE_CHARS = 100_000  # bigger files are bundles, fixtures or generated (real components reach 65k: Actual)
BUDGET_CHARS = 200_000    # about 50k tokens of source per fix request
MIN_CLUE = 3
QUOTED = re.compile(r"['\"‘“]([^'\"’”]{3,80})['\"’”]")
PATH = re.compile(r"/[\w\-./]{2,}")
SELECTOR = re.compile(r"[#.]([A-Za-z][\w-]{2,})")
ATTRIBUTE = re.compile(r'\b[\w-]+="[^"]{2,40}"')  # type="date": how source code writes the element
IMPORT = re.compile(r"""(?:from|import|require\()\s*['"]([^'"]+/[^'"]+)['"]""")  # paths only, not 'react'
IMPORT_SUFFIXES = ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".vue", ".svelte", "/index.ts", "/index.tsx", "/index.js")
FOLLOW_TOP = 3  # imports of the best matches only: a shared component often holds the bug (an input used everywhere)


def list_sources(root: Path, allowed: tuple[str, ...] = ()) -> list[str]:
    """Repo-relative paths of text source files (git's view when it is a git repo)."""
    try:
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=root, capture_output=True,
                             text=True, check=True).stdout.splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        out = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
    paths = []
    for rel in out:
        parts = rel.split("/")
        if SKIP_PARTS & set(parts[:-1]) or parts[-1] in SKIP_NAMES or Path(rel).suffix.lower() not in SOURCE_SUFFIXES:
            continue
        if allowed and not any(fnmatch.fnmatch(rel, g) for g in allowed):
            continue
        path = root / rel
        if path.is_file() and path.stat().st_size <= MAX_FILE_CHARS * 4:
            paths.append(rel)
    return sorted(paths)


def clues(texts: list[str]) -> list[str]:
    """Short strings worth searching the code for, taken from evidence details and step names."""
    found: set[str] = set()
    for text in texts:
        found.update(QUOTED.findall(text))
        found.update(p.strip("/.") for p in PATH.findall(text))
        found.update(SELECTOR.findall(text))
        found.update(ATTRIBUTE.findall(text))
    return sorted(c for c in found if len(c.strip()) >= MIN_CLUE)


def pick(root: Path, hints: list[str], allowed: tuple[str, ...] = (), budget: int = BUDGET_CHARS) -> list[str]:
    """Files to show the fixer: everything when it fits the budget, else the files that best match the clues."""
    texts = {}
    for rel in list_sources(root, allowed):
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if len(text) <= MAX_FILE_CHARS:
            texts[rel] = text
    if sum(map(len, texts.values())) <= budget:
        return sorted(texts)
    lowered = {r: t.lower() for r, t in texts.items()}
    terms = [c.lower() for c in clues(hints)]
    df = {c: sum(1 for t in lowered.values() if c in t) for c in terms}
    n = len(lowered)

    def score(rel: str) -> float:
        return sum(math.log((n + 1) / (df[c] + 1)) * (1 + (c in rel.lower())) for c in terms if c in lowered[rel])

    ranked = [r for r in sorted(lowered, key=score, reverse=True) if score(r) > 0]
    # The best matches first, then the local files they import, then the other matches.
    order = ranked[:FOLLOW_TOP] + [i for r in ranked[:FOLLOW_TOP] for i in local_imports(r, texts)] + ranked[FOLLOW_TOP:]
    chosen, used = [], 0
    for rel in dict.fromkeys(order):
        if used + len(texts[rel]) > budget:
            continue
        chosen.append(rel)
        used += len(texts[rel])
    return sorted(chosen)


def local_imports(rel: str, texts: dict[str, str]) -> list[str]:
    """Repo files that `rel` imports: relative (./Button) or through an alias (#components/x, @/x, ~/x).

    An alias is matched by the end of the path, and only when exactly one repo file fits.
    """
    found = []
    for spec in IMPORT.findall(texts[rel]):
        if spec.startswith("."):
            parts = []
            for part in (Path(rel).parent / spec).as_posix().split("/"):  # resolve ../ without the disk
                if part == "..":
                    parts = parts[:-1]
                elif part not in (".", ""):
                    parts.append(part)
            found += [f for s in IMPORT_SUFFIXES if (f := "/".join(parts) + s) in texts][:1]
        else:
            tail = "/" + spec.lstrip("#@~/")
            fits = [f for f in texts if any(f.endswith(tail + s) for s in IMPORT_SUFFIXES)]
            found += fits if len(fits) == 1 else []
    return found


def read(root: Path, rels: list[str]) -> str:
    return "\n\n".join(f"=== {rel} ===\n{(root / rel).read_text(encoding='utf-8')}" for rel in rels)
