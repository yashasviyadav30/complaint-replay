import { Bug, ChatText, HandTap, Hourglass, WifiSlash, type Icon } from "@phosphor-icons/react";
import type { Case, Kind, Stage } from "./types";

export const KIND: Record<Kind, { label: string; icon: Icon }> = {
  spoken: { label: "Complaint", icon: ChatText },
  rage_click: { label: "Rage click", icon: HandTap },
  js_error: { label: "Page error", icon: Bug },
  failed_request: { label: "Failed request", icon: WifiSlash },
  slow_request: { label: "Slow request", icon: Hourglass },
};

export const STAGE: Record<Stage, { label: string; busy?: boolean; tone?: "ok" | "accent" | "muted" }> = {
  heard: { label: "Heard", tone: "muted" },
  queued: { label: "Sent to your CI", busy: true },
  reproducing: { label: "Replaying as this user", busy: true },
  reproduced: { label: "Bug proven", tone: "accent" },
  not_reproduced: { label: "Could not reproduce", tone: "muted" },
  ux_confusion: { label: "Works, but confusing", tone: "accent" },
  fixing: { label: "Nemotron is writing a fix", busy: true },
  proving: { label: "Replaying on the fix", busy: true },
  fixed: { label: "Fix proven", tone: "ok" },
  fix_unproven: { label: "Fix did not hold", tone: "accent" },
  fix_failed: { label: "Fix could not be applied", tone: "accent" },
  guarded: { label: "Guarded by a test", tone: "ok" },
  error: { label: "Something broke", tone: "accent" },
  not_a_bug: { label: "Not a bug: not replayed", tone: "muted" },
};

export const EVIDENCE: Record<string, string> = {
  request_failed: "Request failed",
  http_error: "HTTP error",
  console_error: "Console error",
  offscreen_control: "Control off screen",
  language_mismatch: "Wrong language",
  a11y_violation: "Accessibility",
  amount_mismatch: "Money mismatch",
  duplicate_request: "Duplicate payment",
  covered_control: "Control covered",
  clipped_text: "Text cut off",
  page_overflow: "Page wider than screen",
  broken_image: "Image missing",
  slow_request: "Slow request",
  slow_page: "Slow page",
  layout_shift: "Layout jumped",
  stuck_loading: "Stuck loading",
  redirect_loop: "Redirect loop",
  rtl_missing: "Right-to-left missing",
  focus_invisible: "Focus not visible",
  not_keyboard_reachable: "Keyboard can't reach",
  unclear_name: "Unclear name",
  no_response: "Tap did nothing",
  tap_blocked: "Tap blocked",
};

export const LANGUAGE = new Intl.DisplayNames(undefined, { type: "language" });
export const languageName = (code?: string) => {
  if (!code) return "";
  try {
    return LANGUAGE.of(code) ?? code;
  } catch {
    return code;
  }
};

export const whatTheySaid = (c: Case) => c.said || c.complaint;

export const twinSummary = (c: Case) => c.condition.persona.replace(/^The real user who reported this:\s*/, "").replace(/\.$/, "");

const RELATIVE = new Intl.RelativeTimeFormat(undefined, { style: "narrow", numeric: "auto" });

export function timeAgo(iso: string, now = Date.now()): string {
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 60) return RELATIVE.format(-s, "second");
  if (s < 3600) return RELATIVE.format(-Math.round(s / 60), "minute");
  if (s < 86400) return RELATIVE.format(-Math.round(s / 3600), "hour");
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(iso));
}
