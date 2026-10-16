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
  // A control with no name of its own (a bare toggle) is described by the text beside it, so it can be found.
  const nearText = (el) => {
    for (let a = el.parentElement, i = 0; a && i < 3; a = a.parentElement, i++) {
      const t = (a.innerText || '').trim().replace(/\s+/g, ' ');
      if (t) return t.slice(0, 40);
    }
    return '';
  };
  const ours = (el) => el.closest(OURS) !== null;
  // Where a control sits, in words a person would use: helps tell two similar bugs apart.
  const PLACES = { nav: 'the navigation', header: 'the top bar', footer: 'the footer', aside: 'a side panel',
    dialog: 'a dialog', form: 'a form', navigation: 'the navigation', banner: 'the top bar' };
  const where = (el) => {
    const land = el.closest('nav, header, footer, aside, dialog, form, [role=dialog], [role=navigation], [role=banner]');
    const place = land ? (land.getAttribute('role') === 'dialog' ? 'a dialog'
      : PLACES[land.getAttribute('role')] || PLACES[land.tagName.toLowerCase()] || '') : '';
    let near = '';
    for (let a = el.parentElement, i = 0; a && i < 5 && !near; a = a.parentElement, i++) {
      const h = a.querySelector('h1, h2, h3, h4, h5, h6, [class*=title]');
      if (h && !h.contains(el)) near = h.innerText.trim().replace(/\s+/g, ' ').slice(0, 40);
    }
    return [place && 'in ' + place, near && "near '" + near + "'"].filter(Boolean).join(', ');
  };
  document.querySelectorAll('[data-bc-idx]').forEach((el) => el.removeAttribute('data-bc-idx'));

  const CONTROLS = 'button, a[href], input:not([type=hidden]), select, textarea, summary, [role=button], [role=link], '
    + '[role=tab], [role=menuitem], [role=checkbox], [role=radio], [role=switch], [role=option], [role=combobox]';
  // An open dialog is meant to cover the page: then only controls inside it are checked for being covered.
  const modal = [...document.querySelectorAll('dialog[open], [aria-modal=true], [role=dialog], .modal.show, .offcanvas.show')]
    .find((d) => !ours(d) && visible(d));
  const elements = [], offscreen = [], covered = [], clipped = [], unnamed = [], els = [];
  let i = 0;
  for (const el of document.querySelectorAll(CONTROLS)) {
    if (ours(el) || !visible(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.left >= vw || r.right <= 0) { offscreen.push({ label: name(el), left: Math.round(r.left), vw, where: where(el) }); continue; }
    el.setAttribute('data-bc-idx', i);
    els.push(el);
    elements.push({ idx: i++, tag: el.tagName.toLowerCase(), role: el.getAttribute('role') || '',
      label: name(el) || (nearText(el) ? `(no name) near '${nearText(el)}'` : ''),
      value: (el.type === 'password' ? '' : el.value) || '', disabled: !!el.disabled });
    // A name with no letters ("1", "+", "x") tells a screen-reader user nothing about what the control does.
    if (!['input', 'select', 'textarea'].includes(el.tagName.toLowerCase()) && !/\p{L}/u.test(name(el))) {
      unnamed.push({ label: name(el), tag: el.tagName.toLowerCase(), where: where(el) });
    }
    // Covered: fully on screen, yet the point at its centre belongs to something else (overlay, banner).
    if ((!modal || modal.contains(el)) && r.top >= 0 && r.bottom <= vh && r.left >= 0 && r.right <= vw) {
      const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      // Something from the control's own parent on top is usually by design (drag handles, overlaid labels).
      // Fixed page chrome (top bar, bottom tabs) over a scrolled list is how apps are built, not a bug.
      const chrome = top && top.closest('nav, header, footer, [role=navigation], [role=banner], [role=tablist], [role=toolbar]');
      const row = el.parentElement;
      const sameParent = row && row !== document.body && row.contains(top)
        && row.getBoundingClientRect().height < 3 * r.height + 40;  // a row, not the whole page
      if (top && top !== el && !el.contains(top) && !top.contains(el) && !ours(top) && !sameParent && !chrome) {
        const cls = typeof top.className === 'string' && top.className ? '.' + top.className.split(' ')[0] : '';
        covered.push({ label: name(el), by: (top.id ? '#' + top.id : top.tagName.toLowerCase()) + cls, where: where(el) });
      }
    }
    // Clipped: the text is wider than the box that hides the overflow ("Pay no..." on a small phone).
    const s = getComputedStyle(el);
    if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0 && (s.overflowX !== 'visible' || s.textOverflow === 'ellipsis')) {
      clipped.push({ label: name(el), needs: el.scrollWidth, has: el.clientWidth, where: where(el) });
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

  // A switch drawn as a <label> for a hidden checkbox (0x0, opacity 0) is what the user taps. Without this, the
  // Cleared and Reconciled switches on Actual's transaction screen were missing from the list (cloud case 8733).
  for (const lab of document.querySelectorAll('label[for]')) {
    const box = document.getElementById(lab.getAttribute('for'));
    if (!box || ours(lab) || !visible(lab) || visible(box) || !['checkbox', 'radio'].includes(box.type)) continue;
    lab.setAttribute('data-bc-idx', i);
    els.push(lab);
    elements.push({ idx: i++, tag: box.type === 'radio' ? 'radio' : 'switch', role: 'switch',
      label: (box.getAttribute('aria-label') || '').trim() || name(lab) || (nearText(lab) ? `(no name) near '${nearText(lab)}'` : ''),
      value: box.checked ? 'on' : 'off', disabled: !!box.disabled });
  }

  // Several controls with one name ("✓" on every row) can't be told apart: add their row. The twin ticked the same
  // checkbox six times believing it was selecting several transactions (cloud case 8765).
  const counts = {};
  elements.forEach((e) => { counts[e.label] = (counts[e.label] || 0) + 1; });
  elements.forEach((e, k) => {
    if (counts[e.label] < 2) return;
    const row = els[k].closest('[role=row], tr, li, [data-testid=row]');
    const text = row ? row.innerText.trim().replace(/\s+/g, ' ').slice(0, 50) : '';
    if (text && text !== e.label) e.label = `${e.label} in row '${text}'`;
  });

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
    url: location.pathname, vw, elements, offscreen, covered, clipped, unnamed, unreachable, brokenImages, busy, alerts, focus,
    overflow: document.documentElement.scrollWidth - vw,
    lang: document.documentElement.lang || '', dir: getComputedStyle(document.body).direction,
    vitals: window.__crp || null,
    text: document.body.innerText.slice(0, 1200),
  };
}
