# Design partners: draft (not sent)

For the user to send or adapt. Nothing here has been posted anywhere.

## Who to ask

Small teams (2-30 engineers) with a public web app and users on phones, slow networks or several languages:
Indian D2C shops, fintech and edtech startups, NGOs with public forms, open-source web apps with an issue tracker.
Five teams is the goal (plan.md, Phase 2).

## The message (short, for a founder or CTO)

> Hi {name}, I built Complaint Replay, an open-source tool that turns a user's complaint ("OTP never comes",
> "the pay button is missing on my phone") into a pull request. It replays the complaint in a real browser as
> that user (their phone, network, language, screen reader), proves the bug with evidence the browser records,
> writes the fix, and leaves a test in your CI so it can't come back. It runs in your own GitHub Actions, so your
> code never leaves your CI.
>
> I'm looking for five teams to try it free for a month and tell me what's wrong with it. Setup is one script tag
> and one workflow file, about ten minutes. Would {company} try it on its staging site?

## What a partner gets

- Setup help on a call, and a fix within a day for anything that blocks them.
- Every proven bug as a pull request with evidence, screenshots and a guard test.
- Their users' complaints in any language grouped, ranked by impact, and answered ("fixed") in the widget.

## What we ask

- Ten minutes of setup on a staging or preview site.
- A short call after two weeks: which PRs they merged, which they rejected and why.
- Permission to quote the numbers (merged PRs, time to first PR) without naming users.

## What to measure

- Time from install to first pull request.
- Pull requests merged vs rejected, and why rejected.
- Complaints proven vs "could not reproduce".
