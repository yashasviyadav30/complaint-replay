from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import server.app as srv
from replay.conditions import twin_condition
from server.intake import mask_pii
from server.store import Store

ENV = {"effective_type": "3g", "rtt_ms": 1800, "viewport": {"width": 360, "height": 740},
       "language": "hi-IN", "user_agent": "Mozilla/5.0 (Linux; Android 11) Mobile", "touch": True}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(srv, "store", Store(f"sqlite:///{tmp_path / 'db.sqlite'}"))
    monkeypatch.setattr(srv.github, "login_configured", lambda: False)

    async def no_grouping(*_):
        return None, None

    monkeypatch.setattr(srv, "group_into_existing", no_grouping)  # no model calls in unit tests
    srv._hits.clear()
    srv.ensure_demo()
    return TestClient(srv.app)


def test_complaint_is_stored_with_pii_masked(client) -> None:
    text = "OTP not coming on 9876543210, mail me at a.b@example.com, order 123456789012"
    r = client.post("/api/complaints", json={"kind": "spoken", "text": text, "env": ENV})
    assert r.status_code == 201
    stored = client.get("/api/complaints").json()[0]
    assert stored["text"] == "OTP not coming on [phone], mail me at [email], order [number]"
    assert stored["received_at"] and "status_token" not in stored


@pytest.mark.parametrize("raw,masked", [
    ("मेरा नंबर ९८७६५४३२१० है", "मेरा नंबर [phone] है"),           # Devanagari digits
    ("call +44 20 7946 0958 please", "call [phone] please"),
    ("PAN ABCDE1234F", "PAN [tax id]"),
    ("aadhaar 1234 5678 9012", "aadhaar [id number]"),
    ("card 4111 1111 1111 1111 failed", "card [number] failed"),
    ("the total was 499 rupees", "the total was 499 rupees"),           # small numbers stay
])
def test_pii_masking_across_formats_and_scripts(raw, masked) -> None:
    assert mask_pii(raw) == masked


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


def test_reporter_can_follow_their_report_only_with_their_token(client) -> None:
    r = client.post("/api/v1/reports", json={"project": "demo", "kind": "spoken", "text": "Pay is missing", "env": ENV})
    body = r.json()
    assert client.get(f"/api/v1/reports/{body['id']}", params={"token": body["token"]}).json()["status"] == "received"
    assert client.get(f"/api/v1/reports/{body['id']}", params={"token": "guess"}).status_code == 404


def test_unknown_project_key_and_foreign_site_are_refused(client) -> None:
    report = {"kind": "spoken", "text": "x", "env": ENV}
    assert client.post("/api/v1/reports", json={"project": "nope", **report}).status_code == 404
    project = client.post("/api/v1/projects", json={"name": "Shop", "origins": ["https://shop.example"]}).json()
    ok = client.post("/api/v1/reports", json={"project": project["key"], **report},
                     headers={"Origin": "https://shop.example"})
    bad = client.post("/api/v1/reports", json={"project": project["key"], **report},
                      headers={"Origin": "https://evil.example"})
    assert ok.status_code == 201 and bad.status_code == 403


def test_projects_belong_to_their_owner(client) -> None:
    created = client.post("/api/v1/projects", json={"name": "Shop", "repo": "acme/shop"})
    assert created.status_code == 201 and created.json()["key"].startswith("crp_")
    names = [p["name"] for p in client.get("/api/v1/projects").json()]
    assert names == ["BadShop demo", "Shop"]


def test_action_progress_needs_the_case_token(client) -> None:
    r = client.post("/api/v1/reports", json={"project": "demo", "kind": "spoken", "text": "Pay missing", "env": ENV})
    case_id = r.json()["id"]
    url = f"/api/v1/cases/{case_id}/progress"
    assert client.post(url, json={"stage": "guarded"}, headers={"Authorization": "Bearer x"}).status_code == 403
    update = {"stage": "guarded", "guard": {"file": "g.json", "test": {"steps": []}}, "pr": "https://github.com/a/b/pull/1"}
    good = client.post(url, json=update, headers={"Authorization": f"Bearer {srv.case_token(case_id)}"})
    case = client.get(f"/api/v1/cases/{case_id}").json()
    assert good.status_code == 200 and case["stage"] == "guarded" and case["pr"].endswith("/pull/1")
    assert "test" not in case["guard"]
    status = client.get(f"/api/v1/reports/{case_id}", params={"token": r.json()["token"]}).json()
    assert status["status"] == "fixed"


def test_a_running_investigation_does_not_wipe_merged_reports(client) -> None:
    in_memory = {"id": "c1", "project": "demo", "stage": "reproducing"}  # the investigation's own copy
    srv.save_case(dict(in_memory))
    srv.save_case({**in_memory, "reports": 2, "also_reported": [{"said": "same bug"}]})
    srv.save_case({**in_memory, "stage": "fixing"})  # stale copy saves later
    saved = srv.store.get("case", "c1")
    assert saved["stage"] == "fixing" and saved["reports"] == 2 and saved["also_reported"] == [{"said": "same bug"}]


def test_old_reports_and_cases_are_deleted_after_the_retention_period(client) -> None:
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    srv.store.put("case", {"id": "old", "project": "demo", "created_at": old})
    srv.store.put("case", {"id": "new", "project": "demo", "created_at": srv.now()})
    srv.sweep_once()
    assert srv.store.get("case", "old") is None and srv.store.get("case", "new")


def test_impact_ranks_money_bugs_with_many_reports_first() -> None:
    from server.intake import impact

    money = {"reports": 3, "replay": {"cited": ["E1"], "evidence": [{"id": "E1", "kind": "duplicate_request"}]}}
    image = {"reports": 3, "replay": {"cited": ["E1"], "evidence": [{"id": "E1", "kind": "broken_image"}]}}
    assert impact(money) == 15 and impact(image) == 3 and impact({}) == 1


def test_twin_copies_the_reporters_conditions() -> None:
    cond = twin_condition(ENV)
    assert cond.context["viewport"] == {"width": 360, "height": 740}
    assert cond.context["locale"] == "hi-IN" and cond.context["is_mobile"]
    assert cond.network == {"latency": 1800}
    assert cond.locale == "hi-IN" and not cond.rtl


def test_twin_on_fast_desktop_keeps_its_small_real_latency() -> None:
    cond = twin_condition({"effective_type": "4g", "rtt_ms": 50, "viewport": {"width": 1280, "height": 800}})
    assert cond.network == {"latency": 50}
    assert not cond.context["is_mobile"]


def test_twin_copies_timezone_dark_mode_and_rtl() -> None:
    env = {**ENV, "language": "ar-EG", "timezone": "Africa/Cairo", "color_scheme": "dark", "reduced_motion": True}
    cond = twin_condition(env)
    assert cond.context["timezone_id"] == "Africa/Cairo" and cond.context["color_scheme"] == "dark"
    assert cond.context["reduced_motion"] == "reduce" and cond.rtl


def test_unknown_timezone_is_dropped_not_crashed_on() -> None:
    assert srv.Env(viewport={"width": 400, "height": 800}, timezone="Africa/Cairo").timezone == "Africa/Cairo"
    assert srv.Env(viewport={"width": 400, "height": 800}, timezone="Mars/Olympus").timezone is None


def test_what_the_user_says_about_themselves_joins_the_measured_conditions() -> None:
    from replay.conditions import with_needs

    cond = with_needs(twin_condition(ENV), {"screen_reader": True, "keyboard_only": False, "zoom": 1.0})
    assert cond.screen_reader and not cond.keyboard_only and cond.context["locale"] == "hi-IN"
    assert "uses a screen reader" in cond.persona
    assert with_needs(twin_condition(ENV), {}) == twin_condition(ENV)


def test_spam_is_kept_but_not_replayed(client, monkeypatch) -> None:
    async def grouping_with_vector(*_):
        return None, [1.0, 0.0]

    monkeypatch.setattr(srv, "group_into_existing", grouping_with_vector)
    monkeypatch.setattr(srv, "classify", lambda vec: {"label": "spam", "margin": 0.4, "replay": False})
    started = []

    async def fake_start(*args):
        started.append(args)

    monkeypatch.setattr(srv, "start_case", fake_start)
    r = client.post("/api/v1/reports", json={"project": "demo", "kind": "spoken", "text": "buy followers", "env": ENV})
    case = srv.store.get("case", r.json()["id"])
    assert case["stage"] == "not_a_bug" and case["triage"]["label"] == "spam" and not started
