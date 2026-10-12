import pytest
from fastapi.testclient import TestClient

import server.app as srv
from replay.conditions import twin_condition

ENV = {"effective_type": "3g", "rtt_ms": 1800, "viewport": {"width": 360, "height": 740},
       "language": "hi-IN", "user_agent": "Mozilla/5.0 (Linux; Android 11) Mobile", "touch": True}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(srv, "STORE", tmp_path / "complaints.jsonl")
    srv._hits.clear()
    return TestClient(srv.app)


def test_complaint_is_stored_with_pii_masked(client) -> None:
    text = "OTP not coming on 9876543210, mail me at a.b@example.com, order 123456789012"
    r = client.post("/api/complaints", json={"kind": "spoken", "text": text, "env": ENV})
    assert r.status_code == 201
    stored = client.get("/api/complaints").json()[0]
    assert stored["text"] == "OTP not coming on [phone], mail me at [email], order [number]"
    assert stored["received_at"]


def test_rejects_unknown_kind_and_huge_text(client) -> None:
    assert client.post("/api/complaints", json={"kind": "hack", "env": ENV}).status_code == 422
    assert client.post("/api/complaints", json={"kind": "spoken", "text": "x" * 1001, "env": ENV}).status_code == 422


def test_rate_limit(client) -> None:
    codes = [client.post("/api/complaints", json={"kind": "rage_click", "env": ENV}).status_code
             for _ in range(srv.RATE_LIMIT + 1)]
    assert codes[-1] == 429 and codes[0] == 201


def test_serves_widget(client) -> None:
    r = client.get("/widget.js")
    assert r.status_code == 200 and "Report a problem" in r.text


def test_twin_copies_the_reporters_conditions() -> None:
    cond = twin_condition(ENV)
    assert cond.context["viewport"] == {"width": 360, "height": 740}
    assert cond.context["locale"] == "hi-IN" and cond.context["is_mobile"]
    assert cond.network == {"latency": 1800}
    assert cond.hindi


def test_twin_on_fast_desktop_keeps_its_small_real_latency() -> None:
    cond = twin_condition({"effective_type": "4g", "rtt_ms": 50, "viewport": {"width": 1280, "height": 800}})
    assert cond.network == {"latency": 50}
    assert not cond.context["is_mobile"]
