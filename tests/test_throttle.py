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


def test_own_model_server_wins_when_configured(monkeypatch) -> None:
    from replay.llm import make_client

    monkeypatch.setenv("REPLAY_BASE_URL", "http://10.0.0.5:8000/v1")
    monkeypatch.setenv("NEBIUS_API_KEY", "k")
    assert str(make_client().base_url).startswith("http://10.0.0.5:8000/v1")


def test_busy_model_server_is_retried_patiently() -> None:
    import asyncio

    from openai import InternalServerError

    from replay.llm import patiently

    calls, waits = [], []
    busy = InternalServerError.__new__(InternalServerError)  # a 503 "ResourceExhausted", without building a response

    async def call():
        calls.append(1)
        if len(calls) < 3:
            raise busy
        return "ok"

    async def sleep(s):
        waits.append(s)

    assert asyncio.run(patiently(call, sleep)) == "ok" and waits == [30, 60]


def test_default_model_is_nemotron_super_not_a_nano_model(monkeypatch) -> None:
    import asyncio
    from types import SimpleNamespace

    from replay.llm import pick_model

    monkeypatch.delenv("REPLAY_MODEL", raising=False)
    ids = ["nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", "nvidia/nemotron-3-super-120b-a12b", "nvidia/nemotron-nano-9b"]

    class Models:
        async def list(self):
            return SimpleNamespace(data=[SimpleNamespace(id=i) for i in ids])

    assert asyncio.run(pick_model(SimpleNamespace(models=Models()))) == "nvidia/nemotron-3-super-120b-a12b"
