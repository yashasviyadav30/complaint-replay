# Demo video script for the real product (target 2:50, limit 3:00) - DRAFT

Replaces `video-script.md` (v0, BadShop only). Every shot is a real run, recorded from the screen. Record on
Oct 26-27 per plan.md, after the Token Factory key is in, so the captions can say "on Nebius Token Factory".
Numbers marked {..} come from the final benchmark run; fill them in, never estimate.

| Time | On screen | Voice-over or caption |
|---|---|---|
| 0:00-0:12 | A phone in Hindi. The user taps "🎤 बोलकर बताएँ" and speaks: "मैं स्क्रीन रीडर से फ़ोन चलाता हूँ... कार्ट का बटन सिर्फ 'बटन' बोलता है"; the words appear in the box. Cut to a developer laptop where the cart looks fine. | A blind user says, in Hindi, that the cart button only says "button". On the developer's laptop, nothing looks wrong. |
| 0:12-0:20 | Title: Complaint Replay. "Your users already told you what's broken." | Complaint Replay turns that complaint into a pull request. |
| 0:20-0:45 | Setup on a fresh repo: copy the script tag, run `crp init`, install the GitHub App. A timer in the corner. | Setup: one script tag, one workflow, one install. Under ten minutes. |
| 0:45-1:25 | The complaint arrives on the board, "Sent to your CI". GitHub Actions log: "Replaying as: ... the user says they use a screen reader". Stages move: Reproducing, Reproduced, Fixing, Proving, Guarded. | It runs in the team's own GitHub Actions, so the code never leaves their CI. Nemotron read "screen reader" in Hindi, so the twin uses one. |
| 1:25-1:35 | Dashboard case view: press **Listen**. The browser reads the screen aloud: "BadShop, heading level 1. Button. Shop, heading level 2..." | This is what a blind user hears. Which button is the cart? |
| 1:35-1:55 | The pull request: proof from the browser ("a button is announced only as '(nothing)'" and axe's "Buttons must have discernible text"), the one-line fix, the two films side by side (red "Found", green "the problem is gone"), CI green on the fix and "catches the bug on main". | The proof comes from the browser, not the model. NVIDIA Nemotron on Nebius Token Factory writes the fix, the same steps prove it on film, and a guard test keeps it from coming back. |
| 1:55-2:05 | The widget on the phone now says "Fixed..." in Hindi, with "अब इसे ठीक चलते हुए देखें"; tap it: the green film plays. | And the person who complained hears back, and can watch it working. |
| 2:05-2:20 | Quick cuts: an issue labelled `replay` getting a reply; Claude Code calling `replay_complaint` and `run_guards` over MCP; the Arabic right-to-left widget. | It works from GitHub issues, support desks and Sentry, in any language, and coding agents can drive it too. |
| 2:20-2:45 | `benchmarks/real-bugs.md`: real bugs from Actual Budget, re-created from their real fixes. Show the table, misses included: {solved} of 8. | We tested it on real bugs from a real app, not only on bugs we planted. It solved {solved} of 8, and every miss taught it something. |
| 2:45-2:55 | Repo link, Apache 2.0, "Built with NVIDIA Nemotron on Nebius Token Factory". | Open source. Try it on your app. |

Captions-only version: one line per row, 6 to 10 words, at least 2 seconds each.

Recorded material already real (Oct 17): films `results/cases/shots/bug-4-*.gif` (Pay button off a 360 px screen)
and `bug-10-*.gif` + the bug-10 transcript (screen reader). Shots to capture with `scripts/record_demo.py`: the board moving, the GitHub Actions log, PR #4 (Hindi) or a fresh
one, the widget status on a 360 px phone, the issue reply on demo issue #5.
