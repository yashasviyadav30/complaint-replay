"""GitHub: send a complaint to the team's repo (their GitHub Action replays it), and log people in.

Two ways to reach a repo:
- A GitHub App (hosted service): one install click; tokens are short-lived and scoped to the repos chosen.
  Credentials come from GITHUB_APP_ID / GITHUB_APP_PRIVATE_KEY / GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET,
  or from results/github-app.json written by the one-click setup page (`/setup/github-app`).
- A personal token in GITHUB_TOKEN (self-hosting for one team).
"""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

API = "https://api.github.com"
APP_FILE = Path(__file__).resolve().parent.parent / "results" / "github-app.json"


class GitHubError(RuntimeError):
    pass


def call(method: str, path: str, token: str = "", body: dict | None = None) -> dict:
    req = urllib.request.Request(path if path.startswith("http") else API + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                                          "User-Agent": "complaint-replay", "Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise GitHubError(f"GitHub {method} {path} -> {e.code}: {e.read()[:300].decode(errors='replace')}") from e


def app_settings() -> dict:
    """GitHub App credentials, from the environment or from the setup page's saved file."""
    saved = json.loads(APP_FILE.read_text(encoding="utf-8")) if APP_FILE.exists() else {}
    return {
        "id": os.getenv("GITHUB_APP_ID") or str(saved.get("id") or ""),
        "slug": os.getenv("GITHUB_APP_SLUG") or saved.get("slug") or "",
        "pem": (os.getenv("GITHUB_APP_PRIVATE_KEY") or saved.get("pem") or "").replace("\\n", "\n"),
        "client_id": os.getenv("GITHUB_CLIENT_ID") or saved.get("client_id") or "",
        "client_secret": os.getenv("GITHUB_CLIENT_SECRET") or saved.get("client_secret") or "",
    }


def app_configured() -> bool:
    s = app_settings()
    return bool(s["id"] and s["pem"])


def login_configured() -> bool:
    s = app_settings()
    return bool(s["client_id"] and s["client_secret"])


def app_jwt() -> str:
    import jwt  # PyJWT

    s = app_settings()
    now = int(time.time())
    return jwt.encode({"iat": now - 60, "exp": now + 540, "iss": s["id"]}, s["pem"], algorithm="RS256")


def installation_token(repo: str) -> str:
    """A one-hour token for the app's installation on `owner/name`."""
    inst = call("GET", f"/repos/{repo}/installation", app_jwt())
    return call("POST", f"/app/installations/{inst['id']}/access_tokens", app_jwt(), {})["token"]


def repo_token(repo: str) -> str:
    if app_configured():
        return installation_token(repo)
    if os.getenv("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    raise GitHubError("no way to reach GitHub: install the GitHub App or set GITHUB_TOKEN")


def dispatch(repo: str, payload: dict) -> None:
    """Start the repo's Complaint Replay workflow (repository_dispatch, event type 'complaint')."""
    call("POST", f"/repos/{repo}/dispatches", repo_token(repo), {"event_type": "complaint", "client_payload": payload})


def user_can_push(repo: str, user_token: str) -> bool:
    """Only people who can change a repo may connect it to a project."""
    try:
        perms = call("GET", f"/repos/{repo}", user_token).get("permissions", {})
    except GitHubError:
        return False
    return bool(perms.get("admin") or perms.get("maintain") or perms.get("push"))


# --- Log in with GitHub (the GitHub App's own OAuth) ---

def login_url(state: str, redirect: str) -> str:
    return "https://github.com/login/oauth/authorize?" + urlencode(
        {"client_id": app_settings()["client_id"], "state": state, "redirect_uri": redirect})


def exchange_code(code: str) -> str:
    s = app_settings()
    data = call("POST", "https://github.com/login/oauth/access_token",
                body={"client_id": s["client_id"], "client_secret": s["client_secret"], "code": code})
    if "access_token" not in data:
        raise GitHubError(f"login failed: {data.get('error_description') or data}")
    return data["access_token"]


def whoami(user_token: str) -> str:
    return call("GET", "/user", user_token)["login"]


# --- One-click GitHub App creation (manifest flow) ---

def manifest(base_url: str, name: str) -> dict:
    return {
        "name": name[:34],
        "url": "https://github.com/yashasviyadav30/complaint-replay",
        "hook_attributes": {"url": f"{base_url}/api/v1/github/webhook", "active": False},
        "redirect_url": f"{base_url}/setup/github-app/done",
        "callback_urls": [f"{base_url}/auth/callback"],
        "public": True,
        "default_permissions": {"contents": "write", "pull_requests": "write", "metadata": "read"},
        "default_events": [],
    }


def convert_manifest(code: str) -> dict:
    """GitHub returns the new app's id, key and secrets exactly once; save them for this server."""
    data = call("POST", f"/app-manifests/{code}/conversions")
    saved = {k: data.get(k) for k in ("id", "slug", "pem", "client_id", "client_secret")}
    APP_FILE.parent.mkdir(parents=True, exist_ok=True)
    APP_FILE.write_text(json.dumps(saved), encoding="utf-8")
    return saved
