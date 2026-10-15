"""Complaint Replay service: receives complaints from the widget and serves it.

Run: uv run uvicorn server.app:app --port 8200
"""

import asyncio
import json
import logging
import os
import random
import re
import time
import uuid
from collections import defaultdict, deque
from contextlib import ExitStack, asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from zoneinfo import available_timezones

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from replay.bugs import BUGS, LIVE_SHOP, Bug, inject, reset_workspace
from replay.conditions import twin_condition
from replay.grouping import find_duplicate
from replay.investigate import investigate
from replay.llm import Chat, make_client, pick_model
from replay.project import running_app

HERE = Path(__file__).resolve().parent
STORE = HERE.parent / "results" / "complaints.jsonl"
CASES_DIR = HERE.parent / "results" / "cases"
VECTORS = CASES_DIR.parent / "vectors.json"  # case id -> embedding of its first complaint (not a case file)
DASHBOARD_DIST = HERE.parent / "dashboard" / "dist"
RATE_LIMIT, RATE_WINDOW_S = 30, 60
LIVE_PORT = int(os.getenv("LIVE_SHOP_PORT", "8100"))
log = logging.getLogger("complaint-replay")
TIMEZONES = available_timezones()

# Personal data masked before a complaint is stored or shown to any model.
PII_PATTERNS = (
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"), "[phone]"),
    (re.compile(r"(?<!\d)\d{12,19}(?!\d)"), "[number]"),  # cards, Aadhaar, long order ids
)


def mask_pii(text: str) -> str:
    for pattern, token in PII_PATTERNS:
        text = pattern.sub(token, text)
    return text


class Viewport(BaseModel):
    width: int = Field(ge=200, le=8000)
    height: int = Field(ge=200, le=8000)


class Env(BaseModel):
    effective_type: Literal["slow-2g", "2g", "3g", "4g"] | None = None
    rtt_ms: int | None = Field(None, ge=0, le=60_000)
    downlink_mbps: float | None = Field(None, ge=0, le=10_000)
    device_memory_gb: float | None = Field(None, ge=0, le=1024)
    cpu_cores: int | None = Field(None, ge=0, le=1024)
    viewport: Viewport
    pixel_ratio: float = Field(1, ge=0.1, le=10)
    language: str = Field("en", max_length=35)
    user_agent: str = Field("", max_length=200)
    touch: bool = False
    timezone: str | None = Field(None, max_length=64)
    color_scheme: Literal["dark", "light"] | None = None
    reduced_motion: bool = False
    forced_colors: bool = False

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, tz: str | None) -> str | None:
        return tz if tz in TIMEZONES else None  # an unknown zone would crash the browser; drop it instead


class ComplaintIn(BaseModel):
    kind: Literal["spoken", "rage_click", "js_error", "failed_request", "slow_request"]
    text: str = Field("", max_length=1000)
    page: str = Field("/", max_length=300)
    env: Env
    breadcrumbs: list[str] = Field(default_factory=list, max_length=20)


live: dict = {"stack": None, "url": "", "bug": None}
_tasks: set[asyncio.Task] = set()
# ponytail: one investigation at a time (each drives a real browser); add a worker pool if demand grows.
_investigation_lock = asyncio.Lock()


def start_live(bug: Bug | None = None) -> None:
    """(Re)start the live BadShop, optionally with one planted bug."""
    if live["stack"]:
        live["stack"].close()
    shop = reset_workspace(LIVE_SHOP)
    if bug:
        inject(bug, shop)
    stack = ExitStack()
    live.update(url=stack.enter_context(running_app(shop, LIVE_PORT)), stack=stack, bug=bug.id if bug else None)


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_dotenv()
    if os.getenv("START_LIVE_SHOP", "1") == "1":
        start_live()
    yield
    if live["stack"]:
        live["stack"].close()


app = FastAPI(title="Complaint Replay", lifespan=lifespan)
# The widget runs on customers' sites, so complaints arrive cross-origin. No cookies are used.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
_hits: dict[str, deque] = defaultdict(deque)


def rate_limited(ip: str) -> bool:
    # ponytail: in-memory per-process limiter; move to Redis if this runs on more than one worker.
    now, hits = time.monotonic(), _hits[ip]
    while hits and now - hits[0] > RATE_WINDOW_S:
        hits.popleft()
    if len(hits) >= RATE_LIMIT:
        return True
    hits.append(now)
    return False


def save_case(case: dict) -> None:
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    path = CASES_DIR / f"{case['id']}.json"
    if path.exists():
        # A running investigation holds its own copy of the case; reports merged into it meanwhile live only
        # on disk. Keep them, or the investigation's next save would wipe the "xN reports" count.
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        if on_disk.get("reports", 1) > case.get("reports", 1):
            case["reports"] = on_disk["reports"]
            case["also_reported"] = on_disk.get("also_reported", [])
    path.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")


def complaint_for_model(record: dict) -> str:
    said = record["text"] if record["kind"] == "spoken" else f"(The user typed nothing. Silent signal: {record['text']})"
    trail = "; ".join(record["breadcrumbs"][-6:])
    return f"{said}\nPage: {record['page']}." + (f" What the user did just before: {trail}." if trail else "")


async def run_investigation(case: dict, env: dict) -> None:
    async with _investigation_lock:
        try:
            client = make_client()
            chat = Chat(client, await pick_model(client))
            await investigate(case, twin_condition(env), live["url"], LIVE_SHOP, client, chat, save_case,
                              CASES_DIR / "shots")
        except Exception as e:  # the case must show what went wrong instead of hanging in a stage
            log.exception("investigation %s failed", case["id"])
            case.update(stage="error", error=str(e)[:300])
            save_case(case)


def load_vectors() -> dict[str, list[float]]:
    return json.loads(VECTORS.read_text(encoding="utf-8")) if VECTORS.exists() else {}


async def group_into_existing(record: dict, cond) -> tuple[str | None, list[float] | None]:
    """Attach a complaint to the open case it duplicates, so one bug gets one investigation and a count."""
    text = record["text"] or record["kind"]
    try:
        cases = {c["id"]: c for c in list_cases()}
        said = {cid: c.get("said") or c["complaint"] for cid, c in cases.items()}
        cid, vec = await find_duplicate(make_client(), text, load_vectors(), said)
    except Exception:  # grouping is an optimisation: if it fails, investigate the complaint on its own
        log.exception("duplicate check failed")
        return None, None
    if cid:
        case = cases[cid]
        case["reports"] = case.get("reports", 1) + 1
        case.setdefault("also_reported", []).append(
            {"said": record["text"], "kind": record["kind"], "condition": cond.label, "at": record["received_at"]})
        save_case(case)
    return cid, vec


@app.post("/api/complaints", status_code=201)
async def receive(complaint: ComplaintIn, request: Request) -> dict:
    if rate_limited(request.client.host if request.client else "unknown"):
        raise HTTPException(429, "too many complaints, slow down")
    record = complaint.model_dump()
    record["text"] = mask_pii(record["text"])
    record["breadcrumbs"] = [mask_pii(b)[:80] for b in record["breadcrumbs"]]
    record["id"] = uuid.uuid4().hex[:12]
    record["received_at"] = datetime.now(timezone.utc).isoformat()
    STORE.parent.mkdir(exist_ok=True)
    with STORE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    if live["url"]:
        cond = twin_condition(record["env"])
        duplicate, vec = await group_into_existing(record, cond)
        if duplicate:
            return {"id": record["id"], "grouped_into": duplicate}
        case = {"id": record["id"], "created_at": record["received_at"], "kind": record["kind"],
                "complaint": complaint_for_model(record), "said": record["text"],
                "condition": {"label": cond.label, "persona": cond.persona}, "stage": "heard"}
        save_case(case)
        if vec:
            vectors = load_vectors()
            vectors[case["id"]] = vec
            VECTORS.write_text(json.dumps(vectors), encoding="utf-8")
        task = asyncio.create_task(run_investigation(case, record["env"]))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    return {"id": record["id"]}


@app.get("/api/cases")
def list_cases() -> list[dict]:
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in CASES_DIR.glob("*.json")] if CASES_DIR.exists() else []
    return sorted(cases, key=lambda c: c.get("created_at", ""), reverse=True)


@app.get("/api/live")
def live_state() -> dict:
    return {"url": live["url"], "broken": live["bug"] is not None}


@app.post("/api/break")
def break_it() -> dict:
    """Plant a random bug in the live shop. The id stays secret: finding it is the tool's job."""
    choices = [b for b in BUGS if b.id != live["bug"]]
    start_live(random.choice(choices))
    return {"broken": True}


@app.post("/api/reset")
def reset_live() -> dict:
    start_live()
    return {"broken": False}


@app.get("/api/complaints")
def list_complaints() -> list[dict]:
    if not STORE.exists():
        return []
    return [json.loads(line) for line in STORE.read_text(encoding="utf-8").splitlines() if line.strip()]


@app.get("/widget.js")
def widget() -> FileResponse:
    return FileResponse(HERE / "widget.js", media_type="text/javascript")


app.mount("/shots", StaticFiles(directory=CASES_DIR / "shots", check_dir=False), name="shots")
if DASHBOARD_DIST.exists():  # mounted last so /api routes win
    app.mount("/", StaticFiles(directory=DASHBOARD_DIST, html=True), name="dashboard")
