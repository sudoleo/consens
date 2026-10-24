"""Bilder der echten Oberflaeche fuer den taeglichen visuellen Feinschliff.

Laeuft nur mit ``VISUAL_TOUR_DIR``: ohne die Variable ueberspringt pytest die
Datei, die CI wird dadurch weder langsamer noch rot. Pro Bereich ein Fall,
``VISUAL_TOUR_AREA`` (kommagetrennt) grenzt ein. Jedes Bild liegt unter
``<VISUAL_TOUR_DIR>/<bereich>/<breite>-<theme>-<zustand>.png``, daneben eine
gleichnamige ``.json`` mit Messwerten: horizontaler Ueberlauf, abgeschnittener
Text, Elemente ausserhalb des Viewports, Kontrast und ungleiche Abstaende
gleichartiger Geschwister.

Gestartet wie jeder Browserlauf ueber die Warteschlange:
    $env:VISUAL_TOUR_DIR = '<ordner>'; $env:VISUAL_TOUR_AREA = 'app-start'
    .\\dev.ps1 check browser -TestPath tests/e2e/test_visual_tour.py

Modellantworten kommen aus MOCK_LLM, Konto- und Chatdaten aus Playwright-Routen
(Vorlage: test_phase4_frontend._real_firebase_page); nichts kostet Geld.
"""
import json
import os
from pathlib import Path

import pytest

from app.services.llm.agent_client import agent_model_options
from app.services.starter_questions import CURATED_STARTERS
from tests.e2e.test_phase4_frontend import (
    FIREBASE_APP_STUB,
    FIREBASE_AUTH_STUB,
    _json,
    _route_account_settings,
)

TOUR_DIR = os.environ.get("VISUAL_TOUR_DIR", "").strip()
if not TOUR_DIR:
    pytest.skip("Bilder nur mit VISUAL_TOUR_DIR", allow_module_level=True)

SELECTED = {name.strip() for name in os.environ.get("VISUAL_TOUR_AREA", "").split(",") if name.strip()}

# Jeder Bereich in denselben fuenf Ansichten, Geraetefaktor 2.
VIEWS = (
    (1440, 900, "light"),
    (1440, 900, "dark"),
    (390, 844, "light"),
    (390, 844, "dark"),
    (320, 568, "dark"),
)

# Die drei laengsten kuratierten Beispielfragen: der Server zieht pro Aufruf
# zufaellig, Vorher und Nachher brauchen dieselben Knoepfe.
FIXED_STARTERS = sorted(CURATED_STARTERS, key=lambda item: -len(item["label"]))[:3]

PREDICTED = [
    {"label": "Heat pump running costs?", "question": "What will a heat pump cost to run in our 1978 house per year?"},
    {"label": "AI Act deadlines?", "question": "Which EU AI Act deadlines apply to our support chatbot?"},
    {"label": "Creatine timing?", "question": "Does the time of day I take creatine change how I sleep?"},
]

CHATS = [
    {"id": f"tour_{index}", "query": question, "title": title,
     "timestamp": f"2026-10-{24 - index:02d}T09:00:00Z"}
    for index, (title, question) in enumerate((
        ("Heat pump running costs", "What will a heat pump cost to run in our 1978 house?"),
        ("EU AI Act for support chatbots", "Which EU AI Act deadlines apply to our support chatbot?"),
        ("Creatine and sleep", "Does creatine change how I sleep?"),
        ("Postgres or MongoDB for an event log", "Postgres or MongoDB for an append-only event log?"),
        ("Four-day week evidence", "Do four-day weeks keep output stable?"),
        ("Solid-state batteries timeline", "When will solid-state EV batteries ship at scale?"),
    ))
]

LONG_QUESTION = (
    "We are a team of six and want to move our support inbox to an AI assistant. "
    "Which EU AI Act obligations apply to us from 2026, and what do we have to "
    "document before we switch it on?"
)

# Misst im Browser, was das Auge leicht uebersieht. Farben laufen ueber ein
# Canvas, damit auch color-mix()/oklab-Werte vergleichbar werden.
AUDIT_JS = r"""
() => {
  const vw = innerWidth, vh = innerHeight;
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = 1;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const rgba = value => {
    ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = '#000'; ctx.fillStyle = value; ctx.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data; return [r, g, b, a / 255];
  };
  const name = el => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    const cls = [...el.classList].slice(0, 3);
    return cls.length ? s + '.' + cls.join('.') : s;
  };
  const path = el => { const parts = []; for (let n = el; n && n !== document.body && parts.length < 4; n = n.parentElement) parts.unshift(name(n)); return parts.join(' > '); };
  const shown = el => {
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility !== 'visible' || el.closest('[hidden],[inert],[aria-hidden="true"]')) return false;
    for (let n = el; n; n = n.parentElement) if (parseFloat(getComputedStyle(n).opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  };
  const clipper = el => {
    for (let p = el.parentElement; p && p !== document.documentElement; p = p.parentElement) {
      const st = getComputedStyle(p);
      if (st.overflowX !== 'visible' || st.overflowY !== 'visible' || st.clipPath !== 'none') return p;
    }
    return null;
  };
  const ownText = el => [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').replace(/\s+/g, ' ').trim();
  const lum = ([r, g, b]) => { const f = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const over = (top, bottom) => { const a = top[3]; return [0, 1, 2].map(i => top[i] * a + bottom[i] * (1 - a)).concat(1); };
  // A fill drawn by ::before/::after (Send, Sign up) is invisible to the walk.
  const paintedByPseudo = n => ['::before', '::after'].some(pseudo => {
    const st = getComputedStyle(n, pseudo);
    return st.content !== 'none' && (rgba(st.backgroundColor)[3] > 0 || st.backgroundImage !== 'none');
  });
  const background = el => {
    const layers = [];
    for (let n = el; n; n = n.parentElement) {
      const st = getComputedStyle(n);
      if (st.backgroundImage !== 'none' && !st.backgroundImage.startsWith('url(') || paintedByPseudo(n)) return null;
      const c = rgba(st.backgroundColor);
      if (c[3] > 0) { layers.push(c); if (c[3] >= 0.999) break; }
    }
    let base = [255, 255, 255, 1];
    for (const layer of layers.reverse()) base = over(layer, base);
    return base;
  };
  const elements = [...document.body.querySelectorAll('*')].filter(el => !el.closest('svg, script, style, template, noscript'));
  const visible = elements.filter(shown);
  const set = new Set(visible);

  const offscreen = [];
  for (const el of visible) {
    const r = el.getBoundingClientRect();
    if (r.right <= vw + 1 && r.left >= -1) continue;
    if (clipper(el) || set.has(el.parentElement) && offscreen.some(o => o.el === el.parentElement)) continue;
    if (getComputedStyle(el).position === 'fixed' && (r.right <= 0 || r.left >= vw)) continue;
    offscreen.push({ el, at: path(el), left: Math.round(r.left), right: Math.round(r.right) });
  }

  const truncated = [];
  for (const el of visible) {
    const text = ownText(el);
    if (!text) continue;
    const st = getComputedStyle(el);
    const wide = el.scrollWidth > el.clientWidth + 1 && st.overflowX !== 'visible';
    const tall = el.scrollHeight > el.clientHeight + 1 && st.overflowY !== 'visible' && !['auto', 'scroll'].includes(st.overflowY);
    if (wide || tall) truncated.push({ at: path(el), text: text.slice(0, 80), how: wide ? (st.textOverflow === 'ellipsis' ? 'ellipsis' : 'cut') : 'clamp' });
  }

  const contrast = [];
  for (const el of visible) {
    const text = ownText(el);
    if (!text || el.closest('[disabled],[aria-disabled="true"]')) continue;
    const st = getComputedStyle(el);
    const bg = background(el);
    if (!bg) continue;
    let fg = rgba(st.color);
    let alpha = fg[3];
    for (let n = el; n; n = n.parentElement) alpha *= parseFloat(getComputedStyle(n).opacity);
    fg = over([fg[0], fg[1], fg[2], alpha], bg);
    const [hi, lo] = [lum(fg), lum(bg)].sort((a, b) => b - a);
    const ratio = (hi + 0.05) / (lo + 0.05);
    const size = parseFloat(st.fontSize), weight = parseInt(st.fontWeight, 10) || 400;
    const need = size >= 24 || (size >= 18.66 && weight >= 700) ? 3 : 4.5;
    if (ratio < need) contrast.push({ at: path(el), text: text.slice(0, 60), ratio: Math.round(ratio * 100) / 100, need, size });
  }

  const spacing = [];
  for (const parent of new Set(visible.map(el => el.parentElement))) {
    if (!parent || !/flex|grid/.test(getComputedStyle(parent).display)) continue;
    const kids = [...parent.children].filter(el => set.has(el) && getComputedStyle(el).position !== 'absolute');
    const groups = {};
    for (const kid of kids) (groups[kid.tagName + '.' + (kid.classList[0] || '')] ||= []).push(kid);
    for (const [key, group] of Object.entries(groups)) {
      if (group.length < 3) continue;
      const boxes = group.map(el => el.getBoundingClientRect());
      const gaps = [];
      for (let i = 1; i < boxes.length; i++) {
        const a = boxes[i - 1], b = boxes[i];
        if (Math.abs(a.top - b.top) < 2) gaps.push(b.left - a.right);
        else if (Math.abs(a.left - b.left) < 2) gaps.push(b.top - a.bottom);
      }
      if (gaps.length >= 2 && Math.max(...gaps) - Math.min(...gaps) > 1.5)
        spacing.push({ at: path(parent), children: key, gaps: gaps.map(g => Math.round(g * 10) / 10) });
    }
  }

  // A shadow that the viewport edge cuts off reads as a smudge.
  const cutShadows = [];
  for (const el of elements) {
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility !== 'visible' || st.boxShadow === 'none') continue;
    let opacity = 1;
    for (let n = el; n; n = n.parentElement) opacity *= parseFloat(getComputedStyle(n).opacity);
    if (opacity === 0) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (r.top < 0 || r.left < 0 || r.bottom > vh || r.right > vw)
      cutShadows.push({ at: path(el), rect: [r.left, r.top, r.width, r.height].map(Math.round), opacity: Math.round(opacity * 100) / 100 });
  }

  return {
    url: location.pathname + location.search,
    viewport: [vw, vh],
    overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    overflowY: document.documentElement.scrollHeight - document.documentElement.clientHeight,
    offscreen: offscreen.slice(0, 20).map(({ el, ...rest }) => rest),
    cutShadows: cutShadows.slice(0, 20),
    truncated: truncated.slice(0, 30),
    contrast: contrast.slice(0, 30),
    spacing: spacing.slice(0, 20),
  };
}
"""

SETTLE_JS = """async () => {
  await document.fonts.ready;
  const finite = document.getAnimations().filter(a => a.effect?.getTiming?.().iterations !== Infinity);
  await Promise.race([Promise.all(finite.map(a => a.finished.catch(() => null))), new Promise(r => setTimeout(r, 2500))]);
}"""


def _open(browser, server, view, *, uid="visual-tour", path="/app", init_script=None, routes=None):
    """Seite wie test_phase4_frontend._real_firebase_page, aber mit Geraete-
    faktor 2, Systemfarbschema und auf Telefonbreite mit Touch."""
    width, height, theme = view
    phone = width < 768
    context = browser.new_context(
        viewport={"width": width, "height": height}, device_scale_factor=2,
        color_scheme=theme, has_touch=phone, is_mobile=phone,
    )
    context.add_init_script(f"window.__E2E_INITIAL_UID = {json.dumps(uid)};")
    context.add_init_script(
        "localStorage.setItem('consensio.settingsReset', '2026-10-12');"
        f"localStorage.setItem('theme', {json.dumps(theme)});"
    )
    if init_script:
        context.add_init_script(init_script)
    context.route("https://www.gstatic.com/firebasejs/9.22.0/firebase-app.js",
                  lambda route: route.fulfill(content_type="application/javascript", body=FIREBASE_APP_STUB))
    context.route("https://www.gstatic.com/firebasejs/9.22.0/firebase-auth.js",
                  lambda route: route.fulfill(content_type="application/javascript", body=FIREBASE_AUTH_STUB))
    context.route("https://cloud.umami.is/**",
                  lambda route: route.fulfill(content_type="application/javascript", body="/* tour */"))
    page = context.new_page()
    page.route("**/confirm-registration", lambda route: _json(route, {"status": "ok"}))
    page.route("**/user_status", lambda route: _json(route, {"tier": "free", "is_pro": False, "agent_access": True}))
    page.route("**/usage", lambda route: _json(route, {
        "is_pro": False, "remaining": 3, "deep_remaining": 0, "total_limit": 3, "deep_total_limit": 0}))
    page.route("**/bookmarks?*", lambda route: _json(route, {"bookmarks": [], "next_cursor": None}))
    page.route("**/auth/session", lambda route: _json(route, {"status": "ok"}))
    page.route("**/agent/budget", lambda route: _json(route, {"token_budget": {"limit": 660000, "used": 0, "remaining": 660000}}))
    page.route("**/api/my/memory", lambda route: _json(route, {"memory": {"content": "", "revision": 0}}))
    # Der Stub meldet sich mit "token-<uid>", das MOCK_AUTH nicht kennt: jede
    # angemeldete Route, die ein Zustand braucht, steht deshalb hier.
    catalog = agent_model_options()
    page.route("**/agent/models", lambda route: _json(route, catalog))
    page.route("**/agent/google/connections", lambda route: _json(route, {"configured": False, "connections": []}))
    page.route("**/api/my/watches", lambda route: _json(route, {
        "status": "success", "watches": [], "limits": {"plan": "free", "active_count": 0, "active_limit": 3}}))
    _route_account_settings(page)
    failed = []
    page.on("response", lambda response: failed.append(f"{response.status} {response.request.method} {response.url.split('?')[0]}")
            if response.status >= 400 and response.url.startswith(server) else None)
    page.tour_failed = failed
    for pattern, handler in (routes or {}).items():
        page.route(pattern, handler)
    # Inter's Latin part loads with font-display: optional (typography.css):
    # a cold context got the fallback face at random. The second load is the
    # returning visitor's, with the font in the cache before the first paint.
    for _ in range(2):
        page.goto(server + path, wait_until="domcontentloaded")
        page.wait_for_function("() => window.__consensioAuthState?.known === true")
    page.wait_for_function("() => document.fonts.check('16px \"Inter Variable\"')")
    _fix_starters(page)
    return context, page


def _fix_starters(page):
    page.evaluate("""starters => {
      const buttons = document.querySelectorAll('#composerStarters .composer-starter:not([data-starter="check"]):not([data-starter="predicted"])');
      buttons.forEach((button, index) => {
        const item = starters[index];
        if (!item) return;
        button.dataset.starter = item.key;
        button.dataset.question = item.question;
        button.textContent = item.label;
      });
    }""", [{"key": item["key"], "label": item["label"], "question": item["question"]} for item in FIXED_STARTERS])


def _soft_wait(page, script, timeout=8000):
    try:
        page.wait_for_function(script, timeout=timeout)
    except Exception:  # noqa: BLE001 - ein fehlender Zustand soll im Bild auffallen, nicht den Rundgang beenden
        pass


def _shooter(area, view):
    width, _height, theme = view
    folder = Path(TOUR_DIR) / area
    folder.mkdir(parents=True, exist_ok=True)

    def shoot(page, state, *, full_page=False):
        page.evaluate(SETTLE_JS)
        page.wait_for_timeout(250)
        stem = f"{width}-{theme}-{state}"
        page.screenshot(path=str(folder / f"{stem}.png"), full_page=full_page)
        audit = page.evaluate(AUDIT_JS)
        # Ein roter Request heisst meist: dem Rundgang fehlt eine Route, das
        # Bild zeigt dann einen Fehlerzustand statt des gemeinten.
        audit["failedRequests"] = sorted(set(getattr(page, "tour_failed", [])))
        (folder / f"{stem}.json").write_text(json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")
    return shoot


def _app_start(browser, server, view, shoot):
    agent_ready = "() => !document.getElementById('agentModelDropdown')?.disabled"

    context, page = _open(browser, server, view, uid=None)
    try:
        _soft_wait(page, "() => !!document.querySelector('#agentModelControls .model-picker-display')")
        shoot(page, "gast-leer")
        page.fill("#questionInput", LONG_QUESTION)
        shoot(page, "gast-getippt")
    finally:
        context.close()

    context, page = _open(browser, server, view)
    try:
        _soft_wait(page, agent_ready)
        shoot(page, "konto-leer")
        page.click("#attachTrigger")
        _soft_wait(page, "() => !document.getElementById('attachMenu').hidden")
        shoot(page, "konto-plusmenue")
        page.keyboard.press("Escape")
        _soft_wait(page, "() => document.getElementById('attachMenu').hidden")
        page.fill("#questionInput", LONG_QUESTION)
        shoot(page, "konto-getippt")
    finally:
        context.close()

    context, page = _open(browser, server, view, routes={
        "**/bookmarks?*": lambda route: _json(route, {"bookmarks": CHATS, "next_cursor": None}),
        "**/api/my/starter-questions": lambda route: _json(route, {"status": "success", "questions": PREDICTED}),
    })
    try:
        _soft_wait(page, "() => document.querySelectorAll('[data-starter=\"predicted\"]').length === 3")
        _soft_wait(page, agent_ready)
        shoot(page, "konto-chats")
    finally:
        context.close()

    context, page = _open(browser, server, view, init_script=(
        "if (!sessionStorage.getItem('tourModeSeeded')) {"
        " localStorage.setItem('runMode', 'consensus'); sessionStorage.setItem('tourModeSeeded', '1'); }"))
    try:
        _soft_wait(page, "() => document.querySelectorAll('#composerModelIcons img').length >= 2")
        shoot(page, "konto-consensus")
    finally:
        context.close()


AREAS = {
    "app-start": _app_start,
    # Die uebrigen Bereiche bekommen ihre Zustaende in dem Lauf, der sie als
    # Erster braucht (siehe Liste in der Aufgabe consens-visual-polish).
    "app-agent": None,
    "app-compare": None,
    "app-chrome": None,
    "watches": None,
    "landing": None,
    "public": None,
    "share-legal": None,
    "deutsch": None,
}


@pytest.mark.parametrize("area", list(AREAS))
def test_visual_tour(browser, app_server, area):
    if SELECTED and area not in SELECTED:
        pytest.skip(f"{area} nicht in VISUAL_TOUR_AREA")
    tour = AREAS[area]
    if tour is None:
        pytest.skip(f"Fuer {area} gibt es noch keine Zustaende")
    for view in VIEWS:
        tour(browser, app_server, view, _shooter(area, view))
