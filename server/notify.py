"""Tell the team when a complaint turns into something worth their time, in their chat.

Any Slack-compatible incoming webhook works: Slack, Mattermost, Rocket.Chat, and Discord (add /slack to its URL).
"""

import json
import logging
import urllib.request

log = logging.getLogger("complaint-replay")
# Only stages a person should act on; "reproducing" or "fixing" every few seconds would be noise.
WORTH_SAYING = {
    "reproduced": "Bug proven",
    "guarded": "Fixed, proven and guarded: a pull request is waiting for review",
    "fixed": "Fixed and proven",
    "fix_failed": "Bug proven, but the automatic fix could not be applied: it needs a person",
    "fix_unproven": "Bug proven, but the automatic fix did not hold: it needs a person",
    "not_reproduced": "Could not reproduce",
}


def message(case: dict, project: dict, dashboard: str) -> str:
    said = " ".join((case.get("said") or case.get("complaint") or "").split())[:200]
    reports = f" ({case['reports']} people)" if case.get("reports", 1) > 1 else ""
    lines = [f"*{WORTH_SAYING[case['stage']]}* in {project['name']}{reports}", f"> {said}",
             f"Who: {case.get('condition', {}).get('persona', '')}"]
    if case.get("pr"):
        lines.append(f"Pull request: {case['pr']}")
    if case.get("issue"):
        lines.append(f"Issue: {case['issue']}")
    lines.append(f"Case: {dashboard}")
    return "\n".join(lines)


def send(url: str, text: str) -> None:
    """Best effort: a chat being down must never break a replay."""
    req = urllib.request.Request(url, json.dumps({"text": text}).encode(), {"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except OSError as e:
        log.warning("notification to the team's chat failed: %s", e)
