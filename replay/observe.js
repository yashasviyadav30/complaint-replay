// What the user can see and use right now, plus layout facts the evidence collectors check.
// Runs in the page. Marks each usable control with data-bc-idx so actions can address it.
() => {
  const OURS = '#cr-widget';
  const vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight;
  const visible = (el) => {
    const s = getComputedStyle(el), r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0
      && (el.offsetParent !== null || s.position === 'fixed');
  };
  // aria-label plus visible text, so a sighted user's view of badges/counts ("Cart 3") is kept
  const name = (el) => {
    const parts = [el.getAttribute('aria-label'), el.innerText || el.value || el.placeholder || el.title
      || (el.labels && el.labels[0] && el.labels[0].innerText) || el.getAttribute('alt')]
      .map((s) => (s || '').trim()).filter(Boolean);
    return [...new Set(parts)].join(' ').replace(/\s+/g, ' ').slice(0, 60);
  };
  const ours = (el) => el.closest(OURS) !== null;
  document.querySelectorAll('[data-bc-idx]').forEach((el) => el.removeAttribute('data-bc-idx'));

  const CONTROLS = 'button, a[href], input:not([type=hidden]), select, textarea, summary, [role=button], [role=link], '
    + '[role=tab], [role=menuitem], [role=checkbox], [role=radio], [role=switch], [role=option], [role=combobox]';
  const elements = [], offscreen = [], covered = [], clipped = [];
  let i = 0;
  for (const el of document.querySelectorAll(CONTROLS)) {
    if (ours(el) || !visible(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.left >= vw || r.right <= 0) { offscreen.push({ label: name(el), left: Math.round(r.left), vw }); continue; }
    el.setAttribute('data-bc-idx', i);
    elements.push({ idx: i++, tag: el.tagName.toLowerCase(), role: el.getAttribute('role') || '', label: name(el),
      value: (el.type === 'password' ? '' : el.value) || '', disabled: !!el.disabled });
    // Covered: fully on screen, yet the point at its centre belongs to something else (overlay, banner).
    if (r.top >= 0 && r.bottom <= vh && r.left >= 0 && r.right <= vw) {
      const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      if (top && top !== el && !el.contains(top) && !top.contains(el) && !ours(top)) {
        const cls = typeof top.className === 'string' && top.className ? '.' + top.className.split(' ')[0] : '';
        covered.push({ label: name(el), by: (top.id ? '#' + top.id : top.tagName.toLowerCase()) + cls });
      }
    }
    // Clipped: the text is wider than the box that hides the overflow ("Pay no..." on a small phone).
    const s = getComputedStyle(el);
    if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0 && (s.overflowX !== 'visible' || s.textOverflow === 'ellipsis')) {
      clipped.push({ label: name(el), needs: el.scrollWidth, has: el.clientWidth });
    }
  }

  // Looks clickable (pointer cursor) but a keyboard can never reach it.
  const unreachable = [];
  for (const el of document.querySelectorAll('div, span, li, img, svg, td')) {
    if (unreachable.length >= 5 || ours(el) || !visible(el)) continue;
    if (getComputedStyle(el).cursor !== 'pointer' || el.tabIndex >= 0) continue;
    if (el.closest(CONTROLS) || el.querySelector(CONTROLS)) continue;
    if (el.parentElement && getComputedStyle(el.parentElement).cursor === 'pointer') continue;
    unreachable.push(name(el) || el.tagName.toLowerCase());
  }

  const brokenImages = [...document.images].filter((img) => !ours(img) && visible(img) && img.complete && img.naturalWidth === 0)
    .slice(0, 5).map((img) => img.getAttribute('src') || '');
  const busy = [...document.querySelectorAll('[aria-busy=true], [role=progressbar], [class*=spinner], [class*=loader], [class*=loading]')]
    .filter((el) => !ours(el) && visible(el)).slice(0, 5)
    .map((el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + '.' + String(el.className).split(' ')[0]);
  const alerts = [...document.querySelectorAll('[role=alert], [aria-live], .error, .alert, [class*=toast]')]
    .filter((e) => !ours(e) && visible(e)).map((e) => e.innerText.trim()).filter(Boolean);
  const active = document.activeElement && document.activeElement !== document.body ? document.activeElement : null;
  let focus = null;
  if (active && !ours(active)) {
    const s = getComputedStyle(active);
    focus = { label: name(active), tag: active.tagName.toLowerCase(),
      outline: !(s.outlineStyle === 'none' || parseFloat(s.outlineWidth) === 0) || s.boxShadow !== 'none' };
  }
  return {
    url: location.pathname, vw, elements, offscreen, covered, clipped, unreachable, brokenImages, busy, alerts, focus,
    overflow: document.documentElement.scrollWidth - vw,
    lang: document.documentElement.lang || '', dir: getComputedStyle(document.body).direction,
    vitals: window.__crp || null,
    text: document.body.innerText.slice(0, 1200),
  };
}
