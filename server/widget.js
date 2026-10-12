/* Complaint Replay widget: one <script> tag on any site.
 * Sends spoken complaints ("Report a problem") and silent ones (rage clicks, JS errors,
 * failed or very slow requests), each with the user's real conditions.
 * Never sends what the user typed into fields: only button/link names.
 */
(() => {
  const script = document.currentScript;
  const ENDPOINT = new URL("/api/complaints", script.src).href;
  const origFetch = window.fetch.bind(window); // the widget's own calls are never watched
  const SLOW_MS = 8000;
  const RAGE_CLICKS = 3, RAGE_WINDOW_MS = 1000, RAGE_RADIUS_PX = 30;
  const breadcrumbs = [];
  const sentSilent = new Set();

  const label = (el) => {
    const target = el.closest("button, a, [role=button], input, select, label") || el;
    const fieldLabel = target.labels && target.labels[0] && target.labels[0].innerText;
    const text = target.getAttribute("aria-label") || fieldLabel || target.innerText || target.placeholder || target.tagName;
    return (text || "").trim().replace(/\s+/g, " ").slice(0, 60);
  };

  const env = () => {
    const c = navigator.connection || {};
    return {
      effective_type: c.effectiveType || null,
      rtt_ms: typeof c.rtt === "number" ? c.rtt : null,
      downlink_mbps: typeof c.downlink === "number" ? c.downlink : null,
      device_memory_gb: navigator.deviceMemory || null,
      cpu_cores: navigator.hardwareConcurrency || null,
      viewport: { width: innerWidth, height: innerHeight },
      pixel_ratio: devicePixelRatio,
      language: navigator.language,
      user_agent: navigator.userAgent.slice(0, 200),
      touch: navigator.maxTouchPoints > 0,
    };
  };

  const send = (kind, text) => {
    const body = JSON.stringify({ kind, text: (text || "").slice(0, 1000), page: location.pathname,
                                  env: env(), breadcrumbs: breadcrumbs.slice(-10) });
    return origFetch(ENDPOINT, { method: "POST", headers: { "Content-Type": "application/json" }, body, keepalive: true })
      .catch(() => {}); // the widget must never break the host page
  };
  const sendSilentOnce = (kind, key, text) => {
    if (sentSilent.has(kind + key)) return;
    sentSilent.add(kind + key);
    send(kind, text);
  };

  // Breadcrumbs + rage clicks
  let clicks = [];
  addEventListener("click", (e) => {
    if (e.target.closest("#cr-widget")) return;
    breadcrumbs.push("clicked " + label(e.target));
    const now = Date.now();
    clicks = clicks.filter((c) => now - c.t < RAGE_WINDOW_MS && Math.hypot(c.x - e.clientX, c.y - e.clientY) < RAGE_RADIUS_PX);
    clicks.push({ t: now, x: e.clientX, y: e.clientY });
    if (clicks.length >= RAGE_CLICKS) {
      sendSilentOnce("rage_click", label(e.target), `Rage-clicked "${label(e.target)}"`);
      clicks = [];
    }
  }, true);

  // JS errors
  addEventListener("error", (e) => sendSilentOnce("js_error", e.message, e.message));
  addEventListener("unhandledrejection", (e) => sendSilentOnce("js_error", String(e.reason), String(e.reason).slice(0, 300)));

  // Failed and slow requests
  window.fetch = async (input, init) => {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    const started = performance.now();
    try {
      const res = await origFetch(input, init);
      const ms = performance.now() - started;
      if (res.status >= 500) sendSilentOnce("failed_request", url.pathname, `${url.pathname} returned HTTP ${res.status}`);
      else if (ms > SLOW_MS) sendSilentOnce("slow_request", url.pathname, `${url.pathname} took ${Math.round(ms)} ms`);
      return res;
    } catch (err) {
      sendSilentOnce("failed_request", url.pathname, `${url.pathname} failed after ${Math.round(performance.now() - started)} ms: ${err.name}`);
      throw err;
    }
  };

  // "Report a problem" button
  const ui = document.createElement("div");
  ui.id = "cr-widget";
  ui.innerHTML = `
    <style>
      #cr-widget{position:fixed;right:16px;bottom:16px;z-index:2147483647;font:14px/1.4 system-ui,sans-serif}
      #cr-widget button{min-height:44px;padding:8px 14px;border-radius:22px;border:0;background:#1d1b18;color:#fff;cursor:pointer}
      #cr-widget form{display:none;width:min(300px,calc(100vw - 32px));background:#fff;color:#1d1b18;border-radius:12px;padding:12px;box-shadow:0 8px 30px rgba(0,0,0,.25)}
      #cr-widget textarea{width:100%;min-height:80px;box-sizing:border-box;font:inherit;padding:8px;border:1px solid #ccc;border-radius:8px}
      #cr-widget form button{margin-top:8px;width:100%}
      #cr-widget[data-open] form{display:block} #cr-widget[data-open] > button{display:none}
    </style>
    <button type="button" aria-haspopup="dialog">Report a problem</button>
    <form aria-label="Report a problem">
      <label for="cr-text">What went wrong?</label>
      <textarea id="cr-text" maxlength="1000" required></textarea>
      <button type="submit">Send</button>
    </form>`;
  const open = ui.querySelector(":scope > button");
  const form = ui.querySelector("form");
  open.addEventListener("click", () => { ui.dataset.open = ""; ui.querySelector("textarea").focus(); });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    await send("spoken", form.querySelector("textarea").value);
    form.reset();
    delete ui.dataset.open;
    open.textContent = "Thanks, we're on it";
  });
  (document.body ? Promise.resolve() : new Promise((r) => addEventListener("DOMContentLoaded", r)))
    .then(() => document.body.append(ui));
})();
