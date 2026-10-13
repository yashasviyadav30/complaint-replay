import asyncio

import replay.llm as llm


def test_throttle_waits_once_the_minute_is_full(monkeypatch) -> None:
    monkeypatch.setenv("REPLAY_MAX_RPM", "2")
    monkeypatch.setattr(llm, "_calls", llm.deque())
    clock = [100.0]
    slept = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(round(seconds, 2))
        clock[0] += seconds

    async def three_calls() -> None:
        for _ in range(3):
            await llm.throttle(now=lambda: clock[0], sleep=fake_sleep)

    asyncio.run(three_calls())
    assert slept == [60.05]  # the third call waited for the first one to leave the 60 s window


def test_no_limit_on_token_factory(monkeypatch) -> None:
    monkeypatch.delenv("REPLAY_MAX_RPM", raising=False)
    monkeypatch.setenv("NEBIUS_API_KEY", "x")
    assert llm.max_rpm() == 0
