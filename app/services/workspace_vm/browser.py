"""consens.io workspace: `browser`, the agent's way to use the workspace's
Chrome from the shell (agent_workspace.py, AGENT_VM_PROMPT).

The same Chrome the user sees and steers in the live view, with the
sign-ins the user made there. Pages are read as text: `read` lists the
page's headings and the elements one can act on, each with a ref (e12) that
click, type, select and upload take; every action prints the page again, so
the agent sees what changed in the same step. A screenshot only when the
text does not tell enough.

Two things the agent never does here: type into a password field (the user
signs in in the live view), and act while the user has taken over the
browser (CONTROL, written by consens.io's server): it waits with `wait`.

Exit codes: 0 done, 1 failed, 2 refused, 3 the user has the browser, 4 the
browser is still being set up.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
SETUP_MARKER = os.path.join(HOME, ".consens/workspace/setup-done-2")
CONTROL = os.path.join(HOME, ".consens/workspace/control.json")
# The last ref given in this workspace: refs are never given twice.
REF_COUNTER = os.path.join(HOME, ".consens/workspace/ref-count")
CDP = "http://127.0.0.1:9222"
READ_CHARS = 6000
AFTER_ACTION_CHARS = 4000
TEXT_CHARS = 12000
WAIT_MAX = 120
KEYS = {"Enter", "Tab", "Escape", "Backspace", "Delete", "Space", "ArrowUp", "ArrowDown", "ArrowLeft",
        "ArrowRight", "PageUp", "PageDown", "Home", "End", "Shift+Tab"}

USAGE = """usage: browser <command>
  open <url> [--new]       go to a page (--new: in a new tab)
  read [--offset N]        the page's headings and elements with refs
  text [--offset N]        the page's text, to read it
  click <ref>              click an element (ref from read, e.g. e12)
  type <ref> <text> [--enter]   fill a field (never a password)
  select <ref> <option>    choose an option of a list
  upload <ref> <file>      put a file of the VM into a file field
  key <key>                press Enter, Tab, Escape, ArrowDown, PageDown, ...
  scroll up|down           scroll the page
  back | forward           history of the tab
  tabs | tab <n> | close-tab [n]
  screenshot [file]        save a PNG of the visible page (look at it with vm_view_image)
  wait [seconds]           wait (up to 120 s), also until the user hands the browser back
  status                   setup, page and who has the browser"""

# A ref stays with its element, and a new element takes the next number of
# the workspace (``start``, REF_COUNTER). Until 2026-10-27 every read numbered
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
      lines.push('frame ' + clip(el.src || '(inline)', 100) + ' (its content: open it with browser open)');
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
    code = 2


class UserHasControl(Exception):
    code = 3


class SettingUp(Exception):
    code = 4


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
    """Installs the browser once, then starts it unless it runs."""
    if not os.path.exists(SETUP_MARKER):
        subprocess.Popen(["setsid", "bash", os.path.join(HERE, "setup.sh")], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
        for _ in range(45):
            if os.path.exists(SETUP_MARKER):
                break
            time.sleep(1)
        else:
            raise SettingUp("The browser is being set up (once, about a minute). Run the command again in a minute.")
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
    """Lines from ``offset`` up to ``limit_chars``, and a hint to read on."""
    shown, size = [], 0
    for line in lines[offset:]:
        if size + len(line) + 1 > limit_chars and shown:
            break
        shown.append(line)
        size += len(line) + 1
    rest = len(lines) - offset - len(shown)
    return shown, rest


def print_read(page, offset=0, limit=READ_CHARS, command="read"):
    lines = page_lines(page)
    shown, rest = paged(lines, offset, limit)
    print(header(page))
    print("\n".join(shown) if shown else "(no headings or elements to act on; read the page with: browser text)")
    if rest > 0:
        print(f"(… {rest} more lines: browser {command} --offset {offset + len(shown)})")


def print_text(page, offset):
    text = page.evaluate("() => (document.body || document.documentElement).innerText || ''")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    shown, rest = paged(lines, offset, TEXT_CHARS)
    print(header(page))
    print("\n".join(shown) if shown else "(the page shows no text)")
    if rest > 0:
        print(f"(… {rest} more lines: browser text --offset {offset + len(shown)})")


def element(page, ref):
    if not ref.startswith("e") or not ref[1:].isdigit():
        raise Refused(f"{ref} is no ref: take one from browser read (like e12).")
    locator = page.locator(f'[data-consens-ref="{ref}"]')
    if locator.count() == 0:
        raise Refused(f"{ref} is not on the page any more (it changed). Run browser read for the current refs.")
    return locator.first


def option_value(args, name):
    if name in args:
        index = args.index(name)
        if index + 1 < len(args) and args[index + 1].isdigit():
            return int(args[index + 1])
    return 0


def run(args):
    if not args or args[0] in {"-h", "--help", "help"}:
        print(USAGE)
        return 0
    command, rest = args[0], args[1:]
    acting = command in {"open", "click", "type", "select", "upload", "key", "scroll", "back", "forward", "tab",
                         "close-tab"}
    if acting and user_control():
        raise UserHasControl("The user has taken over the browser in the workspace view. Do not act in it now: "
                             "wait with `browser wait 60` until they hand it back, or answer with what you have.")
    ensure_browser()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(CDP, timeout=20_000)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = current_page(context)
        if command == "status":
            print("Browser: running. " + ("The user has it now (taken over in the view)." if user_control()
                                          else "You may use it."))
            print(header(page))
            print(f"Tabs: {len(context.pages)}")
            return 0
        if command == "read":
            print_read(page, option_value(rest, "--offset"))
            return 0
        if command == "text":
            print_text(page, option_value(rest, "--offset"))
            return 0
        if command == "tabs":
            for number, tab in enumerate(context.pages, 1):
                marker = "*" if tab == page else " "
                try:
                    title = tab.title()
                except Exception:
                    title = ""
                print(f"{marker}{number}. \"{title[:80]}\" {tab.url[:160]}")
            print("(* = the tab in front; switch with: browser tab <n>)")
            return 0
        if command == "screenshot":
            path = os.path.abspath(rest[0] if rest else "screenshot.png")
            page.screenshot(path=path, type="png")
            print(f"Saved {path} ({page.url}). Look at it with vm_view_image.")
            return 0
        if command == "wait":
            seconds = min(WAIT_MAX, max(1, int(rest[0]) if rest and rest[0].isdigit() else 30))
            deadline, held = time.time() + seconds, user_control()
            while time.time() < deadline:
                time.sleep(1)
                if held and not user_control():
                    break
            if user_control():
                print("The user still has the browser.")
            elif held:
                print("The user handed the browser back.")
            page = current_page(context)
            settle(page)
            print_read(page, 0, AFTER_ACTION_CHARS)
            return 0
        done = act(context, page, command, rest)
        page = current_page(context)
        settle(page)
        print(done)
        print_read(page, 0, AFTER_ACTION_CHARS)
        return 0


def act(context, page, command, rest):
    """One action; returns what it did."""
    if command == "open":
        target = next((arg for arg in rest if not arg.startswith("--")), "")
        if not target:
            raise Refused("open needs a URL.")
        if "://" not in target and not target.startswith("about:"):
            target = "https://" + target
        if "--new" in rest:
            page = context.new_page()
        page.bring_to_front()
        page.goto(target, wait_until="domcontentloaded", timeout=30_000)
        return f"Opened {page.url}"
    if command == "click":
        if not rest:
            raise Refused("click needs a ref.")
        element(page, rest[0]).click(timeout=10_000)
        return f"Clicked {rest[0]}."
    if command == "type":
        if len(rest) < 2:
            raise Refused('type needs a ref and the text: browser type e7 "text"')
        target = element(page, rest[0])
        if target.evaluate(IS_SECRET_JS):
            raise Refused("That is a password or code field: only the user types those. Ask the user to sign in "
                          "themselves in the workspace view, then go on.")
        text = " ".join(arg for arg in rest[1:] if arg != "--enter")
        if target.evaluate("el => el.isContentEditable"):
            target.click(timeout=10_000)
            page.keyboard.insert_text(text)
        else:
            target.fill(text, timeout=10_000)
        if "--enter" in rest:
            target.press("Enter")
        return f"Typed into {rest[0]}" + (" and pressed Enter." if "--enter" in rest else ".")
    if command == "select":
        if len(rest) < 2:
            raise Refused("select needs a ref and an option.")
        target, choice = element(page, rest[0]), " ".join(rest[1:])
        try:
            target.select_option(label=choice, timeout=5_000)
        except Exception:
            target.select_option(choice, timeout=5_000)
        return f"Selected \"{choice}\" in {rest[0]}."
    if command == "upload":
        if len(rest) < 2:
            raise Refused("upload needs a ref and a file of the VM.")
        path = os.path.abspath(rest[1])
        if not os.path.isfile(path):
            raise Refused(f"No file at {path}.")
        element(page, rest[0]).set_input_files(path, timeout=10_000)
        return f"Put {path} into {rest[0]}."
    if command == "key":
        key = rest[0] if rest else ""
        if key not in KEYS:
            raise Refused("key takes one of: " + ", ".join(sorted(KEYS)) + ". Text goes in with browser type.")
        page.keyboard.press(key)
        return f"Pressed {key}."
    if command == "scroll":
        direction = -1 if rest and rest[0] == "up" else 1
        page.evaluate("d => window.scrollBy(0, d * window.innerHeight * 0.8)", direction)
        return "Scrolled " + ("up." if direction < 0 else "down.")
    if command in {"back", "forward"}:
        (page.go_back if command == "back" else page.go_forward)(wait_until="domcontentloaded", timeout=15_000)
        return f"Went {command}."
    if command in {"tab", "close-tab"}:
        pages = context.pages
        number = int(rest[0]) if rest and rest[0].isdigit() else (pages.index(page) + 1)
        if not 1 <= number <= len(pages):
            raise Refused(f"There is no tab {number}; browser tabs lists them.")
        if command == "tab":
            pages[number - 1].bring_to_front()
            return f"Tab {number} is in front."
        pages[number - 1].close()
        remaining = [tab for tab in context.pages if not tab.is_closed()]
        if remaining:
            remaining[-1].bring_to_front()
        return f"Closed tab {number}."
    raise Refused(f"Unknown command {command}.\n{USAGE}")


def main():
    try:
        return run(sys.argv[1:])
    except (Refused, UserHasControl, SettingUp) as exc:
        print(str(exc))
        return exc.code
    except Exception as exc:
        message = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        print(f"browser {sys.argv[1] if len(sys.argv) > 1 else ''} failed: {message[:400]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
