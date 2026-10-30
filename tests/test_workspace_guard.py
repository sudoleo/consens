"""The workspace's safety rules on the server (workspace_guard.py, since
2026-10-30): the trail of hosts and bytes, the rules that close or lock the
workspace, and every way into the workspace that asks them first (the
agent's tools, open_workspace, the live view, the terminal, the takeover).
The database is the suites' fake, the resolvers a MockTransport; nothing
calls Cloudflare, Telegram or Sprites."""
from datetime import datetime, timedelta, timezone
import json
import time

import httpx
import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.routers import agent_workspace as workspace_router
from app.services import agent_vm, agent_workspace, workspace_guard
from app.services.workspace_guard import GIB, Rule
from test_agent_runs import AUTH, UID, pending, store  # noqa: F401  (fixtures)
from test_agent_vm import ANSWER, Agent, _admin_allowance, fake_vm, results, vm_loop  # noqa: F401
from test_agent_workspace_view import open_view, terminal_api, view_api  # noqa: F401

DAY = datetime(2026, 10, 30, 14, 0, tzinfo=timezone.utc)
AT = DAY.timestamp()
CATEGORIES = {"adult-1.example": "adult", "adult-2.example": "adult", "adult-3.example": "adult",
              "adult-4.example": "adult", "bad.example": "malware", "www.pornhub.com": "adult"}
CLASSIFY = workspace_guard.classify


@pytest.fixture(autouse=True)
def _quiet_guard(monkeypatch):
    """No thread, no resolver and no Telegram in any test here: counting
    runs on flush(), hosts are sorted by CATEGORIES."""
    monkeypatch.setattr(workspace_guard, "_started", lambda: None)
    monkeypatch.setattr(workspace_guard, "classify", lambda host, client=None: CATEGORIES.get(host, "clean"))
    monkeypatch.setattr(workspace_guard, "_alert", lambda text: None)
    monkeypatch.setattr(workspace_guard, "_shut", lambda uid: None)
    workspace_guard.reset()
    yield
    workspace_guard.use_db(None)


@pytest.fixture
def guard(store, monkeypatch):
    """The guard on the suite's database, hosts sorted by CATEGORIES, alerts
    kept here, the clock at DAY, nobody an admin."""
    workspace_guard.use_db(store.db)
    alerts = []
    clock = {"now": DAY}
    monkeypatch.setattr(workspace_guard, "classify", lambda host, client=None: CATEGORIES.get(host, "clean"))
    monkeypatch.setattr(workspace_guard, "_alert", alerts.append)
    monkeypatch.setattr(workspace_guard, "_now", lambda: clock["now"])
    monkeypatch.setattr(workspace_guard, "_is_admin", lambda uid: False)
    monkeypatch.setattr(workspace_guard, "_started", lambda: None)
    shut = []
    monkeypatch.setattr(workspace_guard, "_shut", shut.append)
    yield store, alerts, clock, shut
    workspace_guard.use_db(None)


def visit(host, by="agent", typed=False, at=AT):
    workspace_guard.note_visit(UID, host, by, typed=typed, at=at)


def trail(store, day="2026-10-30"):
    return workspace_guard.trail_ref(store.db, UID, day).get().to_dict() or {}


def guard_doc(store):
    return workspace_guard.guard_ref(store.db, UID).get().to_dict() or {}


# --- The trail -----------------------------------------------------------------------

def test_the_trail_counts_hosts_by_host_hour_source_and_typing_never_more():
    visits = [("a.example", "agent", False, AT), ("a.example", "view", False, AT + 60),
              ("b.example", "view", True, AT + 120), ("b.example", "agent", True, AT + 180),
              ("b.example", "agent", True, AT + 3600), ("adult-1.example", "view", False, AT + 3600)]
    merged = workspace_guard.merge_visits({"day": "2026-10-30"}, visits,
                                          {"a.example": "clean", "b.example": "clean", "adult-1.example": "adult"})
    assert merged["counts"] == {"hosts": 3, "typed_hosts": 1, "flagged": 1, "flagged_user": 0, "adult": 1,
                                "malware": 0}
    assert merged["hours"] == {"14": {"new_hosts": 2, "typed_hosts": 1}, "15": {"new_hosts": 1, "typed_hosts": 1}}
    first = merged["hosts"][0]
    assert first == {"host": "a.example", "first": "14:00:00", "last": "14:01:00", "n": 2, "by": ["agent", "view"],
                     "category": "clean"}
    # Only hosts and times: no path, no page, no words.
    assert set(merged["hosts"][1]) == {"host", "first", "last", "n", "by", "category", "typed_hour"}


def test_flagged_hosts_count_once_per_site_and_by_who_steered():
    """The review of 2026-10-31: a page could ask the agent to open
    a1 to a15.evil.example and lock its user out. Subdomains are one site,
    and only what the user opened while steering counts towards a lock."""
    visits = [(f"a{n}.evil.example", "agent", False, AT) for n in range(15)] + [
        ("www.adult.co.uk", "user", False, AT), ("m.adult.co.uk", "view", False, AT),
        ("bad.example", "view", False, AT), ("bad.example", "user", False, AT + 1)]
    categories = {**{f"a{n}.evil.example": "malware" for n in range(15)}, "www.adult.co.uk": "adult",
                  "m.adult.co.uk": "adult", "bad.example": "malware"}
    counts = workspace_guard.merge_visits({}, visits, categories)["counts"]
    assert counts["flagged"] == 3 and counts["flagged_user"] == 2 and counts["malware"] == 2 and counts["adult"] == 1
    assert workspace_guard.site_of("a.b.example.co.uk") == "example.co.uk"
    assert workspace_guard.site_of("x.y.example.com") == "example.com"
    assert workspace_guard.site_of("1.2.3.4") == "1.2.3.4"


def test_a_host_sorted_later_counts_once_when_its_resolver_answers():
    merged = workspace_guard.merge_visits({}, [("bad.example", "view", False, AT)], {"bad.example": None})
    assert merged["counts"]["flagged"] == 0 and merged["hosts"][0]["category"] == ""
    # Sorted at a later count, also without a new visit.
    again = workspace_guard.merge_visits(merged, [], {"bad.example": "malware"})
    assert again["counts"]["flagged"] == 1 and again["counts"]["malware"] == 1
    third = workspace_guard.merge_visits(again, [("bad.example", "view", False, AT + 9)], {"bad.example": "malware"})
    assert third["counts"]["flagged"] == 1 and third["hosts"][0]["n"] == 2


def test_past_its_list_the_trail_keeps_counting_and_flagged_hosts_by_name(monkeypatch):
    monkeypatch.setattr(workspace_guard, "MAX_HOSTS", 2)
    visits = [(f"{n}.example", "agent", False, AT) for n in range(4)] + [("adult-1.example", "view", False, AT)]
    merged = workspace_guard.merge_visits({}, visits, {**{f"{n}.example": "clean" for n in range(4)},
                                                       "adult-1.example": "adult"})
    assert [entry["host"] for entry in merged["hosts"]] == ["0.example", "1.example", "adult-1.example"]
    assert merged["counts"]["hosts"] == 5 and merged["hosts_dropped"] == 2 and merged["counts"]["flagged"] == 1


def test_network_counters_add_only_what_one_boot_counted_forward():
    seen = [{"rx": 100, "tx": 10, "boot": "a"}, {"rx": 300, "tx": 30, "boot": "a"},
            # Late, from before: skipped, never counted twice.
            {"rx": 200, "tx": 20, "boot": "a"}, {"rx": 400, "tx": 40, "boot": "a"},
            # A new boot starts again: what ran before our first look is the VM's own start.
            {"rx": 5000, "tx": 50, "boot": "b"}, {"rx": 5100, "tx": 60, "boot": "b"}]
    last, rx, tx = workspace_guard.merge_net({}, seen)
    assert (rx, tx) == (300 + 100, 30 + 10) and last == {"rx": 5100, "tx": 60, "boot": "b"}
    # A jump no network makes is no traffic.
    _, rx, _ = workspace_guard.merge_net(last, [{"rx": 5100 + 300 * GIB, "tx": 60, "boot": "b"}])
    assert rx == 0


def test_only_hosts_of_sites_count():
    assert workspace_guard.normal_host("Example.COM.") == "example.com"
    for host in ("localhost", "127.0.0.1", "::1", "", "a b", "x" * 300, None, "ex/ample"):
        assert workspace_guard.normal_host(host) is None


# --- Sorting by Cloudflare's resolvers --------------------------------------------------

def resolvers(blocked_by, fail=False, nulled=()):
    """Cloudflare's resolvers as measured 2026-10-31: a block answers 0.0.0.0
    with EDE 16/17; ``nulled`` names whose own record is 0.0.0.0 (no note,
    the unfiltered resolver says the same)."""
    def handler(request):
        if fail:
            return httpx.Response(503)
        name = request.url.params["name"]
        assert request.url.params["type"] == "A" and request.headers["accept"] == "application/dns-json"
        if name == "missing.example":
            return httpx.Response(200, json={"Status": 3})
        blocked = any(request.url.host.startswith(kind) for kind in blocked_by.get(name, ()))
        answer = "0.0.0.0" if blocked or name in nulled else "93.184.215.14"
        body = {"Status": 0, "Answer": [{"type": 5, "data": "cname.example."}, {"type": 1, "data": answer}]}
        if blocked:
            body["Comment"] = ["EDE(17): Filtered" if request.url.host.startswith("family") else "EDE(16): Censored"]
        return httpx.Response(200, json=body)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_hosts_are_sorted_by_cloudflares_security_and_family_resolvers():
    client = resolvers({"phish.example": ("security", "family"), "adult.example": ("family",)},
                       nulled=("wild.evil.example",))
    assert CLASSIFY("phish.example", client) == "malware"
    assert CLASSIFY("adult.example", client) == "adult"
    assert CLASSIFY("news.example", client) == "clean"
    assert CLASSIFY("missing.example", client) == "clean"
    # A name whose own record is 0.0.0.0 (a wildcard anyone can set) is no block.
    assert CLASSIFY("wild.evil.example", client) == "clean"
    # An address is sorted by no resolver; a resolver without an answer leaves the host unsorted.
    assert CLASSIFY("93.184.215.14", client) == "clean"
    assert CLASSIFY("news.example", resolvers({}, fail=True)) is None


def test_a_block_without_its_note_is_checked_against_the_unfiltered_resolver():
    def handler(request):
        if request.url.host == "cloudflare-dns.com":
            return httpx.Response(200, json={"Status": 0, "Answer": [{"type": 1, "data": "93.184.215.14"}]})
        return httpx.Response(200, json={"Status": 0, "Answer": [{"type": 1, "data": "0.0.0.0"}]})
    assert CLASSIFY("quiet.example", httpx.Client(transport=httpx.MockTransport(handler))) == "malware"


def test_a_crawl_is_sorted_a_few_hosts_at_a_time_and_each_host_once_a_day(monkeypatch):
    asked = []
    monkeypatch.setattr(workspace_guard, "CLASSIFY_PER_FLUSH", 3)
    monkeypatch.setattr(workspace_guard, "classify",
                        lambda host, client=None: asked.append(host) or (None if host == "0.example" else "clean"))
    hosts = [f"{n}.example" for n in range(5)]
    first, skipped = workspace_guard.sort_hosts(hosts)
    assert sorted(asked) == hosts[:3] and first == {**{host: "clean" for host in hosts[1:3]}, "0.example": None,
                                                    "3.example": None, "4.example": None}
    assert skipped == ["3.example", "4.example"]
    asked.clear()
    second, skipped = workspace_guard.sort_hosts(hosts)
    # Sorted ones come from the cache; one without an answer waits a few minutes.
    assert sorted(asked) == ["3.example", "4.example"] and second["1.example"] == "clean" and skipped == []


def test_sorting_takes_its_budget_and_leaves_the_rest_for_the_next_count(monkeypatch):
    import threading
    release = threading.Event()

    def slow(host, client=None):
        if host == "slow.example":
            release.wait(5)
        return "clean"
    monkeypatch.setattr(workspace_guard, "classify", slow)
    categories, skipped = workspace_guard.sort_hosts(["fast.example", "slow.example"], budget=0.2)
    release.set()
    assert categories == {"fast.example": "clean", "slow.example": None} and skipped == ["slow.example"]


# --- Rules -------------------------------------------------------------------------------

def test_a_rule_closes_at_its_close_and_only_what_the_user_did_locks():
    assert workspace_guard.judge({"flagged": 4}) == (None, None)
    state, rule = workspace_guard.judge({"flagged": 5})
    assert state == "closed" and rule.name == "flagged_sites" and rule.repeat is False
    state, rule = workspace_guard.judge({"flagged": 5, "flagged_user": 5})
    assert state == "closed" and rule.name == "flagged_sites_by_user" and rule.repeat
    assert workspace_guard.judge({"flagged": 15, "flagged_user": 15}) == ("locked", rule)
    # Bytes never lock by themselves, the agent's typing never at all.
    assert workspace_guard.judge({"tx_bytes": 100 * GIB})[0] == "closed"
    assert workspace_guard.judge({"new_hosts_hour": 300})[0] == "closed"
    assert workspace_guard.judge({"typed_hosts_hour": 25})[1].repeat is False
    assert workspace_guard.judge({"view_bytes": 6 * GIB})[0] == "closed"
    assert workspace_guard.judge({"view_bytes": 5 * GIB}) == (None, None)
    assert workspace_guard.judge({"rx_bytes": 30 * GIB})[0] == "closed"
    assert all(isinstance(rule, Rule) and rule.close > 0 for rule in workspace_guard.RULES)
    assert all(rule.lock is None for rule in workspace_guard.RULES if rule.metric.endswith("bytes"))


def test_a_second_close_within_a_week_locks_and_a_lock_stays():
    now = DAY
    user = {"flagged": 5, "flagged_user": 5}
    first = workspace_guard.decide({}, user, "2026-10-30", now)
    assert first["state"] == "closed" and first["until"] == datetime(2026, 10, 31, tzinfo=timezone.utc)
    # The same day again: nothing new.
    assert workspace_guard.decide({**first, "closed_days": ["2026-10-30"]}, user, "2026-10-30", now) is None
    later = now + timedelta(days=3)
    second = workspace_guard.decide({"closed_days": ["2026-10-30"], "state": "closed", "until": first["until"]},
                                    user, "2026-11-02", later)
    assert second["state"] == "locked" and second["rule"] == "repeat:flagged_sites_by_user"
    assert second["until"] is None
    assert workspace_guard.decide({"state": "locked"}, user, "2026-11-02", later) is None
    # Past the week, a close is a close.
    assert workspace_guard.decide({"closed_days": ["2026-10-20"]}, user, "2026-11-02", later)["state"] == "closed"
    # What the agent was talked into closes again, never locks.
    agent = workspace_guard.decide({"closed_days": ["2026-10-30"]}, {"flagged": 9}, "2026-11-02", later)
    assert agent["state"] == "closed" and agent["rule"] == "flagged_sites"


def test_an_unlock_forgives_the_day_so_far_hour_by_hour():
    trail_doc = {"day": "2026-10-30", "counts": {"flagged": 7, "view_bytes": GIB},
                 "hours": {"14": {"new_hosts": 290}, "15": {"new_hosts": 5}}}
    baseline = {"day": "2026-10-30", "counts": {"flagged": 7, "view_bytes": GIB}, "hours": {"14": {"new_hosts": 290}}}
    later = {**trail_doc, "hours": {"14": {"new_hosts": 290}, "15": {"new_hosts": 300}}}
    assert workspace_guard.metrics(trail_doc, baseline)["flagged"] == 0
    assert workspace_guard.metrics(later, baseline)["new_hosts_hour"] == 300
    # A baseline of another day forgives nothing.
    assert workspace_guard.metrics(trail_doc, {**baseline, "day": "2026-10-29"})["flagged"] == 7


# --- Counting into the database ----------------------------------------------------------

def test_flagged_hosts_close_the_workspace_until_tomorrow_and_tell_the_operator(guard):
    store, alerts, _, _ = guard
    for n in range(1, 5):
        visit(f"adult-{n}.example", by="view")
    visit("news.example")
    workspace_guard.flush(UID)
    assert trail(store)["counts"]["flagged"] == 4 and workspace_guard.status(UID).state == "open" and alerts == []
    visit("bad.example")
    workspace_guard.flush(UID)
    found = workspace_guard.status(UID)
    assert found.state == "closed" and found.until == datetime(2026, 10, 31, tzinfo=timezone.utc)
    record = guard_doc(store)
    assert record["rule"] == "flagged_sites" and record["closed_days"] == ["2026-10-30"]
    assert record["history"][-1]["state"] == "closed"
    # What still runs ends (the tunnel, the browser's wake hold), once.
    assert guard[3] == [UID]
    # The guard itself goes a month after its last count, unless locked.
    assert record["expires_at"] == DAY + timedelta(days=workspace_guard.GUARD_RETENTION_DAYS)
    # One alert, without the account (privacy.html: no account identifiers).
    [alert] = alerts
    assert "closed for today" in alert and "flagged_sites" in alert and UID not in alert
    assert workspace_guard.uid_tag(UID) not in alert and "workspace_guard.py list" in alert
    # The trail: hosts, never anything else, kept 31 days from the day's start.
    day = trail(store)
    assert day["uid"] == UID and day["expires_at"] == datetime(2026, 11, 30, tzinfo=timezone.utc)
    assert {entry["host"] for entry in day["hosts"]} == {*(f"adult-{n}.example" for n in range(1, 5)),
                                                         "news.example", "bad.example"}
    # The next day it is open again, with a fresh count.
    guard[2]["now"] = DAY + timedelta(days=1)
    workspace_guard.reset()
    assert workspace_guard.status(UID).state == "open"


def test_a_second_close_in_the_week_locks_until_an_admin_unlocks(guard):
    store, alerts, clock, _ = guard
    for n in range(1, 5):
        visit(f"adult-{n}.example", by="user")
    visit("bad.example", by="user")
    workspace_guard.flush(UID)
    clock["now"] = DAY + timedelta(days=2)
    later = clock["now"].timestamp()
    for n in range(1, 5):
        visit(f"adult-{n}.example", by="user", at=later)
    visit("bad.example", by="user", at=later)
    workspace_guard.flush(UID)
    assert workspace_guard.status(UID).state == "locked" and "locked" in alerts[-1]
    record = guard_doc(store)
    assert record["rule"] == "repeat:flagged_sites_by_user" and record["expires_at"] is None
    # A lock stays through the cleanup.
    assert workspace_guard.cleanup_expired_trails(store.db, now=DAY + timedelta(days=400)) == 2
    assert guard_doc(store)["state"] == "locked"
    before = workspace_guard.unlock(UID, db=store.db)
    assert before.state == "locked" and workspace_guard.status(UID).state == "open"
    # What the day held is forgiven, and the old closes no longer lock.
    visit("adult-1.example", at=later + 60)
    workspace_guard.flush(UID)
    assert workspace_guard.status(UID).state == "open"
    record = guard_doc(store)
    assert record["closed_days"] == [] and record["history"][-1]["rule"] == "unlocked"
    assert record["expires_at"] > clock["now"]


def test_a_page_that_talks_the_agent_into_flagged_sites_closes_a_day_never_locks(guard):
    """The review of 2026-10-31: injected instructions, two days in a row."""
    store, _, clock, _ = guard
    for day in (0, 2):
        clock["now"] = DAY + timedelta(days=day)
        at = clock["now"].timestamp()
        for n in range(1, 5):
            visit(f"adult-{n}.example", at=at)
        visit("bad.example", at=at)
        workspace_guard.flush(UID)
        assert workspace_guard.status(UID).state == "closed"
        workspace_guard.reset()
    assert guard_doc(store)["rule"] == "flagged_sites"


def test_an_admin_is_counted_and_told_once_never_closed(guard, monkeypatch):
    store, alerts, _, _ = guard
    monkeypatch.setattr(workspace_guard, "_is_admin", lambda uid: True)
    for host in [*(f"adult-{n}.example" for n in range(1, 5)), "bad.example"]:
        visit(host)
    workspace_guard.flush(UID)
    visit("www.pornhub.com")
    workspace_guard.flush(UID)
    assert workspace_guard.status(UID).state == "open" and guard_doc(store).get("state") is None
    assert len(alerts) == 1 and "admin" in alerts[0] and "counted only" in alerts[0]


def test_the_live_views_bytes_and_the_vms_counters_count(guard):
    store, alerts, _, _ = guard
    workspace_guard.note_view_bytes(UID, 4 * GIB)
    workspace_guard.note_net(UID, {"rx": 10, "tx": 10, "boot": "a"})
    workspace_guard.note_net(UID, {"rx": 10 + GIB, "tx": 10 + GIB, "boot": "a"})
    # Anything a VM could make up is dropped.
    for odd in ({"rx": -1, "tx": 1, "boot": "a"}, {"rx": "1", "tx": 1, "boot": "a"}, {"rx": 1, "tx": 1}, "x"):
        workspace_guard.note_net(UID, odd)
    workspace_guard.flush(UID)
    counts = trail(store)["counts"]
    assert counts["view_bytes"] == 4 * GIB and counts["rx_bytes"] == GIB and counts["tx_bytes"] == GIB
    assert workspace_guard.status(UID).state == "open"
    workspace_guard.note_view_bytes(UID, 2 * GIB)
    workspace_guard.flush(UID)
    assert workspace_guard.status(UID).rule == "view_bytes" and "view" in alerts[-1]


def test_a_vm_whose_chrome_policy_differs_is_reported_once_a_day(guard):
    store, alerts, _, _ = guard
    workspace_guard.note_policy(UID, workspace_guard.expected_policy())
    workspace_guard.flush(UID)
    assert alerts == []
    workspace_guard.note_policy(UID, "0000000000000000")
    workspace_guard.flush(UID)
    workspace_guard.note_policy(UID, "")
    workspace_guard.flush(UID)
    assert len(alerts) == 1 and "policy differs" in alerts[0] and workspace_guard.status(UID).state == "open"


def test_a_state_that_cannot_be_read_never_closes_the_workspace(guard, monkeypatch):
    def broken(db, uid):
        raise RuntimeError("firestore down")
    monkeypatch.setattr(workspace_guard, "guard_ref", broken)
    assert workspace_guard.status(UID) is workspace_guard.OPEN


def test_without_a_database_in_test_profiles_the_guard_does_nothing(monkeypatch):
    workspace_guard.use_db(None)
    monkeypatch.setenv("UNIT_TEST_MODE", "1")
    workspace_guard.note_visit(UID, "adult-1.example", "view")
    assert workspace_guard._pending == {} and workspace_guard.status(UID) is workspace_guard.OPEN
    assert workspace_guard.cleanup_expired_trails() == 0


def test_trails_expire_after_thirty_days_and_go_with_the_account(guard, monkeypatch):
    store, _, clock, _ = guard
    visit("news.example")
    workspace_guard.flush(UID)
    workspace_guard.guard_ref(store.db, "someone-else").set({"uid": "someone-else"})
    workspace_guard.trail_ref(store.db, "someone-else", "2026-10-30").set(
        {"uid": "someone-else", "expires_at": DAY + timedelta(days=40)})
    assert workspace_guard.cleanup_expired_trails(store.db, now=DAY + timedelta(days=30)) == 0
    # The day's trail and the guard a month after its last count; the other account's guard has no date.
    assert workspace_guard.cleanup_expired_trails(store.db, now=DAY + timedelta(days=32)) == 2
    assert trail(store) == {} and guard_doc(store) == {}
    visit("news.example")
    workspace_guard.flush(UID)
    monkeypatch.setattr(agent_vm, "configured", lambda: False)
    agent_workspace.delete_for_account(store.db, UID)
    assert trail(store) == {} and guard_doc(store) == {}
    assert workspace_guard.guard_ref(store.db, "someone-else").get().exists


# --- Every way into the workspace asks first ------------------------------------------------

def close(store, state="closed"):
    until = datetime.now(timezone.utc) + timedelta(hours=3) if state == "closed" else None
    workspace_guard.guard_ref(store.db, UID).set({"uid": UID, "state": state, "until": until, "rule": "flagged_sites"})
    workspace_guard.reset()


def test_a_closed_workspace_refuses_the_agents_tools_and_open_workspace(store, fake_vm):
    workspace_guard.use_db(store.db)
    try:
        close(store)
        script = Agent([[("vm_exec", {"command": "ls"}), ("browser", {"action": "open", "url": "https://a.example"})]])
        loop = vm_loop(store, script)
        list(loop.run())
        text = workspace_guard.agent_text(workspace_guard.status(UID))
        assert results(loop) == [{"error": text}, {"error": text}] and "until" in text
        # Nothing reached a VM.
        assert fake_vm.calls == []
        close(store, "locked")
        script = Agent([[("open_workspace", {"task": "Check the site"})]])
        loop = vm_loop(store, script, workspace_closed=True, request_id="two")
        list(loop.run())
        assert results(loop) == [{"error": workspace_guard.LOCKED_FOR_AGENT}]
        assert store.get_turn(UID, loop.chat_id, loop.turn_id)["consensus"] == ANSWER
    finally:
        workspace_guard.use_db(None)


def test_the_agents_browser_calls_leave_their_hosts_and_counters(store, fake_vm, monkeypatch):
    workspace_guard.use_db(store.db)
    monkeypatch.setattr(workspace_guard, "classify", lambda host, client=None: CATEGORIES.get(host, "clean"))
    monkeypatch.setattr(workspace_guard, "_started", lambda: None)
    monkeypatch.setattr(workspace_guard, "_alert", lambda text: None)
    monkeypatch.setattr(workspace_guard, "_is_admin", lambda uid: False)
    try:
        answers = iter([
            {"status": "failed", "text": "Page.goto: net::ERR_BLOCKED_BY_ADMINISTRATOR at https://www.pornhub.com/\n"
                                         'Page: "Example"\nURL: https://example.com/',
             "net": {"rx": 1000, "tx": 100, "boot": "b1"}, "policy": "deadbeefdeadbeef"},
            {"status": "ok", "text": 'Typed.\nPage: "Form"\nURL: https://form.example/sign-up?ref=1',
             "net": {"rx": 3000, "tx": 900, "boot": "b1"}, "policy": workspace_guard.expected_policy()}])
        fake_vm.browser = lambda request: next(answers)
        script = Agent([[("browser", {"action": "open", "url": "https://www.pornhub.com/"})],
                        [("browser", {"action": "type", "ref": "e3", "text": "hello"})]])
        loop = vm_loop(store, script)
        list(loop.run())
        workspace_guard.flush(UID)
        day = workspace_guard.trail_ref(store.db, UID, workspace_guard.day_key()).get().to_dict()
        hosts = {entry["host"]: entry for entry in day["hosts"]}
        assert set(hosts) == {"www.pornhub.com", "example.com", "form.example"}
        assert hosts["www.pornhub.com"]["category"] == "adult" and hosts["www.pornhub.com"]["by"] == ["agent"]
        assert hosts["form.example"].get("typed_hour") and not hosts["example.com"].get("typed_hour")
        # The address's path and query stay out; the counters add what the VM sent and received.
        assert "sign-up" not in json.dumps(day, default=str)
        assert day["counts"]["rx_bytes"] == 2000 and day["counts"]["tx_bytes"] == 800
        # A refused call's policy is not a report: only an answered one counts.
        assert (workspace_guard.guard_ref(store.db, UID).get().to_dict() or {}).get("noted") is None
    finally:
        workspace_guard.use_db(None)


def test_a_closed_workspace_refuses_the_view_the_terminal_and_the_takeover(view_api, fake_vm, monkeypatch):
    client, store, gateway, _ = view_api
    workspace_guard.use_db(store.db)
    try:
        for state, code in (("closed", workspace_router.CLOSE_GUARDED), ("locked", workspace_router.CLOSE_LOCKED)):
            close(store, state)
            for path in ("/agent/workspace/view", "/agent/workspace/terminal"):
                with client.websocket_connect(path) as ws:
                    ws.send_text(json.dumps({"id_token": "verified"}))
                    with pytest.raises(WebSocketDisconnect) as closed:
                        ws.receive_text()
                assert closed.value.code == code
            assert fake_vm.calls == [] and gateway.url is None
            refused = client.post("/agent/workspace/control", json={"holder": "user"}, headers=AUTH)
            assert refused.status_code == 403
            assert refused.json()["detail"] == workspace_guard.user_text(workspace_guard.status(UID))
            status = client.get("/agent/workspace", headers=AUTH).json()
            assert status["guard"]["state"] == state
        # Handing the browser back stays possible.
        assert client.post("/agent/workspace/control", json={"holder": "agent"}, headers=AUTH).status_code == 404
    finally:
        workspace_guard.use_db(None)


def test_an_open_view_counts_its_bytes_and_hosts_and_ends_once_the_rules_close(view_api, fake_vm, monkeypatch):
    client, store, gateway, _ = view_api
    workspace_guard.use_db(store.db)
    noted = []
    monkeypatch.setattr(workspace_guard, "CHECK_SECONDS", 0.05)
    monkeypatch.setattr(workspace_guard, "VIEW_BYTES_SECONDS", 0.05)
    monkeypatch.setattr(workspace_guard, "note_view_bytes", lambda uid, count: noted.append(("bytes", count)))
    monkeypatch.setattr(workspace_guard, "note_visit", lambda uid, host, by, **kw: noted.append(("visit", host, by)))
    monkeypatch.setattr(workspace_guard, "note_net", lambda uid, counters: noted.append(("net", counters)))
    monkeypatch.setattr(workspace_guard, "note_policy", lambda uid, value: noted.append(("policy", value)))
    # After "ready", before the VNC banner: what the relay's watch says.
    gateway.frames[3:3] = [b"\x02" + json.dumps({"policy": "abc"}).encode() + b"\n",
                           b"\x02" + b"x" * 5000,
                           b"\x02\n" + json.dumps({"visit": "adult-1.example"}).encode() + b"\n"
                           + json.dumps({"net": {"rx": 1, "tx": 2, "boot": "b"}}).encode() + b"\n"]
    try:
        ws = open_view(client)
        ws.send_bytes(b"12345")
        time.sleep(0.2)
        assert ("visit", "adult-1.example", "view") in noted and ("policy", "abc") in noted
        assert ("net", {"rx": 1, "tx": 2, "boot": "b"}) in noted
        assert sum(count for kind, count, *_ in noted if kind == "bytes") >= len(b"12345RFB 003.008\n")
        close(store)
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_bytes()
        assert closed.value.code == workspace_router.CLOSE_GUARDED
    finally:
        workspace_guard.use_db(None)


def test_an_open_terminal_ends_once_the_rules_close_and_its_bytes_never_count(view_api, fake_vm, monkeypatch):
    """A runaway loop in the user's own terminal prints gigabytes: that is no
    misuse of the browser (the review of 2026-10-31)."""
    client, store, shell = terminal_api(view_api, monkeypatch, [b"agent@workbench:~$ "])
    workspace_guard.use_db(store.db)
    counted = []
    monkeypatch.setattr(workspace_guard, "CHECK_SECONDS", 0.05)
    monkeypatch.setattr(workspace_guard, "VIEW_BYTES_SECONDS", 0.05)
    monkeypatch.setattr(workspace_guard, "note_view_bytes", lambda uid, count: counted.append(count))
    try:
        with client.websocket_connect("/agent/workspace/terminal") as ws:
            ws.send_text(json.dumps({"id_token": "verified", "cols": 80, "rows": 24}))
            assert [json.loads(ws.receive_text())["state"] for _ in range(2)] == ["connecting", "ready"]
            assert ws.receive_bytes() == b"agent@workbench:~$ "
            close(store, "locked")
            with pytest.raises(WebSocketDisconnect) as closed:
                ws.receive_bytes()
        assert closed.value.code == workspace_router.CLOSE_LOCKED and shell.closed and counted == []
    finally:
        workspace_guard.use_db(None)


def test_the_relays_lines_reach_the_rules_with_who_steered_and_nothing_else(monkeypatch):
    noted = []
    monkeypatch.setattr(workspace_guard, "note_visit", lambda uid, host, by, **kw: noted.append((host, by)))
    monkeypatch.setattr(workspace_guard, "note_net", lambda uid, counters: noted.append(counters))
    monkeypatch.setattr(workspace_guard, "note_policy", lambda uid, value: noted.append(value))
    assert workspace_router.relay_line(UID, b'{"state": "ready"}') == "ready"
    for line in (b'{"visit": "a.example"}', b'{"net": {"rx": 1}}', b'{"policy": "p"}', b"[1, 2]", b"not json",
                 b'{"visit": 3}', b'{"state": 5}'):
        assert workspace_router.relay_line(UID, line) is None
    assert noted == [("a.example", "view"), {"rx": 1}, "p"]
    # From the takeover on, a page is the user's; handed back, the agent's they watch.
    workspace_router._note_takeover(UID, "user")
    workspace_router.relay_line(UID, b'{"visit": "b.example"}')
    workspace_router._note_takeover(UID, "agent")
    workspace_router.relay_line(UID, b'{"visit": "c.example"}')
    assert noted[-2:] == [("b.example", "user"), ("c.example", "view")]


def test_a_closed_workspace_takes_no_restore_and_no_key(monkeypatch, store):
    import inspect
    from fastapi import HTTPException
    from app.api.routers import agent as agent_router
    workspace_guard.use_db(store.db)
    close(store, "locked")
    with pytest.raises(HTTPException) as refused:
        agent_router._refuse_closed_workspace(UID)
    assert refused.value.status_code == 403 and refused.value.detail == workspace_guard.LOCKED_FOR_USER
    for route in (agent_router.restore_agent_vm, agent_router.save_agent_secret):
        assert "_refuse_closed_workspace(uid)" in inspect.getsource(route)


def test_only_verified_accounts_reach_the_workspace(monkeypatch):
    """The workspace needs a confirmed e-mail address (Max, 2026-10-30): the
    view and terminal sign in through verify_user_token's default, which
    refuses an unverified token (security.py), never allow_unverified."""
    seen = []

    def verify(token, **kwargs):
        seen.append(kwargs)
        return UID
    monkeypatch.setattr(workspace_router, "verify_user_token", verify)
    monkeypatch.setattr(workspace_router, "require_agent_access", lambda uid: None)
    monkeypatch.setattr(workspace_router, "allowed", lambda uid: True)
    assert workspace_router._sign_in("token") == UID and seen == [{}]
    import inspect
    from app.api.routers import chat_history
    from app.core import security
    assert "allow_unverified" not in inspect.getsource(chat_history._chat_uid)
    assert inspect.signature(security.verify_user_token).parameters["allow_unverified"].default is False


# --- The browser VM's own rules ------------------------------------------------------------

def browser_file(name):
    return agent_workspace.tool_files("browser")[name].decode()


def test_chromes_policy_blocks_what_the_test_sprite_showed_and_keeps_playwright_working():
    """Measured on a test Sprite 2026-10-30: SafeSites blocks adult sites
    (ERR_BLOCKED_BY_ADMINISTRATOR), Safe Browsing phishing and malware once
    its lists loaded (ERR_BLOCKED_BY_CLIENT), URLBlocklist the debugging port,
    file://, DevTools and chrome://flags; an upload still works without file
    dialogs. DeveloperToolsAvailability 2 shut Playwright out of every page,
    DNS over HTTPS every connection (the provider lets through only what its
    own resolver gave out): neither may come back."""
    policy = json.loads(browser_file("policy.json"))
    assert policy["SafeSitesFilterBehavior"] == 1 and policy["ForceGoogleSafeSearch"] is True
    assert policy["SafeBrowsingProtectionLevel"] == 1 and policy["DisableSafeBrowsingProceedAnyway"] is True
    assert policy["AllowFileSelectionDialogs"] is False and policy["PromptForDownloadLocation"] is False
    assert policy["IncognitoModeAvailability"] == 1 and policy["BrowserGuestModeEnabled"] is False
    assert policy["AllowDeletingBrowserHistory"] is False and policy["ExtensionInstallBlocklist"] == ["*"]
    assert policy["PasswordManagerEnabled"] is False and policy["PrintingEnabled"] is False
    assert {"file://*", "devtools://*", "chrome://flags", "chrome://restart", "chrome://quit", "127.0.0.1:9222",
            "localhost:9222"} <= set(policy["URLBlocklist"])
    assert "DeveloperToolsAvailability" not in policy and not any(key.startswith("DnsOverHttps") for key in policy)


def test_chrome_starts_only_under_its_rules_and_restarts_once_for_new_ones():
    display, harden = browser_file("display.sh"), browser_file("harden.sh")
    rules = display.index('bash "$(dirname "$0")/harden.sh"')
    failed = display[rules:display.index("fi", rules)]
    # A Chrome that runs under older rules ends too (the review of 2026-10-31).
    assert rules < display.index("setsid nohup google-chrome") and "stop_chrome" in failed and "exit 1" in failed
    assert 'flags="webgl-1 rules-$(cat "$dir/hardened" 2>/dev/null)"' in display
    assert "/etc/opt/chrome/policies/managed/consens.json" in harden and 'cmp -s "$here/policy.json"' in harden
    assert "dpkg-divert" in harden and "exit 1" in harden and "openbox --reconfigure" in harden
    # setup.sh no longer writes a policy of its own.
    assert "policies/managed" not in browser_file("setup.sh")


def test_openbox_starts_no_program_and_shows_no_menu():
    rc, menu = browser_file("openbox-rc.xml"), browser_file("openbox-menu.xml")
    for action in ('name="Execute"', 'name="ShowMenu"', "<execute>", 'name="Exit"', 'name="Iconify"'):
        assert action not in rc
    assert "<item" not in menu and "<execute>" not in menu


def test_the_relay_names_each_tabs_host_once_it_changes(monkeypatch):
    import threading
    from test_agent_workspace import load
    relay = load("relay")
    said, done = [], threading.Event()
    lists = iter([
        [{"type": "page", "id": "1", "url": "https://adult-1.example/path?q=secret"},
         {"type": "page", "id": "2", "url": "chrome://newtab/"}, {"type": "iframe", "id": "3", "url": "https://x.y"}],
        [{"type": "page", "id": "1", "url": "https://adult-1.example/other"},
         {"type": "page", "id": "2", "url": "https://news.example/"}],
        [{"type": "page", "id": "1", "url": "https://adult-2.example/"}],
    ])

    class Response:
        def __init__(self, body):
            self.body = body

        def read(self):
            return json.dumps(self.body).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def urlopen(url, timeout):
        assert url == "http://127.0.0.1:9222/json/list"
        try:
            return Response(next(lists))
        except StopIteration:
            done.set()
            raise OSError("gone")
    monkeypatch.setattr(relay.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(relay, "say", said.append)
    monkeypatch.setattr(relay, "policy_print", lambda: "fingerprint")
    monkeypatch.setattr(relay, "net_counters", lambda: {"rx": 1, "tx": 2, "boot": "b"})
    relay.watch(done, look=0.001, net=1)
    visits = [line["visit"] for line in said if "visit" in line]
    assert visits == ["adult-1.example", "news.example", "adult-2.example"]
    assert said[0] == {"policy": "fingerprint"} and {"net": {"rx": 1, "tx": 2, "boot": "b"}} in said
    assert relay.page_host("https://Example.COM./x") == "example.com" and relay.page_host("file:///etc") is None


def test_the_relays_watch_outlives_a_failed_look(monkeypatch):
    """A Chrome that restarts mid-answer (IncompleteRead) cost the watch the
    rest of the view before (the review of 2026-10-31); now one look."""
    import http.client
    import threading
    from test_agent_workspace import load
    relay = load("relay")
    said, done, looks = [], threading.Event(), []

    class Response:
        def read(self):
            return json.dumps([{"type": "page", "id": "1", "url": "https://after.example/"}]).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def urlopen(url, timeout):
        looks.append(url)
        if len(looks) == 1:
            raise http.client.IncompleteRead(b"")
        done.set()
        return Response()
    monkeypatch.setattr(relay.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(relay, "say", said.append)
    monkeypatch.setattr(relay, "policy_print", lambda: "")
    monkeypatch.setattr(relay, "net_counters", lambda: None)
    relay.watch(done, look=0.001, net=1000)
    assert {"visit": "after.example"} in said and len(looks) == 2
