"""Send a proven bug that needs a person to the team's tracker: Linear or Jira, besides GitHub issues.

Set in the repo's Action secrets (or your shell):
  LINEAR_API_KEY + LINEAR_TEAM_ID
  JIRA_URL (https://you.atlassian.net) + JIRA_EMAIL + JIRA_API_TOKEN + JIRA_PROJECT (key, e.g. WEB)
Not yet tried against live accounts: the requests follow each API's documented shape and are unit-tested.
"""

import base64
import json
import os
import urllib.request

LINEAR_API = "https://api.linear.app/graphql"
LINEAR_CREATE = "mutation($input: IssueCreateInput!) { issueCreate(input: $input) { success issue { url } } }"


def _post(url: str, body: dict, headers: dict, opener=urllib.request.urlopen) -> dict:
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **headers})
    with opener(req, timeout=20) as resp:
        return json.loads(resp.read() or b"{}")


def linear(title: str, body: str, opener=urllib.request.urlopen) -> str | None:
    if not (os.getenv("LINEAR_API_KEY") and os.getenv("LINEAR_TEAM_ID")):
        return None
    data = _post(LINEAR_API, {"query": LINEAR_CREATE, "variables": {"input": {
        "teamId": os.environ["LINEAR_TEAM_ID"], "title": title, "description": body}}},
        {"Authorization": os.environ["LINEAR_API_KEY"]}, opener)
    return ((data.get("data") or {}).get("issueCreate") or {}).get("issue", {}).get("url")


def jira(title: str, body: str, opener=urllib.request.urlopen) -> str | None:
    need = ("JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_PROJECT")
    if not all(os.getenv(k) for k in need):
        return None
    base = os.environ["JIRA_URL"].rstrip("/")
    auth = base64.b64encode(f"{os.environ['JIRA_EMAIL']}:{os.environ['JIRA_API_TOKEN']}".encode()).decode()
    data = _post(f"{base}/rest/api/2/issue", {"fields": {
        "project": {"key": os.environ["JIRA_PROJECT"]}, "summary": title[:250], "description": body,
        "issuetype": {"name": "Bug"}}}, {"Authorization": f"Basic {auth}"}, opener)
    return f"{base}/browse/{data['key']}" if data.get("key") else None


def file_everywhere(title: str, body: str) -> list[str]:
    """Every tracker the team has set up; one failing must not stop the others."""
    links = []
    for create in (linear, jira):
        try:
            link = create(title, body)
        except OSError as e:
            print(f"  ({create.__name__} did not accept the issue: {e})")
            continue
        if link:
            links.append(link)
    return links
