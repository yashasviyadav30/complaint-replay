"""Record the real demo flow as video clips for the submission video.

Starts the live service, plants the coupon bug, shops and complains like a customer, then films the case
moving across the board until it is guarded. Nothing is faked: the waiting is real and gets cut in editing.
Existing cases are set aside so the board starts empty, then put back (the new case is kept too).
Run: uv run python scripts/record_demo.py      -> video/raw/board.webm, video/raw/shop.webm
"""

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "video" / "raw"
CASES = ROOT / "results" / "cases"
ASIDE = ROOT / "results" / "cases-aside"
SERVICE = "http://127.0.0.1:8200"
SIZE = {"width": 1600, "height": 900}
DONE = {"guarded", "fixed", "fix_unproven", "fix_failed", "not_reproduced", "ux_confusion", "error"}
CASE_TIMEOUT_S = 600


def api(path: str, method: str = "GET") -> dict | list:
    req = urllib.request.Request(SERVICE + path, method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def plant_coupon_bug() -> None:
    live_app = ROOT / "workspace" / "live" / "badshop" / "app.py"
    for _ in range(40):
        api("/api/break", "POST")
        if '"charged": subtotal' in live_app.read_text(encoding="utf-8"):
            return
    raise RuntimeError("could not plant the coupon bug")


async def shop_and_complain(page) -> None:
    await page.goto("http://127.0.0.1:8100")
    await page.wait_for_timeout(1500)
    await page.locator("#phone").press_sequentially("9876543210", delay=60)
    await page.click("#send-otp")
    await page.wait_for_selector("#otp-step:not([hidden])", timeout=20000)
    await page.locator("#otp").press_sequentially("123456", delay=80)
    await page.click("#verify-otp")
    await page.wait_for_selector("#products button")
    await page.wait_for_timeout(800)
    await page.get_by_role("button", name="Add Basmati Rice 1kg").click()
    await page.wait_for_timeout(600)
    await page.click("#cart-btn")
    await page.wait_for_timeout(1000)
    await page.locator("#coupon").press_sequentially("SAVE10", delay=90)
    await page.click("#apply-coupon")
    await page.wait_for_timeout(1500)  # let the viewer read "Total: 162"
    await page.click("#pay")
    await page.wait_for_timeout(2500)  # "Amount charged: 180"
    await page.click("#cr-widget > button")
    await page.locator("#cr-text").press_sequentially(
        "I used SAVE10 and the cart said 162 but you charged me 180?? that's cheating", delay=35)
    await page.wait_for_timeout(600)
    await page.click("#cr-widget form button")
    await page.wait_for_timeout(2000)


async def film(case_timeout_s: int) -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(viewport=SIZE, record_video_dir=str(RAW), record_video_size=SIZE)
        board = await ctx.new_page()
        await board.goto(SERVICE)
        await board.wait_for_timeout(2500)
        await board.click("text=Break It")  # the visible press
        await board.wait_for_timeout(2000)
        plant_coupon_bug()  # make sure the secret bug is the coupon one, the only one a desktop user can hit

        shop = await ctx.new_page()
        await shop_and_complain(shop)

        await board.bring_to_front()
        started = time.monotonic()
        cases: list = []
        while time.monotonic() - started < case_timeout_s:
            cases = api("/api/cases")
            if cases and cases[0]["stage"] in DONE:
                break
            await board.wait_for_timeout(3000)
        print("final stage:", cases[0]["stage"] if cases else None, flush=True)
        await board.wait_for_timeout(3000)
        await board.locator("main section button").first.click()  # open the case card (not the notice)
        await board.wait_for_timeout(2500)
        for _ in range(12):
            await board.locator("aside").evaluate("el => el.scrollBy({top: 260, behavior: 'smooth'})")
            await board.wait_for_timeout(1200)
        names = {"board": await board.video.path(), "shop": await shop.video.path()}
        await ctx.close()  # flushes the videos
        await browser.close()
    for name, path in names.items():
        Path(path).rename(RAW / f"{name}.webm")


def main() -> None:
    shutil.rmtree(RAW, ignore_errors=True)
    RAW.mkdir(parents=True)
    shutil.rmtree(ASIDE, ignore_errors=True)
    if CASES.exists():
        shutil.move(str(CASES), str(ASIDE))
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    # Own process group so Ctrl+Break shuts uvicorn down gracefully; that runs the lifespan, which stops
    # the live shop. A hard terminate on Windows left the shop orphaned, holding ports and pipes.
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "server.app:app", "--port", "8200",
                               "--log-level", "warning"], cwd=ROOT, env=env,
                              creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    try:
        for _ in range(60):
            try:
                api("/api/live")
                break
            except OSError:
                time.sleep(1)
        asyncio.run(film(CASE_TIMEOUT_S))
    finally:
        server.send_signal(signal.CTRL_BREAK_EVENT)
        try:
            server.wait(timeout=20)
        except subprocess.TimeoutExpired:
            server.kill()
        if ASIDE.exists():  # put the earlier cases back next to the new one
            CASES.mkdir(parents=True, exist_ok=True)
            shutil.copytree(ASIDE, CASES, dirs_exist_ok=True)
            shutil.rmtree(ASIDE)
    print("clips:", sorted(p.name for p in RAW.glob("*.webm")))


if __name__ == "__main__":
    main()
