"""Complaint Replay service: takes complaints from the widget on any site and gets each one replayed.

Every site is a project with its own widget key. A project linked to a GitHub repo has its complaints replayed
by that repo's own GitHub Action (the code never leaves the team's CI); progress comes back through a signed
callback. The built-in "demo" project replays complaints in-process against the live BadShop demo.

Run: uv run uvicorn server.app:app --port 8200
Docs for every endpoint: http://127.0.0.1:8200/docs
"""

import asyncio
import html
import json
import logging
import os
import random
import secrets
import time
from collections import defaultdict, deque
from contextlib import ExitStack, asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from zoneinfo import available_timezones

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from replay.bugs import BUGS, LIVE_SHOP, Bug, inject, reset_workspace
from replay.conditions import twin_condition
from replay.grouping import find_duplicate
from replay.langid import detect
from replay.project import running_app
from replay.triage import classify
from server import github
from server.intake import complaint_for_model, impact, mask_pii, sign, unsign
from server.store import Store

HERE = Path(__file__).resolve().parent
SHOTS_DIR = HERE.parent / "results" / "cases" / "shots"
DASHBOARD_DIST = HERE.parent / "dashboard" / "dist"
RATE_LIMIT, RATE_WINDOW_S = 30, 60
LIVE_PORT = int(os.getenv("LIVE_SHOP_PORT", "8100"))
RETENTION_SWEEP_S = 6 * 3600
DEMO = "demo"
COOKIE = "crp_session"
WEEK_S = 7 * 24 * 3600
MAX_PROGRESS_CHARS = 500_000
TIMEZONES = available_timezones()
# What the person who complained is told, by stage. The widget shows these in the user's language.
PUBLIC_STATUS = {
    "heard": "received", "queued": "received", "reproducing": "checking", "reproduced": "found",
    "fixing": "fixing", "proving": "fixing", "fixed": "fixed", "guarded": "fixed", "fix_unproven": "found",
    "fix_failed": "found", "not_reproduced": "not_reproduced", "ux_confusion": "found", "error": "received",
    "not_a_bug": "received",
}
log = logging.getLogger("complaint-replay")
store = Store()


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


class ReportIn(BaseModel):
    project: str = Field(DEMO, max_length=64)  # the widget key from the script tag
    kind: Literal["spoken", "rage_click", "js_error", "failed_request", "slow_request"]
    text: str = Field("", max_length=1000)
    page: str = Field("/", max_length=300)
    env: Env
    breadcrumbs: list[str] = Field(default_factory=list, max_length=20)


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    repo: str = Field("", max_length=140, pattern=r"^$|^[\w.-]+/[\w.-]+$")
    origins: list[str] = Field(default_factory=list, max_length=20)  # sites allowed to send reports
    sector: Literal["general", "ecommerce", "fintech", "public"] = "general"
    retention_days: int = Field(30, ge=1, le=365)
    screenshots: bool = True


# --- projects and cases ---

def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_demo() -> None:
    if not store.get("project", DEMO):
        store.put("project", {"id": DEMO, "name": "BadShop demo", "key": DEMO, "owner": "*", "mode": "local",
                              "repo": "", "origins": [], "sector": "ecommerce", "retention_days": 30,
                              "screenshots": True, "created_at": now()})


def project_by_key(key: str) -> dict:
    found = [p for p in store.all("project") if p["key"] == key]
    if not found:
        raise HTTPException(404, "unknown project key")
    return found[0]


def save_case(case: dict) -> dict:
    stored = store.get("case", case["id"])
    if stored and stored.get("reports", 1) > case.get("reports", 1):
        # A running investigation holds its own copy; reports merged into it meanwhile live only in the store.
        case["reports"] = stored["reports"]
        case["also_reported"] = stored.get("also_reported", [])
    case["impact"] = impact(case)
    case["updated_at"] = now()
    return store.put("case", case)


# --- running investigations ---

live: dict = {"stack": None, "url": "", "bug": None}
_tasks: set[asyncio.Task] = set()
# ponytail: one in-process investigation at a time (each drives a real browser); GitHub-linked projects
# run in their own CI and are not limited by this.
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


async def run_local(case: dict, env: dict) -> None:
    from replay.investigate import investigate
    from replay.llm import Chat, make_client, pick_model

    async with _investigation_lock:
        try:
            client = make_client()
            chat = Chat(client, await pick_model(client))
            await investigate(case, twin_condition(env), live["url"], LIVE_SHOP, client, chat, save_case, SHOTS_DIR)
        except Exception as e:  # the case must show what went wrong instead of hanging in a stage
            log.exception("investigation %s failed", case["id"])
            save_case({**case, "stage": "error", "error": str(e)[:300]})


def case_token(case_id: str) -> str:
    return sign(f"case:{case_id}")


async def start_case(project: dict, case: dict, env: dict, base_url: str) -> None:
    if project["mode"] == "local":
        if live["url"]:
            task = asyncio.create_task(run_local(case, env))
            _tasks.add(task)
            task.add_done_callback(_tasks.discard)
        return
    if not project.get("repo"):
        return  # collected only: the team replays by hand with `crp replay`
    payload = {"case_id": case["id"], "kind": case["kind"], "complaint": case["complaint"], "said": case["said"],
               "env": env, "reports": case.get("reports", 1), "token": case_token(case["id"]),
               "callback": f"{base_url}/api/v1/cases/{case['id']}/progress"}
    try:
        await asyncio.to_thread(github.dispatch, project["repo"], payload)
        save_case({**case, "stage": "queued"})
    except github.GitHubError as e:
        log.warning("dispatch to %s failed: %s", project["repo"], e)
        save_case({**case, "stage": "error", "error": f"Could not start the GitHub Action: {e}"[:300]})


async def group_into_existing(project_id: str, record: dict, label: str) -> tuple[str | None, list[float] | None]:
    """Attach a complaint to the open case it duplicates, so one bug gets one investigation and a count."""
    from replay.llm import make_client

    cases = {c["id"]: c for c in store.all("case", project=project_id)}
    vectors = {v["id"]: v["vector"] for v in store.all("vector", project=project_id) if v["id"] in cases}
    said = {cid: c.get("said") or c["complaint"] for cid, c in cases.items()}
    try:
        cid, vec = await find_duplicate(make_client(), record["text"] or record["kind"], vectors, said)
    except Exception:  # grouping is an optimisation: if it fails, investigate the complaint on its own
        log.exception("duplicate check failed")
        return None, None
    if cid:
        case = cases[cid]
        case["reports"] = case.get("reports", 1) + 1
        case.setdefault("also_reported", []).append(
            {"said": record["text"], "kind": record["kind"], "condition": label, "at": record["received_at"]})
        save_case(case)
    return cid, vec


def sweep_once() -> None:
    """Delete reports and cases older than each project's retention setting."""
    for project in store.all("project"):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=project.get("retention_days", 30))).isoformat()
        for kind in ("report", "case", "vector"):
            for doc in store.all(kind, project=project["id"]):
                if doc.get("created_at", now()) < cutoff:
                    store.delete(kind, doc["id"])
                    for shot in (doc.get("shots") or {}).values():
                        (SHOTS_DIR / shot).unlink(missing_ok=True)


async def retention_loop() -> None:
    while True:
        sweep_once()
        await asyncio.sleep(RETENTION_SWEEP_S)


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_dotenv()
    ensure_demo()
    if os.getenv("START_LIVE_SHOP", "1") == "1":
        start_live()
    sweeper = asyncio.create_task(retention_loop())
    yield
    sweeper.cancel()
    if live["stack"]:
        live["stack"].close()


app = FastAPI(title="Complaint Replay", lifespan=lifespan)
# The widget runs on customers' sites, so reports arrive cross-origin; per-project origin lists are checked below.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
_hits: dict[str, deque] = defaultdict(deque)


def rate_limited(key: str) -> bool:
    # ponytail: in-memory per-process limiter; move to Redis if this runs on more than one worker.
    t, hits = time.monotonic(), _hits[key]
    while hits and t - hits[0] > RATE_WINDOW_S:
        hits.popleft()
    if len(hits) >= RATE_LIMIT:
        return True
    hits.append(t)
    return False


def public_url(request: Request) -> str:
    return (os.getenv("PUBLIC_URL") or str(request.base_url)).rstrip("/")


def current_user(request: Request) -> str | None:
    if not github.login_configured():
        return "local"  # self-hosted without GitHub login: whoever can reach this server owns it
    return unsign(request.cookies.get(COOKIE, ""))


def require_user(request: Request) -> str:
    user = current_user(request)
    if not user:
        raise HTTPException(401, "log in with GitHub first")
    return user


def owned_project(project_id: str, user: str) -> dict:
    project = store.get("project", project_id)
    if not project or project["owner"] not in (user, "*"):
        raise HTTPException(404, "no such project")
    return project


# --- the widget ---

@app.post("/api/v1/reports", status_code=201)
async def receive_report(report: ReportIn, request: Request) -> dict:
    """A complaint (spoken or silent) from the widget, with the user's real conditions."""
    ip = request.client.host if request.client else "unknown"
    if rate_limited(ip) or rate_limited("project:" + report.project):
        raise HTTPException(429, "too many reports, slow down")
    project = project_by_key(report.project)
    origin = request.headers.get("origin", "")
    if project["origins"] and origin and origin not in project["origins"]:
        raise HTTPException(403, "this site is not allowed to send reports to this project")
    record = report.model_dump()
    record["text"] = mask_pii(record["text"])
    record["breadcrumbs"] = [mask_pii(b)[:80] for b in record["breadcrumbs"]]
    record.update(id=secrets.token_hex(6), project=project["id"], received_at=now(), created_at=now(),
                  status_token=secrets.token_urlsafe(16))
    record["lang"] = detect(record["text"])[0] if record["text"].strip() else ""
    cond = twin_condition(record["env"])
    duplicate, vec = await group_into_existing(project["id"], record, cond.label)
    record["case"] = duplicate or record["id"]
    store.put("report", record)
    if not duplicate:
        case = {"id": record["id"], "project": project["id"], "created_at": record["received_at"],
                "kind": record["kind"], "complaint": complaint_for_model(record), "said": record["text"],
                "lang": record["lang"], "page": record["page"],
                "condition": {"label": cond.label, "persona": cond.persona}, "stage": "heard"}
        if vec:
            store.put("vector", {"id": case["id"], "project": project["id"], "vector": vec, "created_at": now()})
            case["triage"] = classify(vec)
        if case.get("triage", {}).get("replay", True):
            save_case(case)
            await start_case(project, case, record["env"], public_url(request))
        else:  # spam or a clear feature wish: keep it for the team, don't spend a replay on it
            save_case({**case, "stage": "not_a_bug"})
    return {"id": record["id"], "token": record["status_token"], "grouped_into": duplicate}


@app.get("/api/v1/reports/{report_id}")
def report_status(report_id: str, token: str) -> dict:
    """What the person who complained may see: how far their report got. Needs the token they were given."""
    record = store.get("report", report_id)
    if not record or not secrets.compare_digest(record.get("status_token", ""), token):
        raise HTTPException(404, "no such report")
    case = store.get("case", record["case"]) or {}
    return {"status": PUBLIC_STATUS.get(case.get("stage", "heard"), "received"), "reports": case.get("reports", 1)}


@app.get("/widget.js")
def widget() -> FileResponse:
    return FileResponse(HERE / "widget.js", media_type="text/javascript")


# --- progress from the team's GitHub Action ---

@app.post("/api/v1/cases/{case_id}/progress")
async def case_progress(case_id: str, request: Request) -> dict:
    auth = request.headers.get("authorization", "").removeprefix("Bearer ")
    if not secrets.compare_digest(auth, case_token(case_id)):
        raise HTTPException(403, "bad case token")
    case = store.get("case", case_id)
    if not case:
        raise HTTPException(404, "no such case")
    raw = await request.body()
    if len(raw) > MAX_PROGRESS_CHARS:
        raise HTTPException(413, "progress update too large")
    update = json.loads(raw)
    if not isinstance(update, dict):
        raise HTTPException(422, "progress must be a JSON object")
    for key in ("stage", "condition", "replay", "fix", "proof", "guard", "shots", "pr", "error"):
        if key in update:
            case[key] = update[key]
    project = store.get("project", case["project"]) or {}
    if case.get("pr") and project.get("repo"):
        # Screenshots are committed to the pull request branch, not uploaded here: the code stays in GitHub.
        case["shot_base"] = (f"https://github.com/{project['repo']}/blob/complaint-replay/{case_id}/"
                             ".complaint-replay/shots")
    if isinstance(case.get("guard"), dict):
        case["guard"].pop("test", None)  # the full guard lives in the repo, not here
    if isinstance(case.get("fix"), dict):
        case["fix"].pop("edits", None)
    save_case(case)
    return {"ok": True}


# --- the dashboard ---

@app.get("/api/v1/me")
def me(request: Request) -> dict:
    return {"login": current_user(request), "login_enabled": github.login_configured(),
            "github_app": github.app_settings()["slug"] or None}


@app.get("/api/v1/projects")
def list_projects(user: str = Depends(require_user)) -> list[dict]:
    return sorted((p for p in store.all("project") if p["owner"] in (user, "*")), key=lambda p: p["created_at"])


@app.post("/api/v1/projects", status_code=201)
def create_project(body: ProjectIn, request: Request, user: str = Depends(require_user)) -> dict:
    if body.repo and github.login_configured():
        token = unsign(request.cookies.get(COOKIE + "_gh", "")) or ""
        if not github.user_can_push(body.repo, token):
            raise HTTPException(403, f"you need write access to {body.repo} to connect it")
    project = {"id": secrets.token_hex(5), "key": "crp_" + secrets.token_urlsafe(12), "owner": user,
               "mode": "github", "created_at": now(), **body.model_dump()}
    return store.put("project", project)


@app.get("/api/v1/projects/{project_id}/cases")
def project_cases(project_id: str, user: str = Depends(require_user)) -> list[dict]:
    owned_project(project_id, user)
    return sorted(store.all("case", project=project_id), key=lambda c: c.get("created_at", ""), reverse=True)


@app.get("/api/v1/cases/{case_id}")
def get_case(case_id: str, user: str = Depends(require_user)) -> dict:
    case = store.get("case", case_id)
    if not case:
        raise HTTPException(404, "no such case")
    owned_project(case["project"], user)
    return case


@app.post("/api/v1/cases/{case_id}/replay")
async def replay_again(case_id: str, request: Request, user: str = Depends(require_user)) -> dict:
    case = get_case(case_id, user)
    project = owned_project(case["project"], user)
    report = store.get("report", case_id) or {}
    if not report.get("env"):
        raise HTTPException(409, "this case has no recorded user conditions to replay")
    fresh = {k: v for k, v in case.items() if k not in ("replay", "fix", "proof", "guard", "shots", "pr", "error")}
    fresh["stage"] = "heard"
    save_case(fresh)
    await start_case(project, fresh, report["env"], public_url(request))
    return {"ok": True}


# --- logging in with GitHub, and creating the GitHub App in one click ---

@app.get("/auth/login")
def login(request: Request) -> RedirectResponse:
    if not github.login_configured():
        raise HTTPException(404, "GitHub login is not set up on this server")
    state = secrets.token_urlsafe(16)
    resp = RedirectResponse(github.login_url(state, public_url(request) + "/auth/callback"))
    resp.set_cookie("crp_state", state, max_age=600, httponly=True, samesite="lax", secure=True)
    return resp


@app.get("/auth/callback")
def auth_callback(code: str, state: str, request: Request) -> RedirectResponse:
    if not secrets.compare_digest(state, request.cookies.get("crp_state", "")):
        raise HTTPException(400, "login expired, try again")
    token = github.exchange_code(code)
    resp = RedirectResponse("/")
    resp.set_cookie(COOKIE, sign(github.whoami(token)), max_age=WEEK_S, httponly=True, samesite="lax", secure=True)
    resp.set_cookie(COOKIE + "_gh", sign(token), max_age=WEEK_S, httponly=True, samesite="lax", secure=True)
    return resp


@app.get("/auth/logout")
def logout() -> RedirectResponse:
    resp = RedirectResponse("/")
    resp.delete_cookie(COOKIE)
    resp.delete_cookie(COOKIE + "_gh")
    return resp


@app.get("/setup/github-app", response_class=HTMLResponse)
def setup_github_app(request: Request, user: str = Depends(require_user)) -> str:
    """One click: GitHub creates this server's App from a manifest, then sends its keys back here."""
    if github.app_configured():
        slug = github.app_settings()["slug"]
        return f"<p>The GitHub App is already set up: <a href='https://github.com/apps/{slug}'>open it</a>.</p>"
    manifest = json.dumps(github.manifest(public_url(request), os.getenv("GITHUB_APP_NAME", "Complaint Replay")))
    return ("<!doctype html><meta charset=utf-8><title>Create the GitHub App</title>"
            "<form action='https://github.com/settings/apps/new' method='post'>"
            f"<input type='hidden' name='manifest' value='{html.escape(manifest, quote=True)}'>"
            "<p>Complaint Replay needs a GitHub App to start replays in your repos and open pull requests.</p>"
            "<button>Create it on GitHub</button></form>")


@app.get("/setup/github-app/done", response_class=HTMLResponse)
def setup_github_app_done(code: str, user: str = Depends(require_user)) -> str:
    if github.app_configured():
        raise HTTPException(409, "the GitHub App is already set up")
    saved = github.convert_manifest(code)
    slug = html.escape(saved["slug"] or "")
    return (f"<p>Done. The app <b>{slug}</b> is saved on this server.</p>"
            f"<p><a href='https://github.com/apps/{slug}/installations/new'>Install it on your repos</a>, "
            "then restart the server.</p>")


# --- the built-in demo (BadShop) and the original endpoints the v0 dashboard uses ---

@app.post("/api/complaints", status_code=201)
async def receive_legacy(report: ReportIn, request: Request) -> dict:
    """v0 widget format: same as /api/v1/reports, always for the demo project."""
    report.project = DEMO
    return await receive_report(report, request)


@app.get("/api/complaints")
def list_demo_reports() -> list[dict]:
    reports = sorted(store.all("report", project=DEMO), key=lambda r: r["received_at"])
    return [{k: v for k, v in r.items() if k != "status_token"} for r in reports]


@app.get("/api/cases")
def list_demo_cases() -> list[dict]:
    return sorted(store.all("case", project=DEMO), key=lambda c: c.get("created_at", ""), reverse=True)


@app.get("/api/live")
def live_state() -> dict:
    return {"url": live["url"], "broken": live["bug"] is not None}


@app.post("/api/break")
def break_it() -> dict:
    """Plant a random bug in the live shop. The id stays secret: finding it is the tool's job."""
    start_live(random.choice([b for b in BUGS if b.id != live["bug"]]))
    return {"broken": True}


@app.post("/api/reset")
def reset_live() -> dict:
    start_live()
    return {"broken": False}


app.mount("/shots", StaticFiles(directory=SHOTS_DIR, check_dir=False), name="shots")
if DASHBOARD_DIST.exists():  # mounted last so /api routes win
    app.mount("/", StaticFiles(directory=DASHBOARD_DIST, html=True), name="dashboard")
