"""Any web app as a replay target, described by a small `complaint-replay.toml` in its repo.

    [app]
    start = "npm run dev -- --port {port}"   # how to run it from the repo root; {port} is filled in
    ready = "/"                              # path that answers once the app is up
    # url = "https://staging.example.com"    # or: replay a running site instead of starting one
    hints = "Test account: demo@example.com / demo1234"   # facts the twin may need (test data)
    auth = ".complaint-replay/auth.json"     # optional saved login (crp auth)
    edit = ["src/**"]                        # optional: files the fixer may change

No config file at all means: a static site served from the repo root.
"""

import os
import signal
import socket
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

CONFIG = "complaint-replay.toml"
SECRET_WORDS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
START_TIMEOUT_S = int(os.getenv("CRP_START_TIMEOUT", "120"))  # a cold `npm run dev` can take a while


@dataclass(frozen=True)
class Project:
    root: Path
    start: str = "{python} -m http.server {port} --bind 127.0.0.1"
    url: str = ""
    ready: str = "/"
    hints: str = ""
    auth: str = ""
    edit: tuple[str, ...] = ()
    checks: tuple[str, ...] = ()  # your own evidence: JS files, each `() => [problem, ...]`, run on every page

    @property
    def check_scripts(self) -> dict[str, str]:
        """{name: JavaScript} for the project's own checks; a missing file is a config error, said loudly."""
        return {Path(c).stem: (self.root / c).read_text(encoding="utf-8") for c in self.checks}

    @property
    def auth_file(self) -> Path | None:
        path = self.root / self.auth if self.auth else None
        return path if path and path.is_file() else None


def load_project(root: Path) -> Project:
    root = Path(root).resolve()
    path = root / CONFIG
    app = tomllib.loads(path.read_text(encoding="utf-8")).get("app", {}) if path.exists() else {}
    known = {k: v for k, v in app.items() if k in Project.__dataclass_fields__ and k != "root"}
    for key in ("edit", "checks"):
        if key in known:
            known[key] = tuple(known[key])
    return Project(root, **known)


def app_env() -> dict[str, str]:
    """The app under test never sees model keys or the GitHub token: it is untrusted code on a fix branch."""
    return {k: v for k, v in os.environ.items() if not any(w in k.upper() for w in SECRET_WORDS)}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _kill_tree(proc: subprocess.Popen) -> None:
    """A shell-started dev server spawns children; stopping only the shell leaves the port taken."""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def _wait_ready(url: str, proc: subprocess.Popen | None, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except urllib.error.HTTPError:  # the server answered; a 404 on the ready path still means it is up
            return
        except OSError:
            if (proc and proc.poll() is not None) or time.monotonic() > deadline:
                raise RuntimeError(f"app did not start: {url} never answered")
            time.sleep(0.3)


@contextmanager
def running_app(root: Path, port: int | None = None) -> Iterator[str]:
    """Run the app in `root` (its own config says how) and yield its base URL.

    A free port by default, so a test run never talks to the live demo by accident.
    """
    project = load_project(root)
    if project.url:
        _wait_ready(project.url.rstrip("/") + project.ready, None, 30)
        yield project.url.rstrip("/")
        return
    port = port or free_port()
    url = f"http://127.0.0.1:{port}"
    cmd = project.start.format(port=port, python=f'"{sys.executable}"')
    # CRP_APP_LOG=<file>: keep the app's own output, to see why it did not start.
    log = open(os.environ["CRP_APP_LOG"], "a", encoding="utf-8") if os.getenv("CRP_APP_LOG") else subprocess.DEVNULL
    proc = subprocess.Popen(cmd, shell=True, cwd=project.root, start_new_session=os.name != "nt", env=app_env(),
                            stdout=log, stderr=subprocess.STDOUT)
    try:
        _wait_ready(url + project.ready, proc, START_TIMEOUT_S)
        yield url
    finally:
        _kill_tree(proc)
        if log is not subprocess.DEVNULL:
            log.close()
