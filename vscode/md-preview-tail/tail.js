(() => {
  const SETTLE_MS = 400;   // after a refresh, scrolls we didn't cause (VS Code's restore) are overridden this long
  const SLACK_VH = 0.33;   // still following if the content end is within this much of a screen below the fold
  const PAD = 24;          // gap left under the last line when following
  const SHOW_BADGE = true; // corner indicator: following / paused

  const root = document.documentElement, body = document.body;
  let source = '';
  try { source = JSON.parse(document.getElementById('vscode-markdown-preview-data').dataset.settings).source || ''; } catch {}
  const KEY = 'mdTail:' + source;

  // Survives full preview reloads (remove + re-add), which otherwise reset this script
  let st = { stick: true, line: null, offset: 0 };
  try { Object.assign(st, JSON.parse(sessionStorage.getItem(KEY)) || {}); } catch {}
  const save = () => { try { sessionStorage.setItem(KEY, JSON.stringify(st)); } catch {} };

  let settleUntil = 0, lastInput = 0;
  const userActive = () => Date.now() - lastInput < 300;

  // End of real content, excluding the preview's scroll-beyond-last-line margin
  const contentEnd = () => root.scrollHeight - parseFloat(getComputedStyle(body).marginBottom || 0);
  const nearEnd = () => contentEnd() <= scrollY + innerHeight * (1 + SLACK_VH);

  // Anchor = first source-line element at the top of the viewport; stable when text is appended below it
  const firstVisible = () => {
    const els = document.querySelectorAll('.markdown-body [data-line]');
    let lo = 0, hi = els.length - 1, hit = null;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (els[mid].getBoundingClientRect().bottom > 0) { hit = els[mid]; hi = mid - 1; } else lo = mid + 1;
    }
    return hit;
  };
  const record = () => {
    st.stick = nearEnd();
    const el = firstVisible();
    if (el) { st.line = el.dataset.line; st.offset = el.getBoundingClientRect().top; }
    save(); badge();
  };

  const target = () => {
    if (st.stick) return Math.max(0, contentEnd() - innerHeight + PAD);
    const el = st.line != null && document.querySelector(`.markdown-body [data-line="${st.line}"]`);
    return el ? scrollY + el.getBoundingClientRect().top - st.offset : null;
  };
  const apply = () => { const y = target(); if (y != null && Math.abs(y - scrollY) > 1) scrollTo(0, y); };
  const settle = () => { settleUntil = Date.now() + SETTLE_MS; };
  const refreshed = () => {
    settle(); [0, 50, 150, 300].forEach(t => setTimeout(apply, t));
    // VS Code restores its (fractional) position only after images load, so re-assert after that too
    Promise.all([...document.images].map(i => i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; })))
      .then(() => { settle(); [0, 50, 150].forEach(t => setTimeout(apply, t)); });
  };

  for (const ev of ['wheel', 'keydown', 'mousedown', 'touchstart'])
    addEventListener(ev, () => { lastInput = Date.now(); }, { passive: true });

  let raf = 0;
  addEventListener('scroll', () => {
    if (Date.now() <= settleUntil && !userActive()) { apply(); return; }  // restore flick: put it back
    if (!raf) raf = requestAnimationFrame(() => { raf = 0; record(); });  // wheel, keys, or editor sync
  }, { passive: true });

  new ResizeObserver(() => { settle(); apply(); }).observe(body);  // late image/KaTeX growth
  addEventListener('vscode.markdown.updateContent', refreshed);
  addEventListener('load', refreshed);

  let el;
  function badge() {
    if (!SHOW_BADGE) return;
    if (!el) {
      el = document.createElement('div');
      el.style.cssText = 'position:fixed;right:10px;bottom:8px;z-index:9;font:11px sans-serif;padding:2px 7px;' +
        'border-radius:9px;opacity:.75;pointer-events:none;color:#fff';
      body.appendChild(el);
    }
    el.textContent = st.stick ? '⤓ following' : '⏸ paused';
    el.style.background = st.stick ? '#2e7d32' : '#8d6e00';
  }
  badge();
})();
