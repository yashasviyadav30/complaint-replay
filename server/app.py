"""Complaint Replay service: receives complaints from the widget and serves it.

Run: uv run uvicorn server.app:app --port 8200
"""

import json
import re
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

HERE = Path(__file__).resolve().parent
STORE = HERE.parent / "results" / "complaints.jsonl"
RATE_LIMIT, RATE_WINDOW_S = 30, 60

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


class ComplaintIn(BaseModel):
    kind: Literal["spoken", "rage_click", "js_error", "failed_request", "slow_request"]
    text: str = Field("", max_length=1000)
    page: str = Field("/", max_length=300)
    env: Env
    breadcrumbs: list[str] = Field(default_factory=list, max_length=20)


app = FastAPI(title="Complaint Replay")
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


@app.post("/api/complaints", status_code=201)
def receive(complaint: ComplaintIn, request: Request) -> dict:
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
    return {"id": record["id"]}


@app.get("/api/complaints")
def list_complaints() -> list[dict]:
    if not STORE.exists():
        return []
    return [json.loads(line) for line in STORE.read_text(encoding="utf-8").splitlines() if line.strip()]


@app.get("/widget.js")
def widget() -> FileResponse:
    return FileResponse(HERE / "widget.js", media_type="text/javascript")
