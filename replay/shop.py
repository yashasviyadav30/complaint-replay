"""Start the BadShop working copy as a real server."""

import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def running_shop(shop_dir: Path, port: int | None = None) -> Iterator[str]:
    """A free port by default, so a test run never talks to the live shop by accident."""
    port = port or free_port()
    url = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--app-dir", str(shop_dir),
         "--port", str(port), "--log-level", "warning"],
    )
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                urllib.request.urlopen(f"{url}/api/products", timeout=1)
                break
            except OSError:
                if proc.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("BadShop server did not start")
                time.sleep(0.2)
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)
