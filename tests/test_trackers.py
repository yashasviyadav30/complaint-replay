"""Linear and Jira get the issue in the shape their APIs document (no live accounts in tests)."""

import io
import json

from replay import trackers


class Fake:
    def __init__(self, reply: dict):
        self.reply, self.sent = reply, None

    def __call__(self, req, timeout):
        self.sent = (req.full_url, dict(req.header_items()), json.loads(req.data))
        return io.BytesIO(json.dumps(self.reply).encode())


def test_nothing_is_sent_without_credentials(monkeypatch) -> None:
    for k in ("LINEAR_API_KEY", "LINEAR_TEAM_ID", "JIRA_URL"):
        monkeypatch.delenv(k, raising=False)
    assert trackers.linear("t", "b") is None and trackers.jira("t", "b") is None


def test_linear_issue_create(monkeypatch) -> None:
    monkeypatch.setenv("LINEAR_API_KEY", "lin_key")
    monkeypatch.setenv("LINEAR_TEAM_ID", "team-1")
    fake = Fake({"data": {"issueCreate": {"success": True, "issue": {"url": "https://linear.app/x/issue/WEB-7"}}}})
    assert trackers.linear("bug: pay", "proof", fake) == "https://linear.app/x/issue/WEB-7"
    url, headers, body = fake.sent
    assert url == trackers.LINEAR_API and headers["Authorization"] == "lin_key"
    assert body["variables"]["input"] == {"teamId": "team-1", "title": "bug: pay", "description": "proof"}


def test_jira_issue_create(monkeypatch) -> None:
    for k, v in {"JIRA_URL": "https://acme.atlassian.net/", "JIRA_EMAIL": "a@b.c", "JIRA_API_TOKEN": "t",
                 "JIRA_PROJECT": "WEB"}.items():
        monkeypatch.setenv(k, v)
    fake = Fake({"key": "WEB-42"})
    assert trackers.jira("bug: pay", "proof", fake) == "https://acme.atlassian.net/browse/WEB-42"
    url, headers, body = fake.sent
    assert url.endswith("/rest/api/2/issue") and headers["Authorization"].startswith("Basic ")
    assert body["fields"]["project"] == {"key": "WEB"} and body["fields"]["issuetype"] == {"name": "Bug"}
