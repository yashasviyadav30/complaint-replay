# Evidence kinds

Each evidence line from `replay_complaint` or `run_guards` has a kind in square brackets. Code watching the browser
records them; the model can only cite them. Use this table to explain a line to the user and to know where to look
in the code.

| Kind | What the browser saw | Where the fix usually is |
|---|---|---|
| `request_failed` | A request never got an answer (network error, dropped) | Retry, timeout or error handling around that call |
| `http_error` | The server answered 4xx or 5xx | The API route, or what the page sent it |
| `slow_request` | A request took far longer than the rest | The endpoint, or a timeout set too short on the client |
| `no_response` | The page gave no feedback after an action | The click handler; add a loading or error state |
| `error_after_wait` | An error appeared only after a slow user waited (e.g. a code or session expired) | Timeouts and expiry times |
| `stuck_loading` | A spinner was still showing after 15 seconds | The request behind the spinner, or its error path |
| `redirect_loop` | The page kept redirecting | Auth or routing guards |
| `slow_page` | The page was slow to show content (web vitals) | Page weight, blocking scripts |
| `layout_shift` | Content jumped while loading | Reserve space for images, ads and late content |
| `console_error` | A JavaScript error in the console | The script and line it names |
| `offscreen_control` | A control is outside the screen | CSS: fixed widths, `nowrap`, missing media queries |
| `covered_control` | Something else covers a control | z-index, overlays, sticky bars |
| `clipped_text` | Text is cut off | Fixed heights, `overflow: hidden`, long translations |
| `page_overflow` | The page is wider than the screen | An element with a fixed width |
| `broken_image` | An image did not load | The image path or host |
| `tap_blocked` | A tap hit a different element than intended | Overlapping elements, `pointer-events` |
| `wrong_option_chosen` | Enter or a tap picked another option than the user meant | Select or autocomplete handling |
| `typed_value_lost` | What the user typed vanished | Controlled inputs reset by a re-render |
| `picker_not_opened` | A date or other picker never opened | The picker's trigger on touch devices |
| `a11y_violation` | An axe-core WCAG 2.2 AA failure (rule id given) | The element named in the line |
| `unclear_name` | A control is announced only as "1", "+" or similar | Add an `aria-label` or visible text |
| `focus_invisible` | Keyboard focus cannot be seen | `:focus-visible` styles |
| `not_keyboard_reachable` | A control cannot be reached with Tab | Use a real `button` or link, or add `tabindex` |
| `language_mismatch` | A message is not in the user's language | Missing translation keys |
| `rtl_missing` | A right-to-left page is laid out left to right | `dir="rtl"` and logical CSS properties |
| `duplicate_request` | The same request was sent twice | Disable the button while the first one runs |
| `charged_twice` | The same payment went through twice | An idempotency key on the payment call |
| `amount_mismatch` | Amounts disagree between API calls | Rounding, currency or stale cart totals |
| `check:<name>` | A project's own rule from `checks` in `complaint-replay.toml` failed | What that check describes |
