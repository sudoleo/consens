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
type, select and upload take; every action prints the page again, so the
agent sees what changed in the same step.

Two things the agent never does here: type into a password field (the user
signs in in the live view), and act while the user has taken over the
browser (CONTROL, written by consens.io's server, which also holds the
agent's calls meanwhile).
"""
import base64
import json
import os
import subprocess
import sys
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
WAIT_MAX = 120
# A first setup in one call, within the server's limit (agent_browser.CALL_SECONDS).
SETUP_SECONDS = 100
KEYS = {"Enter", "Tab", "Escape", "Backspace", "Delete", "Space", "ArrowUp", "ArrowDown", "ArrowLeft",
        "ArrowRight", "PageUp", "PageDown", "Home", "End", "Shift+Tab"}
ACTIONS = {"open", "read", "text", "click", "type", "select", "key", "scroll", "back", "forward", "tabs", "tab",
           "screenshot", "upload", "wait"}
# What changes the page or sends something: never while the user has the browser.
ACTING = {"open", "click", "type", "select", "upload", "key", "scroll", "back", "forward", "tab"}

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
  const lines = [];
  let count = start;
  // The element listed last: what lies inside it is part of it. Listed
  // elements never nest, and the walk is in document order.
  let listed = null;
  const given = new Set();
  const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_ELEMENT);
  for (let el = walker.currentNode; el; el = walker.nextNode()) {
    if (listed && listed !== el && listed.contains(el)) continue;
    if (/^H[1-6]$/.test(el.tagName) || el.getAttribute('role') === 'heading') {
      if (shown(el) && clean(el.innerText)) lines.push('heading "' + clip(clean(el.innerText), 120) + '"');
      continue;
    }
    if (el.tagName === 'IFRAME' && shown(el)) {
      lines.push('frame ' + clip(el.src || '(inline)', 100) + ' (its content: open its address with the action open)');
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
    let line = '[' + ref + '] ' + kind + ' "' + clip(label, 80) + '"';
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
    lines.push(line);
  }
  return {lines, count};
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


def header(page):
    try:
        title = page.title()
    except Exception:
        title = ""
    return f'Page: "{title}"\nURL: {page.url}'


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
    lines = page_lines(page)
    shown, rest = paged(lines, offset, limit)
    out = [header(page), "\n".join(shown) if shown else
           "(no headings or elements to act on; read the page with the action text)"]
    if rest > 0:
        out.append(f"(… {rest} more lines: read with offset {offset + len(shown)})")
    return "\n".join(out)


def page_text(page, offset):
    text = page.evaluate("() => (document.body || document.documentElement).innerText || ''")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    shown, rest = paged(lines, offset, TEXT_CHARS)
    out = [header(page), "\n".join(shown) if shown else "(the page shows no text)"]
    if rest > 0:
        out.append(f"(… {rest} more lines: text with offset {offset + len(shown)})")
    return "\n".join(out)


def element(page, ref):
    if not isinstance(ref, str) or not ref.startswith("e") or not ref[1:].isdigit():
        raise Refused(f"{ref} is no ref: take one from read (like e12).")
    locator = page.locator(f'[data-consens-ref="{ref}"]')
    if locator.count() == 0:
        raise Refused(f"{ref} is not on the page any more (it changed). Call read for the current refs.")
    return locator.first


def run(request):
    action = request.get("action")
    if action not in ACTIONS:
        raise Refused(f"Unknown action {action}.")
    if action in ACTING and user_control():
        raise UserHasControl("The user has taken over the browser in the workspace view. Do not act in it now: "
                             "your next call waits until they hand it back, or answer with what you have.")
    ensure_browser()
    # A first setup installed Playwright into the user's site folder, which
    # Python only looks at when it exists at its start.
    import importlib
    import site
    site.addsitedir(site.getusersitepackages())
    importlib.invalidate_caches()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(CDP, timeout=20_000)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = current_page(context)
        offset = int(request.get("offset") or 0)
        if action == "read":
            return {"text": read_text(page, offset)}
        if action == "text":
            return {"text": page_text(page, offset)}
        if action == "tabs":
            lines = []
            for number, tab in enumerate(context.pages, 1):
                try:
                    title = tab.title()
                except Exception:
                    title = ""
                lines.append(f"{'*' if tab == page else ' '}{number}. \"{title[:80]}\" {tab.url[:160]}")
            lines.append("(* = the tab in front; switch with the action tab)")
            return {"text": "\n".join(lines)}
        if action == "screenshot":
            png = page.screenshot(type="png")
            return {"text": header(page), "png": base64.b64encode(png).decode()}
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
            return {"text": said + read_text(page, 0, AFTER_ACTION_CHARS)}
        done = act(context, page, action, request)
        page = current_page(context)
        settle(page)
        return {"text": done + "\n" + read_text(page, 0, AFTER_ACTION_CHARS)}


def act(context, page, action, request):
    """One action that changes the page; returns what it did."""
    if action == "open":
        target = str(request.get("url") or "")
        if not target:
            raise Refused("open needs a URL.")
        if request.get("new_tab"):
            page = context.new_page()
        page.bring_to_front()
        page.goto(target, wait_until="domcontentloaded", timeout=30_000)
        return f"Opened {page.url}"
    if action == "click":
        element(page, request.get("ref")).click(timeout=10_000)
        return f"Clicked {request.get('ref')}."
    if action == "type":
        ref, text = request.get("ref"), str(request.get("text") or "")
        target = element(page, ref)
        if target.evaluate(IS_SECRET_JS):
            raise Refused("That is a password or code field: only the user types those. Ask the user to sign in "
                          "themselves in the workspace view, then go on.")
        if target.evaluate("el => el.isContentEditable"):
            target.click(timeout=10_000)
            page.keyboard.insert_text(text)
        else:
            target.fill(text, timeout=10_000)
        if request.get("enter"):
            target.press("Enter")
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
    try:
        request = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
        if not isinstance(request, dict):
            raise Refused("The request is no JSON object.")
        answer = {"status": "ok", **run(request)}
    except (Refused, UserHasControl, SettingUp) as exc:
        answer = {"status": exc.status, "text": str(exc)}
    except Exception as exc:
        message = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        answer = {"status": "failed", "text": message[:400]}
    sys.stdout.write(json.dumps(answer))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
