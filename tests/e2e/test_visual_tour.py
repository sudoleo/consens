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
  // Site icons come through the favicon proxy: an image still loading looked
  // like a pill without its icon.
  const loading = [...document.images].filter(img => {
    if (img.complete) return false;
    const r = img.getBoundingClientRect();
    return r.bottom > 0 && r.top < innerHeight && r.width > 0;
  }).map(img => new Promise(r => { img.addEventListener('load', r, { once: true }); img.addEventListener('error', r, { once: true }); }));
  await Promise.race([Promise.all([...finite.map(a => a.finished.catch(() => null)), ...loading]), new Promise(r => setTimeout(r, 2500))]);
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
        # Phones scroll the examples sideways: the row's far end.
        page.evaluate("() => { const row = document.getElementById('composerStarters'); row.scrollLeft = row.scrollWidth; }")
        shoot(page, "konto-beispiele-ende")
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
        " localStorage.setItem('runMode', 'compare'); sessionStorage.setItem('tourModeSeeded', '1'); }"))
    try:
        _soft_wait(page, "() => document.querySelectorAll('#composerModelIcons img').length >= 2")
        shoot(page, "konto-compare")
    finally:
        context.close()


AGENT_CHAT, AGENT_TURN = "a" * 32, "b" * 32
SUBSIDY = "The subsidy covers up to 70 percent of the installation cost."
RUNNING = "Running costs land around 1,100 to 1,400 euros a year at current tariffs, compared with about 1,900 euros for gas."
AGENT_TEXT = (
    "For a 1978 house with radiators, a heat pump is usually worth it once the flow temperature "
    "can stay at or below 55 °C on a cold day.\n\n"
    "## What decides it\n\n"
    "Rooms that stay warm today can keep their radiators; the rest need larger ones.\n\n"
    "Running costs land around **1,100 to 1,400 euros a year** at current tariffs, compared with about 1,900 euros for gas.\n\n"
    "- Check the flow temperature on a cold day first\n"
    "- Get a room-by-room heat load calculation\n"
    "- Ask about the federal subsidy before you sign\n\n"
    + SUBSIDY + "\n\n"
    "See the [subsidy terms](https://example.org/subsidy) and the [heat load guide](https://example.org/heat-load)."
)
AGENT_MODELS = (
    ("openai", "OpenAI", "openai/gpt-6-luna", "GPT-6 Luna"),
    ("anthropic", "Claude", "anthropic/claude-sonnet-5.5", "Claude Sonnet 5.5"),
    ("gemini", "Gemini", "google/gemini-3.5-flash", "Gemini 3.5 Flash"),
    ("deepseek", "DeepSeek", "deepseek/deepseek-v4-flash", "DeepSeek V4 Flash"),
    ("grok", "Grok", "x-ai/grok-4.3", "Grok 4.3"),
    ("kimi", "Kimi", "moonshotai/kimi-k2.6", "Kimi K2.6"),
)


def _agent_turn():
    """Eine gespeicherte Agent-Antwort mit allem, was der Bereich zeigt: zwei
    strittige Stellen (Widerspruch rot, geteilt bernstein), Quellen, Vergleich
    mit sechs Modellen und ein Verlauf aus Schritten und Suche."""
    import hashlib

    from app.services.chat_store import turn_detail

    digest = hashlib.sha256(AGENT_TEXT.encode()).hexdigest()
    labels = [label for _p, label, _m, _n in AGENT_MODELS]
    answers = [{"provider": p, "provider_label": label, "model": {"model": model, "label": name},
                "text": "### Short answer\n\nWorth it once the flow temperature stays at or below **55 °C**.\n\n"
                        "- Check the radiators room by room\n- Ask about the subsidy first",
                "sources": []} for p, label, model, name in AGENT_MODELS]
    claims = [
        {"anchor": AGENT_TEXT.split("\n\n")[0], "agree": labels, "dissent": [], "coverage": "supported"},
        {"anchor": RUNNING, "agree": labels[:4], "coverage": "split",
         "dissent": [{"model": "Grok", "quote": "closer to 1,700 euros", "target": "1,100 to 1,400 euros a year"}]},
        {"anchor": SUBSIDY, "agree": labels[:3], "coverage": "split",
         "dissent": [{"model": "DeepSeek", "quote": "usually 30 percent", "target": "up to 70 percent"}]},
    ]
    differences = [{"claim": "How much of the installation the subsidy covers", "consensus_anchor": SUBSIDY,
                    "type": "contradiction", "severity": "major", "positions": [
                        {"models": labels[:3], "stance": "Up to 70 percent with every bonus.", "quote": "up to 70 percent of the cost"},
                        {"models": labels[3:5], "stance": "Usually 30 percent; 70 only for low incomes.", "quote": "usually 30 percent"}]}]
    review = {"status": "succeeded", "answer_version": 1, "answer_hash": digest,
              "versions": [{"id": 1, "text": AGENT_TEXT, "hash": digest, "status": "succeeded"}],
              "comparisons": [{"id": "c1", "basis_hash": "basis", "question": "Is a heat pump worth it for a 1978 house?",
                               "reason": "Running costs and subsidy differ between sources", "status": "succeeded", "answers": answers}],
              "checks": [{"comparison_id": "c1", "basis_hash": "basis", "answer_hash": digest, "status": "succeeded",
                          "differences_data": {"models_compared": labels, "claims": claims, "differences": differences,
                                               "agreement": {"score": 58, "coverage_status": "sufficient"}}}]}
    activity = [
        {"version": 1, "id": "p1", "kind": "progress", "text": "Looking up flow temperatures for radiators from the 1970s."},
        {"version": 1, "id": "search", "kind": "tool", "name": "web_search", "status": "succeeded",
         "sources": [{"url": "https://example.org/heat-load", "title": "Heat load guide"},
                     {"url": "https://example.org/subsidy", "title": "Subsidy terms"},
                     {"url": "https://example.org/tariffs", "title": "Heat pump tariffs 2026"}]},
        {"version": 1, "id": "p2", "kind": "progress", "text": "The sources disagree on the subsidy; comparing six models."},
        {"version": 1, "id": "read", "kind": "tool", "name": "read_source", "status": "succeeded",
         "host": "example.org", "read": "completed", "sources": [{"url": "https://example.org/subsidy", "title": "Subsidy terms"}]},
    ]
    agents = [{"id": f"{i + 10:032x}", "seq": i + 1, "status": "completed", "kind": "comparison", "title": a["model"]["label"],
               "model": a["model"], "duration_ms": 3100, "comparison_id": "c1"} for i, a in enumerate(answers)]
    turn = turn_detail(AGENT_TURN, {
        "execution_mode": "agent", "status": "completed", "question": "Is a heat pump worth it for our 1978 house?",
        "assistant_response": AGENT_TEXT, "agent_review": review, "agent_activity": activity,
        "created_at": "2026-10-24T09:00:00Z", "completed_at": "2026-10-24T09:01:47Z",
        "agent_settings": {"model_id": agent_model_options()["default_model_id"], "policy": {"delegation": True}}}, {})
    return turn, agents


def _app_agent(browser, server, view, shoot):
    width = view[0]
    phone = width < 768
    turn, agents = _agent_turn()
    base = f"**/agent/chats/{AGENT_CHAT}/turns/{AGENT_TURN}/agents"
    context, page = _open(browser, server, view, routes={
        base: lambda route: _json(route, {"agents": agents, "status": "succeeded"}),
        base + "/*": lambda route: _json(route, {"agent": {"assignment": {"goal": "Compare"}}, "messages": [], "has_more": False}),
        f"**/agent/chats/{AGENT_CHAT}/files": lambda route: _json(route, {"files": []}),
        f"**/agent/chats/{AGENT_CHAT}/actions": lambda route: _json(route, {"actions": [], "evidence": []}),
    })
    try:
        # The tests' shortcut to a saved turn; opening a chat also writes its
        # question above the answer (run-view.js, agent-chat.js).
        page.evaluate("""turn => {
          App.runRegistry.showSavedView({type: 'bookmark'}, {chatId: 'a'.repeat(32), turnId: turn.id, executionMode: 'agent',
            question: turn.question, consensus: turn.consensus, currentTurn: turn});
          window.exitHeroMode();
          App.setThreadQuestion(turn.question);
        }""", turn)
        _soft_wait(page, "() => !!document.querySelector('#agentAnswerBody .cx-claim.is-major')")
        page.mouse.move(0, 0)
        shoot(page, "antwort")

        details = page.locator("#agentAnswerActivity details")
        details.locator(".agent-activity-title").click()
        _soft_wait(page, """() => {
          const host = document.getElementById('agentAnswerActivity');
          return host.querySelector('details[open]') && host.getAnimations({subtree: true}).every(a => a.playState !== 'running');
        }""")
        shoot(page, "zeitleiste")
        details.locator(".agent-activity-title").click()
        _soft_wait(page, "() => !document.querySelector('#agentAnswerActivity details[open]')")

        mark = page.locator("#agentAnswerBody .cx-claim.is-major").first
        mark.evaluate("el => el.scrollIntoView({block: 'center'})")
        if phone:
            mark.tap()
            _soft_wait(page, "() => !document.getElementById('claimPopover').hidden")
            shoot(page, "karte-blatt")
            page.locator("#claimPopover .claim-popover-close").tap()
            _soft_wait(page, "() => document.getElementById('claimPopover').hidden")
        else:
            mark.hover()
            _soft_wait(page, "() => !!document.querySelector('.insight-preview:not([hidden])')")
            shoot(page, "karte-hover")
            page.mouse.move(0, 0)
            page.wait_for_timeout(600)
            amber = page.locator("#agentAnswerBody .cx-claim.is-split").first
            amber.hover()
            _soft_wait(page, "() => !!document.querySelector('.insight-preview:not([hidden])')")
            shoot(page, "karte-hover-geteilt")
            page.mouse.move(0, 0)
            page.wait_for_timeout(600)
            mark.click()
            _soft_wait(page, "() => !document.getElementById('claimPopover').hidden")
            shoot(page, "karte-klick")
            page.keyboard.press("Escape")
            _soft_wait(page, "() => document.getElementById('claimPopover').hidden")
            page.mouse.move(0, 0)
            # Escape hands the focus back to the sentence; the footer is shot at rest.
            page.evaluate("() => document.activeElement?.blur()")

        page.locator("#agentAnswer .agent-evidence-link").first.evaluate("el => el.scrollIntoView({block: 'center'})")
        shoot(page, "fuss")
    finally:
        context.close()


COMPARE_QUESTION = "Postgres or MongoDB for an append-only event log with about 2,000 writes a second?"
COMPARE_ANSWERS = (
    "## Short answer\n\nPostgres. One table with a JSONB payload and a `bigserial` key carries "
    "**2,000 writes a second** on a single node with room to spare.\n\n"
    "- Transactions keep the log and its projections in step\n"
    "- Monthly partitions keep old events cheap\n- Logical replication feeds consumers",
    "## Recommendation\n\nGo with **Postgres** unless your event shapes change every week.\n\n"
    "1. Append-only fits a heap table well\n2. Use `BRIN` indexes on the timestamp\n"
    "3. Archive partitions older than a year\n\nMongoDB only wins if nobody wants migrations.",
    "Both work at that rate. Postgres gives you stronger ordering guarantees; MongoDB gives you a "
    "flexible schema and change streams out of the box. For a team that already runs Postgres, stay there.",
    "## It depends on the read side\n\nIf most reads replay one stream, MongoDB's document model is "
    "convenient. If you join events with other tables, **Postgres** is simpler.\n\n"
    "> At 2,000 writes a second either database is far from its limits.",
    "Postgres, with one caveat: plan snapshots once a stream passes a few thousand events, "
    "otherwise rebuilding state gets slow.",
)

CONSENSUS_TEXT = (
    "For an append-only event log at about 2,000 writes a second, Postgres is the safer default.\n\n"
    "## Why Postgres\n\n"
    "A single table with a JSONB payload handles tens of thousands of writes per second on one node.\n\n"
    "- Transactions keep the log and its projections in step\n"
    "- Monthly partitions keep old events cheap\n"
    "- Logical replication streams events to consumers\n\n"
    "MongoDB fits better when the event shapes change weekly and nobody wants migrations.\n\n"
    "Either way, plan for snapshots once a stream passes a few thousand events."
)
SITE_ICON = ('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect width="20" height="20" rx="5" fill="#3a3a3a"/>'
             '<path d="M5 6h10v2H5zm0 5h7v2H5z" fill="white"/></svg>')
CONSENSUS_SOURCES = [
    {"id": f"S{i}", "title": title, "url": url, "snippet": "An excerpt from the page the models cited."}
    for i, (title, url) in enumerate((
        ("PostgreSQL documentation: Table partitioning", "https://www.postgresql.org/docs/current/ddl-partitioning.html"),
        ("MongoDB manual: Change streams", "https://www.mongodb.com/docs/manual/changeStreams/"),
        ("Event sourcing with Postgres in practice", "https://example.org/event-sourcing-postgres"),
        ("Benchmarking JSONB inserts at scale", "https://example.org/jsonb-benchmark"),
    ), start=1)
]


def _saved_consensus(page):
    """Ein gespeicherter Consensus-Chat aus zwei Turns, geoeffnet ueber den
    echten Bookmark-Weg (Vorlage: test_model_answer_reader.seed_reader): Score,
    Satzmarken, zwei Unterschiede, Quellen und fuenf Modellantworten."""
    keys = page.evaluate("() => App.modelPrefs.slice(0, 5).map(p => p.key)")
    labels = keys
    claims = [
        {"anchor": CONSENSUS_TEXT.split("\n\n")[0], "agree": labels, "dissent": []},
        {"anchor": "A single table with a JSONB payload handles tens of thousands of writes per second on one node.",
         "agree": labels[:3], "dissent": [{"model": labels[3], "quote": "closer to 5,000 writes a second without tuning",
                                            "target": "tens of thousands of writes per second"}]},
        {"anchor": "MongoDB fits better when the event shapes change weekly and nobody wants migrations.",
         "agree": labels[:4], "dissent": [{"model": labels[4], "quote": "schema changes are cheap in both"}]},
    ]
    differences = [
        {"claim": "How many writes a second one Postgres node takes", "type": "contradiction", "severity": "major",
         "consensus_anchor": claims[1]["anchor"],
         "positions": [{"models": labels[:3], "stance": "Tens of thousands a second on one node.", "quote": "tens of thousands of inserts per second"},
                       {"models": labels[3:4], "stance": "Closer to 5,000 a second without tuning.", "quote": "closer to 5,000 writes a second"}],
         "verify": "Run a short insert benchmark on your own hardware."},
        {"claim": "When MongoDB is the better fit", "type": "emphasis",
         "positions": [{"models": labels[:2], "stance": "When event shapes change often."},
                       {"models": labels[2:4], "stance": "When reads replay one stream at a time."}]},
    ]
    data = {"models_compared": labels, "claims": claims, "differences": differences,
            "agreement": {"score": 64, "model_count": len(labels), "scored_claims": 7, "total_claims": 10, "coverage_percent": 70}}
    answers = {key: {"answer": text, "model_label": f"{key} model", "sources": CONSENSUS_SOURCES[:2]}
               for key, text in zip(keys, COMPARE_ANSWERS)}
    old = {"id": "tour-old", "position": 1, "status": "completed", "mode": "Standard", "execution_mode": "consensus",
           "question": "Which database should hold our event log?",
           "consensus": "It depends on the write rate and on how you read the events back.",
           "sources": CONSENSUS_SOURCES[2:], "differences_data": {**data, "claims": [], "differences": differences[1:]},
           "model_answers": {key: {"answer": "It depends on the write rate.", "model_label": f"{key} model"} for key in keys[:3]}}
    current = {"id": "tour-current", "position": 2, "status": "completed", "mode": "Standard", "execution_mode": "consensus",
               "question": COMPARE_QUESTION, "consensus": CONSENSUS_TEXT, "sources": CONSENSUS_SOURCES,
               "differences_data": data, "model_answers": answers}
    saved = "tour-saved"
    bookmark = {"id": saved, "query": COMPARE_QUESTION, "title": "Postgres or MongoDB for an event log", "mode": "Standard",
                "chat_id": "c" * 32, "responses": {"consensus": CONSENSUS_TEXT}}
    page.route(f"**/bookmarks/{saved}/conversation*",
               lambda route: _json(route, {"chat_id": "c" * 32, "turns": [old, current], "has_more": False}))
    page.route(f"**/bookmarks/{saved}", lambda route: _json(route, {"bookmark": bookmark}))
    page.route("**/api/topics/favicon?*", lambda route: route.fulfill(content_type="image/svg+xml", body=SITE_ICON))
    page.evaluate("id => window.openBookmark(id)", saved)
    _soft_wait(page, """() => App.followup?.lastExchange?.turn?.turn_id === 'tour-current'
      && document.getElementById('runProvenance')?.hidden === false""")
    # An opened chat scrolls to its newest question (chat-scroll.js).
    page.evaluate("""() => new Promise(resolve => {
      let last = scrollY, still = 0;
      const tick = () => {
        if (Math.abs(scrollY - last) < 1) still += 1; else { still = 0; last = scrollY; }
        if (still >= 12) resolve(); else requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    })""")


def _app_compare(browser, server, view, shoot):
    phone = view[0] < 768
    context, page = _open(browser, server, view, init_script=(
        "if (!sessionStorage.getItem('tourModeSeeded')) {"
        " localStorage.setItem('runMode', 'compare'); sessionStorage.setItem('tourModeSeeded', '1'); }"))
    try:
        _soft_wait(page, "() => document.querySelectorAll('.is-preview .answer-reader-answer').length >= 2")
        shoot(page, "vorschau")

        # A run through the registry, like test_phase4_frontend: nothing is
        # sent, the projection is the real one.
        page.evaluate("""([question, texts]) => {
          const registry = window.App.runRegistry;
          const prefs = App.modelPrefs.filter(p => document.getElementById(p.checkId)?.checked).slice(0, 6);
          const providers = prefs.map(p => ({provider: p.key,
            modelLabel: document.getElementById(p.selectId)?.selectedOptions?.[0]?.textContent?.trim() || p.label}));
          const run = registry.create({runId: 'tour-compare', question, config: {agentMode: false, providers}});
          run.phase = 'answers';
          providers.forEach((p, i) => {
            run.modelResults[p.provider] = i < 2 ? {status: 'complete', text: texts[i], sources: []}
              : i === 2 ? {status: 'streaming', streamText: texts[i].slice(0, 90)} : {status: 'pending'};
          });
          registry.setStatus(run.runId, 'running');
          window.__tourRun = run; window.__tourProviders = providers;
        }""", [COMPARE_QUESTION, list(COMPARE_ANSWERS)])
        _soft_wait(page, "() => !!document.querySelector('.is-direct .answer-reader-answer')")
        page.evaluate("() => window.scrollTo(0, 0)")
        shoot(page, "lauf")

        page.evaluate("""texts => {
          const run = window.__tourRun;
          window.__tourProviders.forEach((p, i) => {
            run.modelResults[p.provider] = i === 5
              ? {status: 'error', text: '', error: 'This model timed out.', sources: []}
              : {status: 'complete', text: texts[i % texts.length], sources: []};
          });
          run.phase = 'done';
          window.App.runRegistry.setStatus(run.runId, 'succeeded');
          window.App.runRegistry.renderVisible();
        }""", list(COMPARE_ANSWERS))
        _soft_wait(page, "() => !document.querySelector('.is-direct .answer-skeleton')")
        page.evaluate("() => window.scrollTo(0, 0)")
        shoot(page, "ergebnis")
        page.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
        shoot(page, "ergebnis-ende")
    finally:
        context.close()

    context, page = _open(browser, server, view)
    try:
        _saved_consensus(page)
        page.mouse.move(0, 0)
        shoot(page, "consensus")
        page.evaluate("() => document.getElementById('runProvenance')?.scrollIntoView({block: 'start'})")
        shoot(page, "consensus-score")
        page.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
        shoot(page, "consensus-fuss")
        page.evaluate("() => document.querySelector('.thread-history-turn')?.scrollIntoView({block: 'start'})")
        shoot(page, "verlauf")

        page.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
        page.locator("#consensusDifferencesTab").click()
        _soft_wait(page, "() => document.querySelectorAll('#answerReaderInspector .diff-card').length > 0")
        shoot(page, "differences")
        page.locator("#answerReaderInspector .diff-card summary").first.click()
        _soft_wait(page, "() => document.querySelector('#answerReaderInspector .diff-card')?.open")
        shoot(page, "differences-offen")
        page.locator("#answerReaderSections [data-section='sources']").click()
        _soft_wait(page, "() => !!document.querySelector('#answerReaderInspector .answer-reader-source-card')")
        shoot(page, "quellen")
        page.keyboard.press("Escape")
        _soft_wait(page, "() => document.getElementById('modelAnswerReader')?.hidden !== false || !document.querySelector('#modelAnswerReader:not([hidden]) .answer-reader-dialog[open]')")

        page.locator("#agentModeAnswersToggle").click()
        _soft_wait(page, "() => !!document.querySelector('#modelAnswerReader:not([hidden]) .answer-reader-body')")
        shoot(page, "antworten")
        page.locator("#answerReaderCompare").click()
        _soft_wait(page, "() => document.querySelector('.answer-reader-dialog')?.dataset.modal === 'true'")
        if phone:
            page.locator("#answerReaderSideB").click()
        shoot(page, "antworten-vergleich")
    finally:
        context.close()


AREAS = {
    "app-start": _app_start,
    # Die uebrigen Bereiche bekommen ihre Zustaende in dem Lauf, der sie als
    # Erster braucht (siehe Liste in der Aufgabe consens-visual-polish).
    "app-agent": _app_agent,
    "app-compare": _app_compare,
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
