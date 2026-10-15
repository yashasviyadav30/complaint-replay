"""The PR step builds a bot-authored branch with the fix and the guard, without touching the checkout."""

import subprocess

from replay.pr import body, open_pr

CASE = {
    "id": "abc123", "complaint": "OTP never comes", "said": "OTP never comes",
    "condition": {"label": "Slow 3G", "persona": "A user on slow 3G."},
    "replay": {"evidence": [{"id": "E1", "kind": "request_failed", "detail": "POST /api/otp failed"}], "cited": ["E1"],
               "steps": [{"action": {"type": "click"}, "target": "Send OTP", "result": "ok"}]},
    "fix": {"explanation": "Timeout too short.", "edits": [{"file": "app.js", "find": "4000", "replace": "30000"}]},
    "guard": {"file": ".complaint-replay/guards/abc123.json", "test": {"steps": []}, "passes_on_fix": True,
              "catches_bug": True},
}


def git(repo, *args) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


def test_pr_branch_holds_fix_and_guard_and_leaves_checkout_alone(tmp_path) -> None:
    (tmp_path / "app.js").write_text("const TIMEOUT = 4000;\n", encoding="utf-8")
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "add", "-A")
    git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    branch = open_pr(tmp_path, CASE, push=False)
    assert git(tmp_path, "log", "-1", "--format=%an", branch).strip() == "Complaint Replay"
    changed = git(tmp_path, "show", "--name-only", "--format=", branch).split()
    assert changed == [".complaint-replay/guards/abc123.json", "app.js"]
    assert "30000" in git(tmp_path, "show", f"{branch}:app.js")
    assert git(tmp_path, "status", "--short") == "" and "4000" in (tmp_path / "app.js").read_text()


def test_pr_body_shows_proof_and_guard() -> None:
    text = body(CASE)
    assert "`request_failed` POST /api/otp failed" in text and "Fails on the old code: **yes**" in text


def test_pr_target_is_origin_even_when_a_fork_has_an_upstream(tmp_path) -> None:
    from replay.pr import origin_slug

    git(tmp_path, "init", "-q")
    git(tmp_path, "remote", "add", "upstream", "https://github.com/someone-else/project.git")
    git(tmp_path, "remote", "add", "origin", "git@github.com:me/my-copy.git")
    assert origin_slug(tmp_path) == "me/my-copy"


def test_user_text_cannot_ping_people_or_break_out_of_the_quote() -> None:
    from replay.pr import quoted

    assert quoted("hi @octocat\n# Fixes #1\n![x](http://evil)") == "hi @​octocat # Fixes #1 [x](http://evil)"
