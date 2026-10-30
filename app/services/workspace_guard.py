"""The workspace's safety rules on consens.io's server (since 2026-10-30).

Max, 2026-10-30, when the workspace opened to every account
(AGENT_AUDIT_ACCESS=all): a rule that recognises harmful behaviour, "nicht
durch den Agenten, durch unseren Server". Three layers (docs/agent-mode.md
"Sicherheitsregeln des Arbeitsplatzes"):

1. Chrome blocks, for the agent and for the user in the live view alike
   (workspace_vm/browser/harden.sh with policy.json): Google's SafeSites
   filter for adult sites, Safe Browsing without "proceed anyway", no file
   dialogs, DevTools, extensions, incognito, debugging port or VM files as a
   page; openbox without menus; an xdg-open that opens nothing. Without them
   no Chrome starts.
2. The trail and the day's counts (here): the hosts the browser showed,
   from the agent's calls (agent_browser.py, note_browser_call) and from the
   live view (relay.py's lines, routers/agent_workspace.py, each with who
   steered: the user after their takeover, else the agent they watched),
   the bytes of the live view and the browser VM's network counters. Each
   host is sorted once by Cloudflare's public resolvers (classify:
   "malware" where the security resolver blocks it, malware and phishing;
   "adult" where only the family resolver does), flagged ones count once
   per site (site_of). One document per account and UTC day in
   TRAIL_COLLECTION, gone after RETENTION_DAYS (cleanup_expired_trails,
   hourly).
3. Consequences (RULES, judge): past a rule's ``close`` the workspace is
   closed for the account until the next UTC day; past its ``lock``, or at
   a second close within REPEAT_DAYS, until an admin unlocks it
   (scripts/workspace_guard.py). Only what the user did locks: what a page
   could talk the agent into (a prompt injection) closes for the day at
   most. Every new state goes to the operator's Telegram, and what still
   runs ends (_shut). The workspace's tools (VMTools._start,
   open_workspace), the live view, the terminal, the takeover, a restore
   and a key for the workbench ask status() first; an open view or terminal
   ends within CHECK_SECONDS. Admins are counted and reported, never
   closed.

What it never does: read a page or an address beyond its host, look at the
words of a prompt, a command or a page (Max's principle: protection in the
infrastructure, no word filters), store an IP address, or tell the agent
more than that the workspace is closed. Chrome blocks by Google's lists and
the counts sort by Cloudflare's: a host one of them flags and the other does
not still counts, since the rule is about what the account tries to open.
An account's guard and trail go with the account (delete_for_account).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import logging
import os
import re
import threading
import time

from app.core.observability import safe_exception

GUARD_COLLECTION = "workspace_guard"
TRAIL_COLLECTION = "workspace_trail"
RETENTION_DAYS = 30
GIB = 1024 ** 3


@dataclass(frozen=True)
class Rule:
    """``metric`` of the day (metrics) at ``close`` closes the workspace
    until the next UTC day, at ``lock`` until an admin unlocks it.
    ``repeat``: a close by this rule within REPEAT_DAYS of an earlier one
    locks. Only what the user did, not what a page could talk the agent into
    (a prompt injection), may lock."""
    name: str
    metric: str
    close: float
    lock: float | None = None
    repeat: bool = True


# First thresholds (2026-10-30), generous on purpose: what an honest run or
# a person in the live view does in a day stays far below them. To be set
# from the first weeks' trails, not guessed lower. Bytes never lock by
# themselves: a canvas app left open in the view is no misuse.
RULES = (
    # Distinct sites (site_of, not every subdomain) of the day that
    # Cloudflare's resolvers flag (adult, malware, phishing) and the user
    # opened while steering the browser in the live view.
    Rule("flagged_sites_by_user", "flagged_user", 5, 15),
    # The same with the agent's: a link that went wrong is one or two; five
    # close for the day, never more, since a page can ask the agent to open them.
    Rule("flagged_sites", "flagged", 5, repeat=False),
    # Hosts first seen in one hour: a person reads a few dozen, a crawler
    # or a proxy thousands.
    Rule("new_hosts_per_hour", "new_hosts_hour", 300),
    # Hosts the agent typed into or uploaded to in one hour: forms on
    # many sites are spam, sign-ups in bulk or credential stuffing; the
    # agent's doing, so never a lock.
    Rule("typed_hosts_per_hour", "typed_hosts_hour", 25, repeat=False),
    # The live view's bytes (both ways, through our server): hours of video
    # streamed through it, not pages read. The terminal does not count.
    Rule("view_bytes", "view_bytes", 6 * GIB),
    # What the browser VM sent and received on its own network (the view's
    # bytes go through the provider's exec API and do not count there,
    # measured on a test Sprite 2026-10-31): uploads or a flood from Fly.io's
    # addresses, and downloads in bulk.
    Rule("sent_bytes", "tx_bytes", 2 * GIB),
    Rule("received_bytes", "rx_bytes", 30 * GIB),
)
# A second close this many days after the last one locks (a rule with ``repeat``).
REPEAT_DAYS = 7
# Hosts kept by name per account and day (about 100 bytes each); flagged
# ones always. Past it a host seen again counts as new: no honest day
# reaches it.
MAX_HOSTS = 2000
HISTORY = 20
# A host is a hostname or an address as urlsplit gives it; anything else is dropped.
HOST = re.compile(r"^[a-z0-9._:-]{1,253}$")
# The workbench's localhost (agent_tunnel.py), never a site.
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
FLAGGED = ("adult", "malware")

# Cloudflare's resolvers (JSON over HTTPS): the security one answers
# 0.0.0.0 for malware and phishing, the family one also for adult sites,
# with an extended DNS error saying so (EDE 16 "Censored", 17 "Filtered";
# checked 2026-10-31). A name whose own record is 0.0.0.0 (anyone can set a
# wildcard so) is no block: without that note the unfiltered resolver decides.
RESOLVERS = (("malware", "https://security.cloudflare-dns.com/dns-query"),
             ("adult", "https://family.cloudflare-dns.com/dns-query"))
UNFILTERED = "https://cloudflare-dns.com/dns-query"
BLOCKED_ANSWER = "0.0.0.0"
BLOCK_NOTE = re.compile(r"EDE\((?:15|16|17)\)")
# Second-level labels under a country's domain that are no site of their own
# (example.co.uk is the site, not co.uk): site_of without a suffix list.
SHARED_SECOND_LEVELS = {"co", "com", "net", "org", "gov", "edu", "ac", "or", "ne", "go", "gob", "nic", "mil"}
CLASSIFY_SECONDS = 3.0
CLASSIFY_CACHE_SECONDS = 24 * 60 * 60
CLASSIFY_RETRY_SECONDS = 5 * 60
CLASSIFY_CACHE_MAX = 50_000
CLASSIFY_WORKERS = 8
CLASSIFY_PER_FLUSH = 64

# Events wait this long, so that one transaction takes a burst; the state
# of an account is read again after STATUS_SECONDS; an open view or
# terminal asks every CHECK_SECONDS and hands its bytes over every
# VIEW_BYTES_SECONDS (routers/agent_workspace.py); sorting hosts takes at
# most CLASSIFY_BUDGET_SECONDS of a count, the rest waits for the next.
FLUSH_DELAY_SECONDS = 3.0
STATUS_SECONDS = 20.0
CHECK_SECONDS = 2.0
VIEW_BYTES_SECONDS = 30.0
CLASSIFY_BUDGET_SECONDS = 8.0
# Pending visits per account beyond this are dropped (a flood of lines);
# unsorted hosts kept for the next count, and kept by name past MAX_HOSTS.
MAX_PENDING_VISITS = 5000
MAX_UNSORTED = 1000
# A guard document without a lock goes this long after its last count.
GUARD_RETENTION_DAYS = 31
# A jump of the VM's counters beyond this between two looks is no traffic.
MAX_NET_STEP = 200 * GIB

# What the agent reads when its workspace is closed (VMTools._start,
# open_workspace), never why.
CLOSED_FOR_AGENT = ("consens.io's safety rules have closed the workspace for this account until {until} UTC. Do not "
                    "call workspace tools again in this message: tell the user the workspace is closed until then, "
                    "and answer without it.")
LOCKED_FOR_AGENT = ("consens.io's safety rules have closed the workspace for this account until consens.io has "
                    "looked at it. Do not call workspace tools again in this message: tell the user, and answer "
                    "without it.")
# What the user reads (routers/agent_workspace.py, workspace-view.js has its own copies for the view).
CLOSED_FOR_USER = ("The workspace is closed on this account until tomorrow: it was used in a way consens.io’s safety "
                   "rules do not allow.")
LOCKED_FOR_USER = "The workspace is closed on this account by consens.io’s safety rules until we have looked at it."


@dataclass(frozen=True)
class Status:
    """An account's guard now: ``state`` open, closed (``until``) or locked."""
    state: str = "open"
    until: datetime | None = None
    rule: str = ""

    @property
    def closed(self):
        return self.state in {"closed", "locked"}


OPEN = Status()


def agent_text(status):
    if status.state == "locked":
        return LOCKED_FOR_AGENT
    until = status.until.strftime("%Y-%m-%d %H:%M") if status.until else "tomorrow"
    return CLOSED_FOR_AGENT.format(until=until)


def user_text(status):
    return LOCKED_FOR_USER if status.state == "locked" else CLOSED_FOR_USER


def _now():
    return datetime.now(timezone.utc)


def day_key(now=None):
    return (now or _now()).strftime("%Y-%m-%d")


def next_day(now=None):
    now = now or _now()
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def expected_policy():
    """The fingerprint of Chrome's policy as harden.sh installs it (relay.py
    and browser.py report what the VM has)."""
    from app.services import agent_workspace
    return hashlib.sha256(agent_workspace.tool_files("browser")["policy.json"]).hexdigest()[:16]


def uid_tag(uid):
    """An account in a log line: a short hash, never the uid itself."""
    return hashlib.sha256(str(uid).encode()).hexdigest()[:10]


# --- Where the guard writes ---------------------------------------------------

_db_override = None


def use_db(db):
    """Tests: the database the guard reads and writes, and with it the guard on."""
    global _db_override
    _db_override = db
    reset()


def _active():
    """The guard counts in production and wherever a test gave it a
    database; test and mock profiles share the real Firestore locally, so
    there it does nothing (like ops_metrics)."""
    if _db_override is not None:
        return True
    return not any(os.getenv(key) == "1" for key in ("UNIT_TEST_MODE", "E2E_TEST_MODE", "MOCK_LLM"))


def _db():
    if _db_override is not None:
        return _db_override
    from app.core.security import db_firestore
    return db_firestore


def guard_ref(db, uid):
    return db.collection(GUARD_COLLECTION).document(uid)


def trail_ref(db, uid, day):
    return db.collection(TRAIL_COLLECTION).document(f"{uid}_{day}")


# --- Sorting hosts --------------------------------------------------------------

_categories: dict[str, tuple[str | None, float]] = {}
_categories_lock = threading.Lock()


def normal_host(host):
    """``host`` lower case without a trailing dot, or None when it is no
    host of a site (empty, odd characters, the workbench's localhost)."""
    if not isinstance(host, str):
        return None
    host = host.strip().lower().rstrip(".")
    if not HOST.match(host) or host in LOCAL_HOSTS:
        return None
    return host


def _is_address(host):
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def site_of(host):
    """The site a host belongs to, as far as its labels tell without a list
    of public suffixes: the last two labels, three under a country's shared
    second level (a.b.example.co.uk -> example.co.uk). A flagged site counts
    once a day however many of its subdomains were opened."""
    if _is_address(host):
        return host
    labels = host.split(".")
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in SHARED_SECOND_LEVELS:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _answer(url, host, client):
    """The resolver's JSON for the host's A record, or None without one."""
    try:
        response = client.get(url, params={"name": host, "type": "A"},
                              headers={"accept": "application/dns-json"}, timeout=CLASSIFY_SECONDS)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logging.info("Workspace guard resolver failed category=%s", safe_exception(exc))
        return None
    return data if isinstance(data, dict) else None


def _nulled(data):
    """Whether every A answer of a found name is 0.0.0.0."""
    if data.get("Status") != 0:
        return False
    answers = [item.get("data") for item in data.get("Answer") or () if isinstance(item, dict) and item.get("type") == 1]
    return bool(answers) and all(answer == BLOCKED_ANSWER for answer in answers)


def _blocked_by(url, host, client):
    """True when the resolver at ``url`` blocks ``host``, False when it does
    not (also no such name, or a name whose own record is 0.0.0.0), None
    without an answer."""
    data = _answer(url, host, client)
    if data is None:
        return None
    if not _nulled(data):
        return False
    if any(BLOCK_NOTE.search(str(note)) for note in data.get("Comment") or ()):
        return True
    unfiltered = _answer(UNFILTERED, host, client)
    if unfiltered is None:
        return None
    return not _nulled(unfiltered)


def classify(host, client=None):
    """"malware", "adult" or "clean" for a host (an address is "clean": no
    resolver sorts it), None when a resolver did not answer."""
    if _is_address(host) or "." not in host:
        return "clean"
    import httpx
    own = client is None
    if own:
        client = httpx.Client()
    try:
        for category, url in RESOLVERS:
            blocked = _blocked_by(url, host, client)
            if blocked is None:
                return None
            if blocked:
                return category
        return "clean"
    finally:
        if own:
            client.close()


def _cached(host):
    """``(True, category)`` from the cache, else ``(False, None)``."""
    with _categories_lock:
        known = _categories.get(host)
    if known is not None and known[1] > time.monotonic():
        return True, known[0]
    return False, None


def category_of(host, client=None):
    """classify with a cache: a day for an answer, a few minutes for none."""
    found, category = _cached(host)
    if found:
        return category
    category = classify(host, client)
    with _categories_lock:
        if len(_categories) >= CLASSIFY_CACHE_MAX:
            _categories.clear()
        _categories[host] = (category, time.monotonic() + (CLASSIFY_CACHE_SECONDS if category
                                                           else CLASSIFY_RETRY_SECONDS))
    return category


def sort_hosts(hosts, budget=None):
    """``(categories, skipped)``: each host's category, from the cache or
    asked of the resolvers CLASSIFY_WORKERS at a time, at most
    CLASSIFY_PER_FLUSH per count and CLASSIFY_BUDGET_SECONDS long. A host
    left over (``skipped``) or without an answer is None for now: the count
    goes on without it, and the next count asks again (_unsorted). A crawl
    of a thousand hosts thus never holds up the count, and hosts that come
    first cannot keep later ones from being sorted."""
    from concurrent.futures import ThreadPoolExecutor, wait
    categories, asking, skipped = {}, [], []
    for host in hosts:
        found, category = _cached(host)
        if found:
            categories[host] = category
        elif len(asking) < CLASSIFY_PER_FLUSH:
            asking.append(host)
        else:
            categories[host] = None
            skipped.append(host)
    if asking:
        import httpx
        client = httpx.Client()
        pool = ThreadPoolExecutor(max_workers=CLASSIFY_WORKERS)
        futures = {pool.submit(category_of, host, client): host for host in asking}
        done, late = wait(futures, timeout=CLASSIFY_BUDGET_SECONDS if budget is None else budget)
        for future, host in futures.items():
            categories[host] = future.result() if future in done and future.exception() is None else None
            if future in late:
                skipped.append(host)
        # The late ones finish into the cache; the client closes after them.
        pool.shutdown(wait=False, cancel_futures=True)
        threading.Thread(target=lambda: (pool.shutdown(wait=True), client.close()), daemon=True).start()
    return categories, skipped


# --- Events -----------------------------------------------------------------------

@dataclass
class _Pending:
    visits: list = field(default_factory=list)
    view_bytes: int = 0
    net: list = field(default_factory=list)
    policies: set = field(default_factory=set)


_pending: dict[str, _Pending] = {}
# Hosts of an account seen but not sorted yet (a resolver without an answer,
# past a count's share): each later count asks again.
_unsorted: dict[str, set] = {}
_lock = threading.Lock()
_wake = threading.Event()
_thread = None
# Who steers what the live view shows: "user" while they hold the browser,
# "view" while they watch the agent, "agent" for the agent's own calls.
SOURCES = ("agent", "view", "user")


def _pend(uid):
    """The account's pending events (under _lock)."""
    pending = _pending.get(uid)
    if pending is None:
        pending = _pending[uid] = _Pending()
    return pending


def _started():
    global _thread
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_run, name="workspace-guard", daemon=True)
        _thread.start()
    _wake.set()


def note_visit(uid, host, by, *, typed=False, at=None):
    """The browser showed (or was asked for) a page of ``host``; ``by`` one
    of SOURCES; ``typed``: the agent typed into it or uploaded to it. Never
    blocks: the guard thread sorts and counts."""
    host = normal_host(host)
    if not uid or host is None or not _active():
        return
    with _lock:
        visits = _pend(uid).visits
        if len(visits) < MAX_PENDING_VISITS:
            visits.append((host, by if by in SOURCES else "view", bool(typed), at or time.time()))
        _started()


def note_view_bytes(uid, count):
    if not uid or not count or not _active():
        return
    with _lock:
        _pend(uid).view_bytes += int(count)
        _started()


def note_net(uid, counters):
    """The browser VM's network counters as relay.py or browser.py read them."""
    if not uid or not isinstance(counters, dict) or not _active():
        return
    rx, tx, boot = counters.get("rx"), counters.get("tx"), counters.get("boot")
    if type(rx) is not int or type(tx) is not int or rx < 0 or tx < 0 or not isinstance(boot, str) or not boot:
        return
    with _lock:
        _pend(uid).net.append({"rx": rx, "tx": tx, "boot": boot[:36]})
        _started()


def note_policy(uid, fingerprint):
    """The fingerprint of the Chrome policy on the account's browser VM, after
    Chrome started under it (relay.py) or answered a call (browser.py)."""
    if not uid or not isinstance(fingerprint, str) or not _active():
        return
    with _lock:
        _pend(uid).policies.add(fingerprint[:16])
        _started()


def note_browser_call(uid, *, action, asked_url="", page_url="", answer=None):
    """One call of the agent's browser tool (agent_browser.BrowserTools.call):
    the host it asked for, the host of the page in front after it, the
    VM's counters and policy from the helper's answer."""
    from urllib.parse import urlsplit

    def host_of(url):
        try:
            parts = urlsplit(url or "")
        except ValueError:
            return None
        return parts.hostname if parts.scheme in {"http", "https"} else None
    typed = action in {"type", "upload"}
    asked, shown = host_of(asked_url), host_of(page_url)
    if asked:
        note_visit(uid, asked, "agent", typed=typed and asked == shown)
    if shown:
        note_visit(uid, shown, "agent", typed=typed)
    if isinstance(answer, dict):
        note_net(uid, answer.get("net"))
        if answer.get("status") == "ok" and action not in {"rest", "warm"}:
            note_policy(uid, answer.get("policy"))


def _run():
    while True:
        _wake.wait()
        time.sleep(FLUSH_DELAY_SECONDS)
        _wake.clear()
        try:
            if flush():
                # Hosts left over for the next count: soon, not only with the next event.
                _wake.set()
        except Exception as exc:
            logging.warning("Workspace guard flush failed category=%s", safe_exception(exc))


def flush(uid=None):
    """Counts what is pending (of ``uid``, else of every account): one
    transaction per account. Tests call it directly. Returns whether hosts
    were left over for the next count (sort_hosts)."""
    with _lock:
        uids = [uid] if uid is not None else list(dict.fromkeys([*_pending, *_unsorted]))
        batches = [(key, _pending.pop(key, None) or _Pending()) for key in uids
                   if key in _pending or key in _unsorted]
    left = False
    for key, pending in batches:
        try:
            left = _count(key, pending) or left
        except Exception as exc:
            logging.warning("Workspace guard count failed category=%s account=%s", safe_exception(exc),
                            uid_tag(key))
    return left


# --- Counting -----------------------------------------------------------------------

def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def merge_visits(trail, visits, categories):
    """``trail`` (the day's document) with ``visits`` counted. Each host's
    category comes from ``categories`` (None: not known yet), also for a
    host of the day that was unsorted until now. The flagged counts are
    sites (site_of), each once a day: ``flagged`` by anyone, ``flagged_user``
    opened while the user steered the browser, ``adult`` and ``malware``."""
    hosts = [dict(entry) for entry in trail.get("hosts") or () if isinstance(entry, dict)]
    known = {entry.get("host"): entry for entry in hosts}
    counts = {key: _num(value) for key, value in (trail.get("counts") or {}).items()}
    hours = {hour: {key: _num(value) for key, value in (values or {}).items()}
             for hour, values in (trail.get("hours") or {}).items()}
    dropped = _num(trail.get("hosts_dropped"))

    def add(name, hour=None, amount=1):
        if hour is None:
            counts[name] = counts.get(name, 0) + amount
        else:
            hours.setdefault(hour, {})[name] = hours.get(hour, {}).get(name, 0) + amount

    for host, by, typed, at in visits:
        moment = time.gmtime(at)
        hour, clock = time.strftime("%H", moment), time.strftime("%H:%M:%S", moment)
        category = categories.get(host)
        entry = known.get(host)
        if entry is None:
            add("hosts")
            add("new_hosts", hour)
            # Flagged hosts are always kept by name, unsorted ones a while longer than clean ones.
            full = len(hosts) >= (MAX_HOSTS if category == "clean" else MAX_HOSTS + MAX_UNSORTED)
            if full and category not in FLAGGED:
                dropped += 1
                if typed:
                    add("typed_hosts")
                    add("typed_hosts", hour)
                continue
            entry = {"host": host, "first": clock, "last": clock, "n": 0, "by": [], "category": category or ""}
            hosts.append(entry)
            known[host] = entry
        entry["n"] = _num(entry.get("n")) + 1
        entry["last"] = clock
        if by not in (entry.get("by") or []):
            entry["by"] = [*(entry.get("by") or []), by]
        if typed and entry.get("typed_hour") != hour:
            # Hosts typed into: today once each, in an hour once each per hour.
            if not entry.get("typed_hour"):
                add("typed_hosts")
            entry["typed_hour"] = hour
            add("typed_hosts", hour)
    for entry in hosts:
        # Sorted now, after a resolver did not answer before.
        if not entry.get("category") and categories.get(entry.get("host")):
            entry["category"] = categories[entry["host"]]
    flagged = {}
    for entry in hosts:
        if entry.get("category") in FLAGGED:
            site = flagged.setdefault(site_of(entry["host"]), {"categories": set(), "by": set()})
            site["categories"].add(entry["category"])
            site["by"].update(entry.get("by") or ())
    counts.update(flagged=len(flagged), flagged_user=sum("user" in site["by"] for site in flagged.values()),
                  **{category: sum(category in site["categories"] for site in flagged.values())
                     for category in FLAGGED})
    return {**trail, "hosts": hosts, "counts": counts, "hours": hours, "hosts_dropped": dropped}


def merge_net(last, observations):
    """``(last, rx, tx)``: the counters seen last after ``observations`` and
    the bytes they add. Only a later reading of the same boot adds; one of a
    new boot starts again (what the VM did before our first look after a
    boot is its own start); an older reading that arrived late is skipped."""
    last = dict(last) if isinstance(last, dict) else {}
    rx = tx = 0
    for seen in observations:
        if seen["boot"] != last.get("boot"):
            last = dict(seen)
            continue
        step_rx, step_tx = seen["rx"] - _num(last.get("rx")), seen["tx"] - _num(last.get("tx"))
        if step_rx < 0 or step_tx < 0:
            continue
        if step_rx <= MAX_NET_STEP and step_tx <= MAX_NET_STEP:
            rx, tx = rx + step_rx, tx + step_tx
        last = dict(seen)
    return last, rx, tx


def metrics(trail, baseline=None):
    """The rules' measures of a day, less what an unlock forgave that day (``baseline``)."""
    counts, hours = trail.get("counts") or {}, trail.get("hours") or {}
    base = baseline if isinstance(baseline, dict) and baseline.get("day") == trail.get("day") else {}
    base_counts, base_hours = base.get("counts") or {}, base.get("hours") or {}
    values = {key: max(0, _num(counts.get(key)) - _num(base_counts.get(key)))
              for key in ("flagged", "flagged_user", "view_bytes", "tx_bytes", "rx_bytes")}
    for metric, key in (("new_hosts_hour", "new_hosts"), ("typed_hosts_hour", "typed_hosts")):
        values[metric] = max([max(0, _num((hours.get(hour) or {}).get(key))
                                  - _num((base_hours.get(hour) or {}).get(key))) for hour in hours] or [0])
    return values


def judge(values):
    """``(state, rule)`` the day's measures call for: "locked" past any
    rule's lock, else "closed" past a close, else (None, None)."""
    for rule in RULES:
        if rule.lock is not None and values.get(rule.metric, 0) >= rule.lock:
            return "locked", rule
    for rule in RULES:
        if values.get(rule.metric, 0) >= rule.close:
            return "closed", rule
    return None, None


def current(guard, now=None):
    """The guard document as a Status (a close past its day is open)."""
    now = now or _now()
    state = guard.get("state")
    until = guard.get("until")
    if state == "locked":
        return Status("locked", None, str(guard.get("rule") or ""))
    if state == "closed" and isinstance(until, datetime) and until > now:
        return Status("closed", until, str(guard.get("rule") or ""))
    return OPEN


def decide(guard, values, day, now):
    """The new guard fields for a day's ``values``, or None when nothing
    changes: closed until the next UTC day, or locked; a close by a rule
    with ``repeat`` on a day after another close within REPEAT_DAYS locks."""
    judged, rule = judge(values)
    if judged is None:
        return None
    before = current(guard, now)
    if before.state == "locked" or (before.state == "closed" and judged == "closed"):
        return None
    state, reason = judged, rule.name
    if judged == "closed" and rule.repeat:
        recent = [past for past in guard.get("closed_days") or () if isinstance(past, str) and past != day
                  and (datetime.fromisoformat(day) - datetime.fromisoformat(past)).days <= REPEAT_DAYS]
        if recent:
            state, reason = "locked", f"repeat:{rule.name}"
    return {"state": state, "rule": reason, "at": now, "values": values,
            "until": next_day(now) if state == "closed" else None}


def _is_admin(uid):
    try:
        from app.core.security import is_user_admin
        return bool(is_user_admin(uid))
    except Exception as exc:
        logging.info("Workspace guard admin check failed category=%s", safe_exception(exc))
        return False


def _count(uid, pending):
    """One transaction for an account's pending events: the day's trail,
    the VM's counters, and a new state where a rule now calls for one.
    Returns whether hosts were left over for the next count."""
    from app.services import persistence_guard
    with _lock:
        waiting = set(_unsorted.pop(uid, ()))
    # The hosts in the order they came, then those still unsorted from before.
    order = list(dict.fromkeys([visit[0] for visit in pending.visits] + sorted(waiting)))
    categories, skipped = sort_hosts(order) if order else ({}, [])
    unsorted = {host for host, category in categories.items() if category is None}
    if unsorted:
        with _lock:
            _unsorted.setdefault(uid, set()).update(sorted(unsorted)[:MAX_UNSORTED])
    sorted_now = any(categories.get(host) for host in waiting)
    if not (pending.visits or pending.view_bytes or pending.net or pending.policies or sorted_now):
        return bool(skipped)
    db = _db()
    now = _now()
    day = day_key(now)
    # Whether the account is an admin's: read once, and only when a rule fires.
    admin = {}
    outcome = {}

    def operation(tx):
        persistence_guard.ensure_account_write_allowed(uid=uid, db=db, transaction=tx)
        guard_doc, trail_doc = guard_ref(db, uid), trail_ref(db, uid, day)
        guard = (tx.get(guard_doc) if tx is not None else guard_doc.get()).to_dict() or {}
        trail = (tx.get(trail_doc) if tx is not None else trail_doc.get()).to_dict() or {}
        trail = merge_visits({**trail, "uid": uid, "day": day}, pending.visits, categories)
        last, rx, sent = merge_net(guard.get("net"), pending.net)
        counts = trail["counts"]
        for key, amount in (("view_bytes", pending.view_bytes), ("rx_bytes", rx), ("tx_bytes", sent)):
            if amount:
                counts[key] = counts.get(key, 0) + amount
        values = metrics(trail, guard.get("baseline"))
        change = decide(guard, values, day, now)
        if change is not None and "value" not in admin:
            admin["value"] = _is_admin(uid)
        guard_fields = {"uid": uid, "updated_at": now, "net": last}
        noted = guard.get("noted") if isinstance(guard.get("noted"), dict) else {}
        keys = list(noted.get("keys") or []) if noted.get("day") == day else []
        alerts = []
        if change is not None and admin.get("value"):
            # Counted and reported once a day per rule, never closed.
            if f"admin:{change['rule']}" not in keys:
                keys.append(f"admin:{change['rule']}")
                alerts.append(("admin", change))
            change = None
        if change is not None:
            guard_fields.update({key: change[key] for key in ("state", "rule", "at", "values", "until")})
            if change["state"] == "closed":
                guard_fields["closed_days"] = [*[past for past in guard.get("closed_days") or ()
                                                 if isinstance(past, str)][-(REPEAT_DAYS - 1):], day]
            guard_fields["history"] = [*(guard.get("history") or [])[-(HISTORY - 1):],
                                       {"at": now, "state": change["state"], "rule": change["rule"]}]
        wrong = sorted(fingerprint for fingerprint in pending.policies if fingerprint != expected_policy())
        if wrong and "policy" not in keys:
            keys.append("policy")
            alerts.append(("policy", wrong[0]))
        if keys:
            guard_fields["noted"] = {"day": day, "keys": keys}
        # The guard goes GUARD_RETENTION_DAYS after its last count
        # (cleanup_expired_trails); a lock stays until it is lifted.
        locked = (change or {}).get("state") == "locked" or current(guard, now).state == "locked"
        guard_fields["expires_at"] = None if locked else now + timedelta(days=GUARD_RETENTION_DAYS)
        trail_fields = {**trail, "updated_at": now,
                        "expires_at": datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
                        + timedelta(days=RETENTION_DAYS + 1)}
        if tx is not None:
            tx.set(guard_doc, guard_fields, merge=True)
            tx.set(trail_doc, trail_fields)
        else:
            guard_doc.set(guard_fields, merge=True)
            trail_doc.set(trail_fields)
        outcome.update(change=change, alerts=alerts, trail=trail)

    persistence_guard._run_transaction(db, operation)
    change = outcome.get("change")
    if change:
        _remember(uid, current(change, now))
        logging.warning("Workspace guard %s account=%s rule=%s", change["state"], uid_tag(uid), change["rule"])
        _alert(_alert_text(uid, change, outcome["trail"], now))
        _shut(uid)
    for kind, detail in outcome.get("alerts") or ():
        if kind == "admin":
            logging.info("Workspace guard would have %s an admin's workspace rule=%s", detail["state"],
                         detail["rule"])
            _alert(_alert_text(uid, detail, outcome["trail"], now, admin=True))
        elif kind == "policy":
            logging.warning("Workspace guard policy differs account=%s", uid_tag(uid))
            _alert(f"⚠️ consens.io workspace: Chrome's policy differs on a browser VM\n"
                   f"Expected {expected_policy()}, the VM has {detail or 'none'} (the log line names the account's "
                   f"tag).\nEnvironment: {_environment()}")
    return bool(skipped)


def _shut(uid):
    """What still runs when the workspace closes: the localhost tunnel ends,
    and the browser VM's wake hold shortens to two minutes (browser.py
    ``rest``), so Chrome's open tabs sleep with it. An open view or terminal
    ends by itself (routers/agent_workspace.py), a running message's next
    workspace call is refused (VMTools._start). Background processes on the
    workbench run out (at most an hour; its network reaches only package
    registries). On a thread of its own; failures are only logged."""
    def run():
        try:
            from app.services import agent_tunnel
            agent_tunnel.close(uid)
        except Exception as exc:
            logging.info("Workspace guard tunnel not closed category=%s", safe_exception(exc))
        try:
            _rest_browser(uid)
        except Exception as exc:
            logging.info("Workspace guard browser not rested category=%s", safe_exception(exc))
    threading.Thread(target=run, name="workspace-guard-shut", daemon=True).start()


def _rest_browser(uid):
    import json
    from app.services import agent_vm, agent_workspace
    from app.services.llm.provider_runtime import ProviderCancellation
    backend = agent_vm.backend()
    if backend is None:
        return
    try:
        name = agent_vm.browser_name(uid)
        if not backend.exists(name):
            return
        backend.run(name, agent_vm.wrapped_command(f"exec python3 {agent_workspace.BROWSER_HELPER}", 20, False),
                    cwd=agent_vm.SERVER_HOME, timeout=20, on_output=lambda stream, chunk: None,
                    cancellation=ProviderCancellation(), input=json.dumps({"action": "rest"}).encode())
    finally:
        backend.close()


# --- State ------------------------------------------------------------------------------

_status: dict[str, tuple[Status, float]] = {}
_status_lock = threading.Lock()


def _remember(uid, status):
    with _status_lock:
        _status[uid] = (status, time.monotonic())


def reset():
    """Tests: forget states, pending events and sorted hosts."""
    with _status_lock:
        _status.clear()
    with _lock:
        _pending.clear()
        _unsorted.clear()
    with _categories_lock:
        _categories.clear()


def status(uid):
    """The account's guard now (OPEN where the guard is off or unreadable:
    a failed read never closes the workspace; the next read STATUS_SECONDS
    later tries again)."""
    if not uid or not _active():
        return OPEN
    now = time.monotonic()
    with _status_lock:
        known = _status.get(uid)
    if known is not None and now - known[1] < STATUS_SECONDS:
        found = known[0]
    else:
        try:
            found = current(guard_ref(_db(), uid).get().to_dict() or {})
        except Exception as exc:
            logging.warning("Workspace guard state unreadable category=%s", safe_exception(exc))
            found = known[0] if known is not None else OPEN
        _remember(uid, found)
    if found.state == "closed" and found.until is not None and found.until <= _now():
        return OPEN
    return found


def unlock(uid, *, db=None, now=None):
    """An admin opens the workspace again (scripts/workspace_guard.py): what
    the account did today until now is forgiven (``baseline``), so the same
    counts do not close it again at once, and earlier closes no longer turn
    the next one into a lock. Returns the state it had."""
    db = db or _db()
    now = now or _now()
    day = day_key(now)
    from app.services import persistence_guard
    seen = {}

    def operation(tx):
        guard_doc, trail_doc = guard_ref(db, uid), trail_ref(db, uid, day)
        guard = (tx.get(guard_doc) if tx is not None else guard_doc.get()).to_dict() or {}
        trail = (tx.get(trail_doc) if tx is not None else trail_doc.get()).to_dict() or {}
        seen["before"] = current(guard, now)
        fields = {"uid": uid, "state": "open", "until": None, "rule": "", "closed_days": [], "updated_at": now,
                  "expires_at": now + timedelta(days=GUARD_RETENTION_DAYS),
                  "baseline": {"day": day, "counts": trail.get("counts") or {}, "hours": trail.get("hours") or {}},
                  "history": [*(guard.get("history") or [])[-(HISTORY - 1):],
                              {"at": now, "state": "open", "rule": "unlocked"}]}
        if tx is not None:
            tx.set(guard_doc, fields, merge=True)
        else:
            guard_doc.set(fields, merge=True)
    persistence_guard._run_transaction(db, operation)
    _remember(uid, OPEN)
    return seen.get("before", OPEN)


# --- Alerts -----------------------------------------------------------------------------

def _environment():
    from app.services.telegram_notifier import alert_environment
    return alert_environment()


def _size(value):
    value = _num(value)
    return f"{value / GIB:.1f} GB" if value >= GIB / 10 else f"{value / (1024 ** 2):.0f} MB"


def _alert_text(uid, change, trail, now, admin=False):
    counts = trail.get("counts") or {}
    rule = change["rule"]
    name = rule.split(":", 1)[-1]
    limit = next((item for item in RULES if item.name == name), None)
    measured = change["values"].get(limit.metric) if limit else None
    shown = _size(measured) if limit and limit.metric.endswith("bytes") else measured
    head = ("⚠️ consens.io workspace: a safety rule fired for an admin (counted only, not closed)" if admin else
            "🚫 consens.io workspace locked until an admin unlocks it" if change["state"] == "locked" else
            "🛑 consens.io workspace closed for today")
    # No account in the alert (privacy.html: the operator's alerts carry no
    # account identifiers): scripts/workspace_guard.py list names it.
    lines = [head, f"Rule: {rule} ({shown} on {day_key(now)})",
             f"Today: {_num(counts.get('hosts'))} hosts, {_num(counts.get('flagged'))} flagged "
             f"({_num(counts.get('adult'))} adult, {_num(counts.get('malware'))} malware/phishing), "
             f"view {_size(counts.get('view_bytes'))}, VM sent {_size(counts.get('tx_bytes'))}, "
             f"received {_size(counts.get('rx_bytes'))}"]
    if change["state"] == "closed" and not admin:
        lines.append("Until: " + change["until"].strftime("%Y-%m-%d %H:%M UTC"))
    if not admin:
        lines.append("Which account, look and unlock: venv/Scripts/python.exe scripts/workspace_guard.py list")
    lines.append(f"Environment: {_environment()}")
    return "\n".join(lines)


def _send(text):
    from app.services.telegram_notifier import send_admin_note
    try:
        send_admin_note(text)
    except Exception as exc:
        logging.warning("Workspace guard alert failed category=%s", safe_exception(exc))


def _alert(text):
    threading.Thread(target=_send, args=(text,), name="workspace-guard-alert", daemon=True).start()


# --- Retention and deletion ---------------------------------------------------------------

CLEANUP_PAGE_SIZE = 100
CLEANUP_TIME_BUDGET_SECONDS = 120


def cleanup_expired_trails(db=None, *, page_size=CLEANUP_PAGE_SIZE, time_budget=CLEANUP_TIME_BUDGET_SECONDS,
                           now=None):
    """Hourly (retention_maintenance.py): every trail past ``expires_at``,
    and every guard past its own (GUARD_RETENTION_DAYS after its last
    count; a lock has none and stays). A field of a top-level collection:
    Firestore's automatic index serves the query, nothing to deploy."""
    from google.cloud.firestore_v1.base_query import FieldFilter
    if db is None and not _active():
        return 0
    db = db or _db()
    deadline = time.monotonic() + time_budget
    threshold = now or _now()
    count = 0
    for collection in (TRAIL_COLLECTION, GUARD_COLLECTION):
        while time.monotonic() < deadline:
            batch = list(db.collection(collection).where(filter=FieldFilter("expires_at", "<=", threshold))
                         .limit(page_size).stream())
            for snapshot in batch:
                if collection == GUARD_COLLECTION and (snapshot.to_dict() or {}).get("state") == "locked":
                    continue
                snapshot.reference.delete()
                count += 1
            if len(batch) < page_size:
                break
    return count


def delete_for_account(db, uid):
    """With the account (agent_workspace.delete_for_account): its guard and every trail."""
    from google.cloud.firestore_v1.base_query import FieldFilter
    guard_ref(db, uid).delete()
    for snapshot in db.collection(TRAIL_COLLECTION).where(filter=FieldFilter("uid", "==", uid)).stream():
        snapshot.reference.delete()
    with _status_lock:
        _status.pop(uid, None)
    with _lock:
        _pending.pop(uid, None)
        _unsorted.pop(uid, None)
