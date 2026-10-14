# Demo video script (target 2:40, limit 3:00)

Record a working run now, not near the deadline. Everything on screen must be a real run.

## Version A: with voice-over (about 330 words, about 130 words per minute)

| Time | On screen | Voice-over |
|---|---|---|
| 0:00-0:12 | A customer complaint in the widget: "OTP never comes!!". Cut to a fast laptop where login works fine. | A customer says the OTP never comes. The developer tries it on a fast laptop. It works. Complaint closed. Customer gone. |
| 0:12-0:22 | Title card: "Complaint Replay". One line under it. | Complaint Replay turns that complaint into proof, a fix, and a test. Here it is, live. |
| 0:22-0:40 | Dashboard. Press Break It. Open the store in a new tab. | I press Break It. That plants a secret bug in this store. I don't know which one. |
| 0:40-1:05 | Use the store as a customer: log in, add rice, coupon SAVE10, Pay. The total says 162, the charge says 180. Open the widget and type the complaint. | I shop like a customer. Coupon applied, cart says 162. But I was charged 180. So I complain, in my own words. |
| 1:05-1:30 | Back to the board. The card appears in Heard, live indicator "Replaying as this user". It moves to Reproduced. | The complaint lands on the board. An AI twin opens a real browser with my screen, my language, my network, and repeats exactly what I did. |
| 1:30-1:50 | Open the case. Screenshot, then the evidence card "Money mismatch: quote said 162, checkout charged 180", marked "cited as proof". | It found the bug. Not because the model says so. The browser caught the cart and the checkout disagreeing. That's the only kind of proof it accepts. |
| 1:50-2:10 | The fix section: Nemotron's explanation and the one-line diff. Card moves to Fixed, then Guarded. Show the guard section with both green lines. | NVIDIA Nemotron on Nebius Token Factory reads the evidence and the code, and writes a one-line fix. The same twin replays it on the fixed code. Then the replay is saved as a test that fails on the old code. |
| 2:10-2:25 | Quick cuts: Hindi error case, off-screen Pay button on a 360 px phone, screen-reader cart button. | It works for slow phones, small screens, Hindi users and screen readers. |
| 2:25-2:38 | README results table. | Seven bugs, three runs each. Twenty-one reproduced, twenty fixed, zero false alarms. |
| 2:38-2:45 | Repo link and name. | Your angriest users are your best testers. I'm Yashasvi. Thanks for watching. |

## Version B: captions only (no voice)

Use the same shots. Put one short caption on screen for each row, 6 to 10 words, for at least 2 seconds:

1. "OTP never comes!!" ... works on my laptop.
2. Complaint Replay: complaint in, proof, fix and test out.
3. Planting a secret bug.
4. Shopping like a customer. Cart 162, charged 180.
5. An AI twin replays it with my real conditions.
6. Proof comes from the browser, not the model.
7. Nemotron on Nebius Token Factory writes the fix.
8. Proven on the fixed code. Saved as a test.
9. Slow phones, small screens, Hindi, screen readers.
10. 21/21 reproduced. 20/21 fixed. 0 false alarms.

## Recording checklist

- Clean Chrome window, no bookmarks bar, no other tabs, 1920x1080, zoom 110% so text is readable.
- `.env` and terminal hidden. No API key on screen at any point.
- Live service running; old cases cleared so the board starts empty.
- Do one silent practice run first. The twin takes about a minute per case, so cut the waiting, don't fake it.
- Upload as public on YouTube, under 3:00. Open the link in a private window to check.
