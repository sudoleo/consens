"""consens.io browser VM: the one program the server runs here for the
agent's ``browser`` tool (agent_browser.py, since 2026-10-27 instead of a
shell command in the agent's VM).

One action per call, as JSON on stdin, typed by the server: {"action":
"open", "url": ...}, {"action": "click", "ref": "e12"} and so on (ACTIONS).
The answer is one JSON object on stdout: {"status", "text"} and, for a
screenshot, "png" (base64). Status "ok", "refused" (the action cannot be
done, the text says why), "user" (the user has the browser), "setup" (the
browser is being installed) or "failed". No code of the agent runs here: it
only chooses among these actions and their typed arguments.

The same Chrome the user sees and steers in the live view, with the sign-ins
the user made there. Pages are read as text: ``read`` lists the page's
headings and the elements one can act on, each with a ref (e12) that click,
type, select and upload take; ``find`` looks up a text in what the page shows
and names the ref of the element it lies in; every action prints the page
again, so the agent sees what changed in the same step. The page's head says
whether the browser holds cookies for its address (yes or no, never which).

Two things the agent never does here: type into a password field (the user
signs in in the live view), and act while the user has taken over the
browser (CONTROL, written by consens.io's server, which also holds the
agent's calls meanwhile).

A Chrome that stops answering costs one call, not the rest of the message
(since 2026-10-28; on Max's browser VM a page load ran into its 30 s, the
next connection into its 20 s, and each later call would have too): a call
that does not finish within CALL_LIMIT ends with "failed" and restarts
Chrome (display.sh --restart, tabs and sign-ins stay), a connection that
does not come about restarts it once and tries again, and open returns a
page that answered but is still loading instead of failing.

Awake between the agent's steps (since 2026-10-29): the VM pauses after a
few idle seconds (measured: 46 of 60 seconds frozen without a command), and a
paused Chrome loses every live connection of its pages; a game on foony.com
went "offline" between two moves, and so do consens.io's live updates. Each
call therefore holds the VM awake for AWAKE_FOR after it, through the Sprites
Tasks API like the workbench's background processes (agent_vm_processes): an
expiring hold, renewed by the next call, gone by itself after the last one.
The live view keeps it awake anyway (its exec session).
"""
import base64
import json
import os
import re
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
STATE = os.path.join(HOME, ".consens/browser")
SETUP_MARKER = os.path.join(STATE, "setup-done-1")
CONTROL = os.path.join(STATE, "control.json")
# The last ref given in this browser: refs are never given twice.
REF_COUNTER = os.path.join(STATE, "ref-count")
# Where the server puts a file of the workbench for an upload.
UPLOADS = os.path.join(STATE, "uploads")
CDP = "http://127.0.0.1:9222"
READ_CHARS = 6000
AFTER_ACTION_CHARS = 4000
TEXT_CHARS = 12000
# find: the text to look for, how many places it lists, and the characters
# of the page it shows on either side of one.
FIND_CHARS = 200
FIND_MATCHES = 20
FIND_AROUND = 60
WAIT_MAX = 120
# A first setup in one call, within the server's limit (agent_browser.CALL_SECONDS).
SETUP_SECONDS = 100
# One action once the browser runs (a wait adds its seconds), the connection
# to Chrome's debugging port, and how long open waits for an address to
# answer and then for its document. Together with a restart they stay within
# the server's limit (agent_browser.CALL_SECONDS).
CALL_LIMIT = 70
CONNECT_SECONDS = 15
RESTART_SECONDS = 30
OPEN_SECONDS = 30
LOADED_SECONDS = 10
# The Tasks API hold that keeps the VM awake after a call (stay_awake).
AWAKE_TASK = "consens-browser-awake"
AWAKE_FOR = "10m"
API_SOCKET = "/.sprite/api.sock"
KEYS = {"Enter", "Tab", "Escape", "Backspace", "Delete", "Space", "ArrowUp", "ArrowDown", "ArrowLeft",
        "ArrowRight", "PageUp", "PageDown", "Home", "End", "Shift+Tab"}
ACTIONS = {"open", "read", "text", "find", "click", "drag", "type", "select", "key", "scroll", "back", "forward",
           "tabs", "tab", "screenshot", "upload", "download", "wait", "warm"}
# What changes the page or sends something: never while the user has the browser.
ACTING = {"open", "click", "drag", "type", "select", "upload", "download", "key", "scroll", "back", "forward", "tab"}
# A place on the page and drag's strokes (agent_browser.py checks the same).
MAX_COORDINATE = 10_000
MAX_STROKES = 50
MAX_STROKE_POINTS = 500
MAX_POINTS = 2_000
DRAG_STEP_PIXELS = 8
# Files a page downloaded (a click, Enter, an address that downloads, the
# action download) until the server copies them to the workbench and deletes
# them here (agent_browser.py, since 2026-10-28). What the user downloads in
# the live view lands in Chrome's own folder and is taken along as well.
DOWNLOADS = os.path.join(STATE, "downloads")
CHROME_DOWNLOADS = os.path.join(HOME, "Downloads")
DOWNLOAD_SECONDS = 60

# A ref stays with its element, and a new element takes the next number of
# the browser (``start``, REF_COUNTER). Until 2026-10-27 every read numbered
# the page from e1 again, so a ref from an older read could name another
# element without an error; now it names its element or none.
SNAPSHOT_JS = r"""
start => {
  const ACT = 'a[href],button,input:not([type=hidden]),select,textarea,summary,[role=button],[role=link],' +
    '[role=checkbox],[role=radio],[role=tab],[role=menuitem],[role=menuitemcheckbox],[role=option],' +
    '[role=switch],[role=combobox],[role=textbox],[role=searchbox],[role=slider],[contenteditable=""],' +
    '[contenteditable=true]';
  const clean = text => (text || '').replace(/\s+/g, ' ').trim();
  const clip = (text, size) => text.length > size ? text.slice(0, size - 1) + '…' : text;
  const shown = el => {
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none') return false;
    const box = el.getBoundingClientRect();
    return box.width > 0 && box.height > 0;
  };
  const labelled = el => (el.getAttribute('aria-labelledby') || '').split(/\s+/).filter(Boolean)
    .map(id => clean((document.getElementById(id) || {}).innerText)).join(' ');
  const name = el => clean(el.getAttribute('aria-label')) || labelled(el) ||
    (el.labels && el.labels.length ? clean(el.labels[0].innerText) : '') || clean(el.getAttribute('placeholder')) ||
    clean(el.getAttribute('alt')) || clean(el.getAttribute('title')) ||
    (el.tagName === 'INPUT' ? '' : clean(el.innerText)) ||
    (el.querySelector && el.querySelector('img[alt]') ? clean(el.querySelector('img[alt]').alt) : '');
  const TYPES = {checkbox: 'checkbox', radio: 'radio', submit: 'button', button: 'button', reset: 'button',
                 image: 'button', file: 'file field', range: 'slider', search: 'searchbox', password: 'password field',
                 email: 'textbox', tel: 'textbox', url: 'textbox', number: 'textbox', date: 'date field'};
  const role = el => el.getAttribute('role') ||
    ({A: 'link', BUTTON: 'button', SELECT: 'list', TEXTAREA: 'textbox', SUMMARY: 'button'})[el.tagName] ||
    (el.tagName === 'INPUT' ? (TYPES[el.type] || 'textbox') : el.isContentEditable ? 'textbox' : 'element');
  // The page's main content first, the rest (header, navigation, footer)
  // after it, so the first page of a read is what the page is about.
  const main = document.querySelector('main, [role=main]');
  const lines = [], outside = [];
  let count = start;
  // The element listed last: what lies inside it is part of it. Listed
  // elements never nest, and the walk is in document order.
  let listed = null;
  const given = new Set();
  const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_ELEMENT);
  for (let el = walker.currentNode; el; el = walker.nextNode()) {
    if (listed && listed !== el && listed.contains(el)) continue;
    const into = main && !main.contains(el) ? outside : lines;
    if (/^H[1-6]$/.test(el.tagName) || el.getAttribute('role') === 'heading') {
      if (shown(el) && clean(el.innerText)) into.push('heading "' + clip(clean(el.innerText), 200) + '"');
      continue;
    }
    if (el.tagName === 'IFRAME' && shown(el)) {
      into.push('frame ' + clip(el.src || '(inline)', 100) + ' (its content: open its address with the action open)');
      continue;
    }
    if (!el.matches(ACT) || !shown(el)) continue;
    listed = el;
    let ref = el.getAttribute('data-consens-ref');
    // A copied element (a framework's clone) brings its original's ref along.
    if (!/^e\d+$/.test(ref || '') || given.has(ref)) {
      ref = 'e' + (++count);
      el.setAttribute('data-consens-ref', ref);
    }
    given.add(ref);
    const kind = role(el);
    let label = name(el) || clean(el.value && el.type !== 'password' ? el.value : '');
    if (!label && el.tagName === 'A') label = clip(clean(el.getAttribute('href')), 60);
    if (!label) label = clean(el.getAttribute('name') || el.id || '');
    let line = '[' + ref + '] ' + kind + ' "' + clip(label, 200) + '"';
    if (el.tagName === 'SELECT') {
      const option = el.options[el.selectedIndex];
      line += ' selected="' + clip(clean(option ? option.text : ''), 60) + '"';
    } else if (el.type === 'checkbox' || el.type === 'radio' || el.getAttribute('aria-checked')) {
      line += (el.checked || el.getAttribute('aria-checked') === 'true') ? ' checked' : ' unchecked';
    } else if (el.type === 'password') {
      line += el.value ? ' (filled)' : ' (empty)';
    } else if ((el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') && el.type !== 'submit' && el.type !== 'button') {
      line += el.value ? ' value="' + clip(clean(el.value), 60) + '"' : ' (empty)';
    }
    if (el.disabled || el.getAttribute('aria-disabled') === 'true') line += ' disabled';
    if (el.getAttribute('aria-expanded')) line += el.getAttribute('aria-expanded') === 'true' ? ' expanded' : ' collapsed';
    into.push(line);
  }
  if (outside.length && lines.length) lines.push('(outside the main content: header, navigation, footer)');
  return {lines: lines.concat(outside), count};
}
"""

# find: what the page shows as one string, its whitespace folded. A text
# counts where its element is shown; a new block or a line break starts with
# a space, where innerText starts a new line. A place's ref is the one of the
# listed element it lies in (``refs``: what read listed just before).
FIND_JS = r"""
({query, refs, limit, around}) => {
  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'TEXTAREA', 'SELECT']);
  const seen = new Map();
  const shown = el => {
    if (!seen.has(el)) {
      const style = getComputedStyle(el);
      const box = el.getBoundingClientRect();
      seen.set(el, style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0);
    }
    return seen.get(el);
  };
  const blocks = new Map();
  const blockOf = el => {
    if (!blocks.has(el)) {
      let node = el;
      while (node.parentElement && /^(inline|contents)/.test(getComputedStyle(node).display)) node = node.parentElement;
      blocks.set(el, node);
    }
    return blocks.get(el);
  };
  const root = document.body || document.documentElement;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode: node => node.nodeType === 1 && SKIP.has(node.tagName) ? NodeFilter.FILTER_REJECT
      : NodeFilter.FILTER_ACCEPT
  });
  let full = '';
  const parts = [];
  let block = null, gap = false;
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (node.nodeType === 1) {
      if (node.tagName === 'BR') gap = true;
      continue;
    }
    const el = node.parentElement;
    if (!el || !shown(el)) continue;
    let text = node.data.replace(/\s+/g, ' ');
    const here = blockOf(el);
    if (block !== null && here !== block) gap = true;
    block = here;
    if (gap && full && !full.endsWith(' ') && !text.startsWith(' ')) full += ' ';
    gap = false;
    if (text.startsWith(' ') && (!full || full.endsWith(' '))) text = text.slice(1);
    if (!text) continue;
    parts.push([full.length, el]);
    full += text;
  }
  const wanted = new Set(refs);
  const refOf = el => {
    for (let node = el; node; node = node.parentElement) {
      const ref = node.getAttribute('data-consens-ref');
      if (ref && wanted.has(ref)) return ref;
    }
    return '';
  };
  const needle = query.replace(/\s+/g, ' ').trim();
  const pattern = new RegExp(needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
  const matches = [];
  let total = 0, part = 0, found;
  while ((found = pattern.exec(full))) {
    total += 1;
    if (matches.length >= limit) continue;
    const at = found.index, end = at + found[0].length;
    while (part + 1 < parts.length && parts[part + 1][0] <= at) part += 1;
    let from = Math.max(0, at - around), to = Math.min(full.length, end + around);
    if (from > 0) {
      const space = full.indexOf(' ', from);
      if (space !== -1 && space < at) from = space + 1;
    }
    if (to < full.length) {
      const space = full.lastIndexOf(' ', to);
      if (space >= end) to = space;
    }
    const snippet = (from > 0 ? '…' : '') + full.slice(from, to).trim() + (to < full.length ? '…' : '');
    matches.push({snippet, ref: refOf(parts[part][1])});
  }
  return {total, matches};
}
"""

IS_SECRET_JS = r"""el => el.type === 'password' || /password/i.test(el.autocomplete || '') ||
  /one-time-code/i.test(el.autocomplete || '')"""


class Refused(Exception):
    status = "refused"


class UserHasControl(Exception):
    status = "user"


class SettingUp(Exception):
    status = "setup"


def user_control():
    """Whether the user has the browser now (the view's takeover; it
    expires by itself when the view stops refreshing it)."""
    try:
        with open(CONTROL, encoding="utf-8") as handle:
            control = json.load(handle)
    except (OSError, ValueError):
        return False
    return control.get("holder") == "user" and float(control.get("until") or 0) > time.time()


def ensure_browser():
    """Installs the browser once (in this call: the VM sleeps between calls,
    and a setup left running in the background would sleep with it), then
    starts it unless it runs."""
    if not os.path.exists(SETUP_MARKER):
        try:
            subprocess.run(["bash", os.path.join(HERE, "setup.sh")], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=SETUP_SECONDS)
        except subprocess.TimeoutExpired:
            pass
        if not os.path.exists(SETUP_MARKER):
            raise SettingUp("The browser is being set up (once, about two minutes). Call browser again in a "
                            "minute.")
    started = subprocess.run(["bash", os.path.join(HERE, "display.sh")], capture_output=True, text=True, timeout=60)
    if started.returncode != 0:
        raise RuntimeError("The browser did not start: " + (started.stderr.strip() or "no reason given"))


def stay_awake():
    """The VM awake for AWAKE_FOR from now (an expiring Tasks API hold; the
    next call renews it). A failure only costs the hold."""
    try:
        subprocess.run(["curl", "-s", "--max-time", "5", "--unix-socket", API_SOCKET,
                        "-H", "Content-Type: application/json", "-X", "PUT",
                        f"http://sprite/v1/tasks/{AWAKE_TASK}", "-d", json.dumps({"expire": AWAKE_FOR})],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
    except Exception:
        pass


def restart_browser():
    """Chrome anew, its profile and tabs kept (display.sh --restart)."""
    started = subprocess.run(["bash", os.path.join(HERE, "display.sh"), "--restart"], capture_output=True, text=True,
                             stdin=subprocess.DEVNULL, timeout=RESTART_SECONDS)
    if started.returncode != 0:
        raise RuntimeError("The browser did not start again: " + (started.stderr.strip() or "no reason given"))


def connect(playwright):
    """The running Chrome; one fresh start when it does not take the
    connection (2026-10-28: connect_over_cdp ran into its limit, and every
    later call would have too)."""
    try:
        return playwright.chromium.connect_over_cdp(CDP, timeout=CONNECT_SECONDS * 1000)
    except Exception:
        restart_browser()
        return playwright.chromium.connect_over_cdp(CDP, timeout=CONNECT_SECONDS * 1000)


# The call's one answer on stdout: from main, or from the watchdog when the
# browser stopped answering (then main writes nothing).
_ANSWER_LOCK = threading.Lock()
_answered = False
_watchdog_done = threading.Event()
_timer = None


def answer_once(answer):
    global _answered
    with _ANSWER_LOCK:
        if _answered:
            return False
        _answered = True
    sys.stdout.write(json.dumps(answer))
    sys.stdout.flush()
    return True


def watchdog(seconds):
    """Ends the call after ``seconds`` when the browser did not answer, and
    restarts Chrome so that the next call finds one that does."""
    def expire():
        global _answered
        with _ANSWER_LOCK:
            if _answered:
                return
            _answered = True
        try:
            restart_browser()
            said = "it was restarted with its tabs and sign-ins"
        except Exception:
            said = "the next call starts it again"
        stay_awake()
        sys.stdout.write(json.dumps({"status": "failed", "text": (
            f"The browser did not answer within {seconds} s; {said}. Read the page again, or open it anew.")}))
        sys.stdout.flush()
        _watchdog_done.set()
        os._exit(0)
    global _timer
    _timer = threading.Timer(seconds, expire)
    _timer.daemon = True
    _timer.start()
    return _timer


def current_page(context):
    """The tab the user sees (its document is visible), else the newest."""
    pages = [page for page in context.pages if not page.is_closed()]
    if not pages:
        return context.new_page()
    for page in reversed(pages):
        try:
            if page.evaluate("document.visibilityState") == "visible":
                return page
        except Exception:
            continue
    return pages[-1]


def settle(page):
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10_000)
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=2_000)
    except Exception:
        pass


def saved_sign_in(page):
    """Whether the browser holds cookies for the page's address, "yes" or
    "no"; None for a page with no web address or when it cannot tell. Only
    that: never a cookie's name, value or their number. Said as cookies, not
    as a sign-in: consent and bot-protection cookies are cookies too."""
    url = str(page.url or "")
    if not url.startswith(("http://", "https://")):
        return None
    try:
        return "yes" if page.context.cookies([url]) else "no"
    except Exception:
        return None


def header(page):
    try:
        title = page.title()
    except Exception:
        title = ""
    lines = [f'Page: "{title}"', f"URL: {page.url}"]
    saved = saved_sign_in(page)
    if saved:
        lines.append(f"Cookies saved for this site: {saved}")
    return "\n".join(lines)


def page_lines(page):
    try:
        with open(REF_COUNTER, encoding="utf-8") as handle:
            start = int(handle.read().strip() or 0)
    except (OSError, ValueError):
        start = 0
    result = page.evaluate(SNAPSHOT_JS, start)
    if result["count"] != start:
        os.makedirs(os.path.dirname(REF_COUNTER), exist_ok=True)
        with open(REF_COUNTER, "w", encoding="utf-8") as handle:
            handle.write(str(result["count"]))
    return result["lines"]


def paged(lines, offset, limit_chars):
    """Lines from ``offset`` up to ``limit_chars``, and how many follow."""
    shown, size = [], 0
    for line in lines[offset:]:
        if size + len(line) + 1 > limit_chars and shown:
            break
        shown.append(line)
        size += len(line) + 1
    rest = len(lines) - offset - len(shown)
    return shown, rest


def read_text(page, offset=0, limit=READ_CHARS):
    if hidden(page):
        return hidden_text(page)
    lines = page_lines(page)
    shown, rest = paged(lines, offset, limit)
    out = [header(page), "\n".join(shown) if shown else
           "(no headings or elements to act on; read the page with the action text)"]
    if rest > 0:
        out.append(f"(… {rest} more lines: read with offset {offset + len(shown)})")
    return "\n".join(out)


# text: the main content's text and the whole page's, so the main content
# comes first as in read (2026-10-28: Wikipedia's text began with its menus).
TEXT_JS = r"""
() => {
  const main = document.querySelector('main, [role=main]');
  return {main: main ? main.innerText || '' : '', all: (document.body || document.documentElement).innerText || ''};
}
"""


def page_text(page, offset):
    if hidden(page):
        return hidden_text(page)
    texts = page.evaluate(TEXT_JS)
    split = lambda text: [line.strip() for line in str(text or "").splitlines() if line.strip()]
    main, lines = split(texts.get("main")), split(texts.get("all"))
    if main:
        # The rest of the page after it, without the main content's lines again.
        inside = set(main)
        rest = [line for line in lines if line not in inside]
        lines = main + (["(outside the main content: header, navigation, footer)"] + rest if rest else [])
    shown, rest = paged(lines, offset, TEXT_CHARS)
    out = [header(page), "\n".join(shown) if shown else "(the page shows no text)"]
    if rest > 0:
        out.append(f"(… {rest} more lines: text with offset {offset + len(shown)})")
    return "\n".join(out)


def find_query(request):
    """find's text with its whitespace folded, or Refused."""
    query = " ".join(str(request.get("text") or "").split())
    if not 1 <= len(query) <= FIND_CHARS:
        raise Refused(f"find needs text, 1 to {FIND_CHARS} characters.")
    return query


def listed_refs(lines):
    """The refs of read's lines (an element's line starts with its ref)."""
    return [match.group(1) for match in (re.match(r"\[(e\d+)\] ", line) for line in lines) if match]


# An element's line of read: its ref and its name, '[e12] link "Name" ...'.
ELEMENT_NAME = re.compile(r'\[(e\d+)\] [^"]*"(.*?)"(?= |$)')


def find_text(page, query):
    """Where ``query`` stands in what the page shows (any case): the first
    FIND_MATCHES places, each with the page around it and the ref of the
    element it lies in when read lists one. The refs come from read itself,
    so they are the ones read gives."""
    lines = page_lines(page)
    found = page.evaluate(FIND_JS, {"query": query, "refs": listed_refs(lines), "limit": FIND_MATCHES,
                                    "around": FIND_AROUND})
    total, matches = int(found.get("total") or 0), found.get("matches") or []
    # Elements whose name holds it (a search box named only by its label or
    # placeholder is in no page text, 2026-10-28), as read lists them.
    seen = {str(match.get("ref") or "") for match in matches}
    named = [line for line in lines if (name := ELEMENT_NAME.match(line)) and name.group(1) not in seen
             and query.casefold() in name.group(2).casefold()][:FIND_MATCHES]
    out = [header(page)]
    if not total and not named:
        out.append(f'"{query}" is neither in the text the page shows nor in the name of an element.')
        return "\n".join(out)
    if total:
        counted = "1 match" if total == 1 else f"{total} matches"
        out.append(f'{counted} for "{query}"' + (f", the first {len(matches)}:" if total > len(matches) else ":"))
    for match in matches:
        ref = str(match.get("ref") or "")
        out.append((f"[{ref}] " if ref else "") + f'"{match.get("snippet") or ""}"')
    if named:
        out.append(f'Elements whose name holds "{query}":')
        out.extend(named)
    return "\n".join(out)


def element(page, ref):
    if not isinstance(ref, str) or not ref.startswith("e") or not ref[1:].isdigit():
        raise Refused(f"{ref} is no ref: take one from read (like e12).")
    locator = page.locator(f'[data-consens-ref="{ref}"]')
    if locator.count() == 0:
        raise Refused(f"{ref} is not on the page any more (it changed). Call read for the current refs.")
    return locator.first


def point(x, y):
    """x, y as whole pixels of the viewport, or Refused."""
    if not all(type(value) is int and 0 <= value <= MAX_COORDINATE for value in (x, y)):
        raise Refused(f"A place needs x and y, whole pixels of the screenshot (0 to {MAX_COORDINATE}).")
    return x, y


def drag(page, strokes):
    """Each stroke: press the mouse at its first point, move through the
    others, release at the last (drawing, a slider, drag and drop). Between
    two points the mouse moves in small steps, as a hand would, so a canvas
    gets a line and not two dots."""
    if not isinstance(strokes, list) or not 1 <= len(strokes) <= MAX_STROKES:
        raise Refused(f"drag needs strokes: 1 to {MAX_STROKES}, each a list of x,y points of the screenshot.")
    total = 0
    paths = []
    for stroke in strokes:
        if not isinstance(stroke, list) or not 2 <= len(stroke) <= MAX_STROKE_POINTS:
            raise Refused(f"Each stroke needs 2 to {MAX_STROKE_POINTS} points.")
        paths.append([point(*pair) if isinstance(pair, list) and len(pair) == 2 else point(None, None)
                      for pair in stroke])
        total += len(stroke)
    if total > MAX_POINTS:
        raise Refused(f"At most {MAX_POINTS} points in one drag.")
    for path in paths:
        page.mouse.move(*path[0])
        page.mouse.down()
        last = path[0]
        for x, y in path[1:]:
            steps = max(1, int(max(abs(x - last[0]), abs(y - last[1])) / DRAG_STEP_PIXELS))
            page.mouse.move(x, y, steps=steps)
            last = (x, y)
        page.mouse.up()
    count = "1 stroke" if len(paths) == 1 else f"{len(paths)} strokes"
    return f"Dragged {count} ({total} points)."


def safe_name(name):
    """A download's file name without folders or odd characters."""
    name = re.sub(r"[^\w.\- ]", "_", os.path.basename(str(name or "").replace("\\", "/"))).strip(". ")
    return name[:120] or "download"


def free_path(folder, name):
    os.makedirs(folder, exist_ok=True)
    stem, dot, ext = name.rpartition(".") if "." in name else (name, "", "")
    path, number = os.path.join(folder, name), 2
    while os.path.exists(path):
        path = os.path.join(folder, f"{stem} ({number}){dot}{ext}")
        number += 1
    return path


def keep_downloads(caught):
    """The downloads this action started, saved in DOWNLOADS once complete;
    their names."""
    names = []
    for download in caught:
        path = free_path(DOWNLOADS, safe_name(download.suggested_filename))
        try:
            download.save_as(path)
        except Exception:
            continue
        names.append(os.path.basename(path))
    return names


# localhost is the workbench's where the tunnel holds the port (tunnel.py,
# agent_tunnel.py), named by the server with every request (local_ports).
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
OWN_COMPUTER = ("This page is on the browser's own computer, which you do not read. Open a page of the web, or "
                "http://localhost:<port> for a port of your workspace.")
# The ports the tunnel holds for this request (run).
LOCAL_PORTS = set()


def hidden(page):
    return own_computer(str(getattr(page, "url", "") or ""), LOCAL_PORTS)


def hidden_text(page):
    """What the agent learns of such a page: its address, never its title or text."""
    return f"URL: {page.url}\n{OWN_COMPUTER}"


def own_computer(url, local_ports=()):
    """Whether the page at ``url`` is the browser's own computer or a
    private network (its debugging port, a link or a redirect there): never
    read nor shown to the agent. Since 2026-10-29 for every page, not only
    for an address the agent opens; localhost on a port the tunnel holds is
    the workbench's."""
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        return False
    host = (parts.hostname or "").lower().rstrip(".")
    if host in LOCAL_HOSTS:
        try:
            return parts.port not in local_ports
        except ValueError:
            return True
    return not public_address(url)


def public_address(url):
    """Only an http(s) address of the open web: never the browser's own
    computer (its debugging port) nor a private network."""
    import ipaddress
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().rstrip(".")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    return (parts.scheme in {"http", "https"} and bool(host) and host != "localhost"
            and not host.endswith((".localhost", ".internal", ".flycast"))
            and (address is None or address.is_global))


def fetch(context, page, url):
    """download: the file at ``url`` (else the current page's address) with
    the browser's sign-ins, as Chrome would send its cookies; a PDF Chrome
    shows in its viewer comes as the file this way."""
    target = url or page.url
    if not public_address(target):
        raise Refused("download takes the address of a file on the web (or the current page's).")
    response = context.request.get(target, timeout=DOWNLOAD_SECONDS * 1000, max_redirects=10)
    if not public_address(response.url):
        raise Refused("That download leads to the browser's own computer or a private network.")
    if not response.ok:
        raise Refused(f"The download failed: HTTP {response.status}.")
    body = response.body()
    disposition = response.headers.get("content-disposition", "")
    named = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", disposition, re.I)
    from urllib.parse import unquote, urlsplit
    name = safe_name(unquote(named.group(1)) if named else unquote(urlsplit(response.url).path.rsplit("/", 1)[-1]))
    path = free_path(DOWNLOADS, name)
    with open(path, "wb") as handle:
        handle.write(body)
    return f"Downloaded {os.path.basename(path)} ({len(body)} bytes)."


def finished_downloads():
    """The files waiting for the server: what this helper saved and what
    Chrome finished in its own folder (the user's downloads in the view)."""
    if os.path.isdir(CHROME_DOWNLOADS):
        for name in sorted(os.listdir(CHROME_DOWNLOADS)):
            source = os.path.join(CHROME_DOWNLOADS, name)
            if os.path.isfile(source) and not name.endswith((".crdownload", ".tmp")):
                try:
                    os.replace(source, free_path(DOWNLOADS, safe_name(name)))
                except OSError:
                    pass
    if not os.path.isdir(DOWNLOADS):
        return []
    return [{"file": os.path.join(DOWNLOADS, name), "name": name,
             "bytes": os.path.getsize(os.path.join(DOWNLOADS, name))}
            for name in sorted(os.listdir(DOWNLOADS)) if os.path.isfile(os.path.join(DOWNLOADS, name))]


def run(request):
    action = request.get("action")
    if action not in ACTIONS:
        raise Refused(f"Unknown action {action}.")
    if action in ACTING and user_control():
        raise UserHasControl("The user has taken over the browser in the workspace view. Do not act in it now: "
                             "your next call waits until they hand it back, or answer with what you have.")
    query = find_query(request) if action == "find" else ""
    LOCAL_PORTS.clear()
    LOCAL_PORTS.update(port for port in request.get("local_ports") or () if type(port) is int)
    ensure_browser()
    if action == "warm":
        # The server's own start of the browser while the workbench gets
        # ready (agent_browser.BrowserTools._warm, since 2026-10-29): it
        # reads nothing of the pages, and the agent never asks for it.
        return {"text": ""}
    # A first setup installed Playwright into the user's site folder, which
    # Python only looks at when it exists at its start.
    import importlib
    import site
    site.addsitedir(site.getusersitepackages())
    importlib.invalidate_caches()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = connect(playwright)
        watchdog(CALL_LIMIT + (min(WAIT_MAX, max(1, int(request.get("seconds") or 30))) if action == "wait" else 0)
                 + (DOWNLOAD_SECONDS if action == "download" else 0))
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = current_page(context)
        offset = int(request.get("offset") or 0)
        # A download this action starts, in any tab, also one it opens.
        # A function of its own: Playwright marks each handler, which a
        # builtin like list.append does not allow (every action failed).
        caught = []

        def catch(download):
            caught.append(download)

        def watch(tab):
            tab.on("download", catch)
        for tab in context.pages:
            watch(tab)
        context.on("page", watch)
        if action == "read":
            return {"text": read_text(page, offset)}
        if action == "text":
            return {"text": page_text(page, offset)}
        if action == "find":
            if hidden(page):
                return {"text": hidden_text(page)}
            return {"text": find_text(page, query)}
        if action == "tabs":
            lines = []
            for number, tab in enumerate(context.pages, 1):
                try:
                    title = "" if hidden(tab) else tab.title()
                except Exception:
                    title = ""
                lines.append(f"{'*' if tab == page else ' '}{number}. \"{title[:80]}\" {tab.url[:160]}")
            lines.append("(* = the tab in front; switch with the action tab)")
            return {"text": "\n".join(lines)}
        if action == "screenshot":
            if hidden(page):
                raise Refused(OWN_COMPUTER)
            line, png = picture(page)
            return {"text": header(page) + "\n" + line, "png": png}
        if action == "wait":
            seconds = min(WAIT_MAX, max(1, int(request.get("seconds") or 30)))
            deadline, held = time.time() + seconds, user_control()
            while time.time() < deadline:
                time.sleep(1)
                if held and not user_control():
                    break
            said = ("The user still has the browser.\n" if user_control() else
                    "The user handed the browser back.\n" if held else "")
            page = current_page(context)
            settle(page)
            return with_picture(page, request, {"text": said + read_text(page, 0, AFTER_ACTION_CHARS)})
        done = act(context, page, action, request)
        page = current_page(context)
        settle(page)
        saved = keep_downloads(caught)
        if saved:
            done += "\nDownloaded: " + ", ".join(saved) + "."
        return with_picture(page, request, {"text": done + "\n" + read_text(page, 0, AFTER_ACTION_CHARS)})


def picture(page):
    """(the line that says its size, the PNG as base64) of the page now. It
    is the viewport, one pixel per CSS pixel: its x,y are what click and drag
    take."""
    png = page.screenshot(type="png")
    width, height = page.evaluate("() => [window.innerWidth, window.innerHeight]")
    return f"Picture: {width}x{height} pixels, the x,y that click and drag take.", base64.b64encode(png).decode()


def with_picture(page, request, answer):
    """An action's answer, with the picture of the page after it when the
    agent asked for it (screenshot_after, since 2026-10-29): before, every
    move on a page drawn on a canvas took a call of its own to look."""
    if not request.get("screenshot_after") or hidden(page):
        return answer
    line, png = picture(page)
    return {**answer, "text": answer["text"] + "\n" + line, "png": png}


def act(context, page, action, request):
    """One action that changes the page; returns what it did."""
    if action == "open":
        target = str(request.get("url") or "")
        if not target:
            raise Refused("open needs a URL.")
        if request.get("new_tab"):
            page = context.new_page()
        page.bring_to_front()
        try:
            # Until the address answers; its document may still be coming.
            page.goto(target, wait_until="commit", timeout=OPEN_SECONDS * 1000)
        except Exception as exc:
            # An address that downloads a file instead of showing a page.
            if "Download is starting" in str(exc):
                return f"Opened {target}: it downloads a file."
            if "Timeout" in str(exc):
                raise RuntimeError(f"{target} did not answer within {OPEN_SECONDS} s.") from None
            raise
        try:
            page.wait_for_load_state("domcontentloaded", timeout=LOADED_SECONDS * 1000)
        except Exception:
            return f"Opened {page.url} (still loading: this is what it shows so far)"
        return f"Opened {page.url}"
    if action == "download":
        return fetch(context, page, str(request.get("url") or ""))
    if action == "click":
        if request.get("ref"):
            element(page, request.get("ref")).click(timeout=10_000)
            return f"Clicked {request.get('ref')}."
        # A place on the page as the screenshot shows it (CSS pixels of the
        # viewport): for what read lists no element of, such as a canvas,
        # a map or an app drawn in one (since 2026-10-28).
        x, y = point(request.get("x"), request.get("y"))
        page.mouse.click(x, y)
        return f"Clicked at {x},{y}."
    if action == "drag":
        return drag(page, request.get("strokes"))
    if action == "type":
        ref, text = request.get("ref"), str(request.get("text") or "")
        target = element(page, ref)
        if target.evaluate(IS_SECRET_JS):
            raise Refused("That is a password or code field: only the user types those. Hand the browser to them "
                          "with ask_user (browser) to sign in, then go on.")
        if target.evaluate("el => el.isContentEditable"):
            target.click(timeout=10_000)
            page.keyboard.insert_text(text)
        else:
            target.fill(text, timeout=10_000)
        if request.get("enter"):
            # The field has the focus: Enter through the keyboard, like the
            # action key. Pressed on the element it waited up to 30 s while a
            # suggestion list covered it (2026-10-28, Wikipedia's search).
            page.keyboard.press("Enter")
        return f"Typed into {ref}" + (" and pressed Enter." if request.get("enter") else ".")
    if action == "select":
        ref, choice = request.get("ref"), str(request.get("option") or "")
        target = element(page, ref)
        try:
            target.select_option(label=choice, timeout=5_000)
        except Exception:
            target.select_option(choice, timeout=5_000)
        return f"Selected \"{choice}\" in {ref}."
    if action == "upload":
        ref, path = request.get("ref"), str(request.get("file") or "")
        # Only a file the server put here for this call.
        if os.path.dirname(os.path.abspath(path)) != os.path.abspath(UPLOADS) or not os.path.isfile(path):
            raise Refused("The file to upload is missing.")
        element(page, ref).set_input_files(path, timeout=10_000)
        return f"Put {os.path.basename(path)} into {ref}."
    if action == "key":
        key = str(request.get("key") or "")
        if key not in KEYS:
            raise Refused("key takes one of: " + ", ".join(sorted(KEYS)) + ". Text goes in with the action type.")
        page.keyboard.press(key)
        return f"Pressed {key}."
    if action == "scroll":
        direction = -1 if request.get("direction") == "up" else 1
        page.evaluate("d => window.scrollBy(0, d * window.innerHeight * 0.8)", direction)
        return "Scrolled " + ("up." if direction < 0 else "down.")
    if action in {"back", "forward"}:
        (page.go_back if action == "back" else page.go_forward)(wait_until="domcontentloaded", timeout=15_000)
        return f"Went {action}."
    if action == "tab":
        pages = context.pages
        number = int(request.get("tab") or 0)
        if not 1 <= number <= len(pages):
            raise Refused(f"There is no tab {number}; the action tabs lists them.")
        pages[number - 1].bring_to_front()
        return f"Tab {number} is in front."
    raise Refused(f"Unknown action {action}.")


def main():
    global _answered
    # One call per process on the VM; tests call main again in one process.
    with _ANSWER_LOCK:
        _answered = False
    _watchdog_done.clear()
    try:
        request = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
        if not isinstance(request, dict):
            raise Refused("The request is no JSON object.")
        answer = {"status": "ok", **run(request)}
        answer["downloads"] = finished_downloads()
    except (Refused, UserHasControl, SettingUp) as exc:
        answer = {"status": exc.status, "text": str(exc)}
    except Exception as exc:
        message = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        answer = {"status": "failed", "text": message[:400]}
    if _timer is not None:
        _timer.cancel()
    stay_awake()
    if not answer_once(answer):
        # The watchdog answered: it ends the process once Chrome restarted.
        _watchdog_done.wait(RESTART_SECONDS + 10)
    return 0


if __name__ == "__main__":
    sys.exit(main())
