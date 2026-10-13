# Feedback for Nebius and NVIDIA (the "Most Valuable Feedback" field)

Everything below happened while building this project.

1. **Card required to start, even with hackathon credits.** Token Factory asked for card details before any use. Many students in India don't have an international card, and a lost debit card stopped me for days. The docs disagree on this: one billing page says a card is mandatory, a newer one says it isn't. Suggestion: let a hackathon code unlock credits without a card, with a hard cap at the credit amount.

2. **Budget alerts don't cap spending.** Nebius budgets send emails but don't stop usage, and a card on file is charged when the balance goes negative. For a student trying a free credit that is scary. A "stop when credits run out" switch would remove the fear.

3. **Thinking models can return an empty answer.** With default settings, Nemotron spent the whole `max_tokens` on reasoning and returned empty `content`, with no error. It cost me a full test run to notice. A warning when reasoning uses up the budget, or a doc note next to the `enable_thinking` flag, would save hours.

4. **Models listed but not callable.** On NVIDIA's API catalog, some Nemotron models appear in `/models` but return 404 when called (for example `nvidia/nemotron-nano-3-30b-a3b`). Either hide them or return a clear "not available for your account" message.

5. **What worked well.** The OpenAI-compatible API meant switching between endpoints was one line. Nemotron 3 Super was fast enough to drive a browser step by step and good at root-cause fixes: it found the real cause in every bug I planted, usually in one line.
