"""Browser regressions for the Phase-4 frontend state races."""

import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest
from playwright.sync_api import expect


FIREBASE_APP_STUB = """
export function initializeApp(config) { return { config }; }
"""

FIREBASE_AUTH_STUB = """
const callbacks = [];
const auth = { currentUser: null };

function makeUser(uid) {
  return {
    uid,
    email: uid + "@example.invalid",
    emailVerified: true,
    displayName: uid,
    getIdToken: async () => "token-" + uid,
    reload: async () => {},
  };
}

window.__switchE2EUser = async function (uid) {
  auth.currentUser = uid ? makeUser(uid) : null;
  for (const callback of callbacks) await callback(auth.currentUser);
};

export class GoogleAuthProvider { setCustomParameters() {} }
export const browserLocalPersistence = {};
export const browserSessionPersistence = {};
export function getAuth() { return auth; }
export async function setPersistence() {}
export function onIdTokenChanged(_auth, callback) {
  callbacks.push(callback);
  queueMicrotask(() => window.__switchE2EUser(window.__E2E_INITIAL_UID));
  return () => {};
}
export function onAuthStateChanged(_auth, callback) { return onIdTokenChanged(_auth, callback); }
export async function signOut() { await window.__switchE2EUser(null); }
export async function signInWithEmailAndPassword() { return { user: auth.currentUser }; }
export async function signInWithPopup() { return { user: auth.currentUser }; }
export async function signInWithRedirect() {}
export async function getRedirectResult() { return null; }
export async function sendPasswordResetEmail() {}
export async function sendEmailVerification() {}
"""


@pytest.fixture(scope="session")
def phase4_server(request):
    """Read-only frontend server for fully mocked Phase-4 browser races.

    No request in this module reaches Firestore. E2E mode still enforces the
    loopback emulator target and disables every lifespan writer, but Java is
    intentionally not a prerequisite for these browser-only regressions.
    """

    port = int(os.environ.get("E2E_PHASE4_PORT", "8033"))
    base_url = f"http://127.0.0.1:{port}"
    # Imported fixtures acquire one FixtureDef per test module. Keep one
    # server per pytest invocation so modules never attach to another child
    # while their own child fails to bind the same port.
    if getattr(request.config, "_phase4_server_url", None):
        yield request.config._phase4_server_url
        return
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"Phase-4 port {port} is already in use; choose E2E_PHASE4_PORT")
    env = os.environ.copy()
    env.update({
        "E2E_TEST_MODE": "1",
        "FIRESTORE_EMULATOR_HOST": "127.0.0.1:8085",
        "GOOGLE_CLOUD_PROJECT": "demo-consensio-e2e",
        "GCLOUD_PROJECT": "demo-consensio-e2e",
        "FIREBASE_PROJECT_ID": "demo-consensio-e2e",
        "MOCK_LLM": "1",
        "MOCK_AUTH": "1",
        "DISABLE_RATE_LIMIT": "1",
    })
    env.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--port", str(port), "--log-level", "warning"],
        cwd=str(Path(__file__).resolve().parents[2]),
        env=env,
    )
    deadline = time.monotonic() + 45
    try:
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"Phase-4 frontend server exited with {proc.returncode}")
            try:
                with urllib.request.urlopen(base_url + "/app", timeout=2) as response:
                    if response.status < 500:
                        break
            except (urllib.error.URLError, OSError):
                time.sleep(0.25)
        else:
            raise RuntimeError("Phase-4 frontend server did not become ready")
        request.config._phase4_server_url = base_url
        yield base_url
    finally:
        request.config._phase4_server_url = None
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def _json(route, payload, status=200):
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(payload),
    )


def test_phase4_server_reuses_its_child_and_rejects_an_unowned_listener(phase4_server, request, monkeypatch):
    """A second imported FixtureDef must not start or terminate another child."""
    def unexpected_process(*_args, **_kwargs):
        raise AssertionError('A second Phase-4 process must not be started')
    monkeypatch.setattr(subprocess, 'Popen', unexpected_process)
    factory = globals()['phase4_server'].__wrapped__
    imported_fixture = factory(request)
    assert next(imported_fixture) == phase4_server
    with pytest.raises(StopIteration):
        next(imported_fixture)
    assert request.config._phase4_server_url == phase4_server
    # Another pytest invocation cannot silently attach to this listener.
    foreign_fixture = factory(SimpleNamespace(config=SimpleNamespace()))
    with pytest.raises(RuntimeError, match='already in use'):
        next(foreign_fixture)


def _route_account_settings(page, settings=None, revision=0):
    """/api/my/settings for one page, held in memory.

    The account starts without saved settings (revision 0) and keeps what the
    page sends, checked by the real route's rules (user_settings); no test
    writes the shared emulator. Returns the state for assertions; a value the
    route would refuse is collected in ``rejected``.
    """
    from app.services import user_settings as account_settings

    state = {"settings": dict(settings or {}), "revision": revision, "field_revisions": {},
             "patches": [], "rejected": []}

    def handle(route):
        answer = {}
        if route.request.method == "PATCH":
            sent = route.request.post_data_json["settings"]
            state["patches"].append(sent)
            changes, rejected = account_settings.validate_changes(sent)
            state["rejected"].extend(rejected)
            if changes:
                state["revision"] += 1
            for name, value in changes.items():
                if value is None:
                    state["settings"].pop(name, None)
                else:
                    state["settings"][name] = value
                state["field_revisions"][name] = state["revision"]
            answer["rejected"] = rejected
        _json(route, {"settings": state["settings"], "revision": state["revision"],
                      "field_revisions": state["field_revisions"], **answer})

    page.route("**/api/my/settings", handle)
    return state


def _real_firebase_page(
    browser, app_server, initial_uid="account-a", path="/app", init_script=None, *, has_touch=False,
    before_goto=None,
):
    context = browser.new_context(viewport={"width": 1280, "height": 820}, has_touch=has_touch)
    context.add_init_script(
        f"window.__E2E_INITIAL_UID = {json.dumps(initial_uid)};"
    )
    if init_script:
        context.add_init_script(init_script)
    context.route(
        "https://www.gstatic.com/firebasejs/9.22.0/firebase-app.js",
        lambda route: route.fulfill(content_type="application/javascript", body=FIREBASE_APP_STUB),
    )
    context.route(
        "https://www.gstatic.com/firebasejs/9.22.0/firebase-auth.js",
        lambda route: route.fulfill(content_type="application/javascript", body=FIREBASE_AUTH_STUB),
    )
    context.route(
        "https://cloud.umami.is/**",
        lambda route: route.fulfill(content_type="application/javascript", body="/* e2e */"),
    )
    page = context.new_page()
    page.route("**/confirm-registration", lambda route: _json(route, {"status": "ok"}))
    page.route(
        "**/user_status",
        lambda route: _json(route, {"is_pro": False, "limit": 3, "deep_limit": 0}),
    )
    page.route(
        "**/usage",
        lambda route: _json(route, {
            "is_pro": False,
            "remaining": 3,
            "deep_remaining": 0,
            "total_limit": 3,
            "deep_total_limit": 0,
        }),
    )
    page.route(
        "**/bookmarks?*",
        lambda route: _json(route, {"bookmarks": [], "next_cursor": None}),
    )
    page.route("**/auth/session", lambda route: _json(route, {"status": "ok"}))
    _route_account_settings(page)
    # Routes and listeners a test needs from the first request on.
    if before_goto:
        before_goto(page)
    page.goto(app_server + path, wait_until="domcontentloaded")
    page.wait_for_function(
        "() => window.__consensioAuthState?.known === true"
        " && typeof window.openShareDialog === 'function'"
    )
    return context, page


def test_compare_stream_keeps_model_loading_nodes(browser, phase4_server):
    """Streamed tokens update a Compare answer in place: the answer that is
    still waiting keeps its loading node, nothing is rebuilt per chunk."""
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.evaluate('''() => {
          const registry = window.App.runRegistry;
          const run = registry.create({question:'Streaming question', config:{agentMode:false,
            providers:[{provider:'OpenAI',modelLabel:'OpenAI'}, {provider:'Gemini',modelLabel:'Gemini'}]}});
          run.modelResults = {OpenAI:{status:'streaming',streamText:'A new answer'}, Gemini:{status:'pending'}};
          run.phase = 'answers';
          registry.setStatus(run.runId,'running');
          window.__streamRun = run;
          window.__waiting = document.querySelector('.is-direct .answer-reader-body[data-provider="Gemini"]');
          window.__waitingSkeleton = window.__waiting?.querySelector('.answer-skeleton');
        }''')
        assert page.evaluate('Boolean(window.__waiting && window.__waitingSkeleton)')
        page.evaluate('''async () => {
          for (let i = 0; i < 12; i++) {
            window.__streamRun.modelResults.OpenAI.streamText += ' another token';
            window.App.runRegistry.renderVisible();
            await new Promise(resolve => setTimeout(resolve, 120));
          }
        }''')
        assert page.evaluate('''() => window.__waiting === document.querySelector('.is-direct .answer-reader-body[data-provider="Gemini"]')
          && window.__waitingSkeleton === window.__waiting.querySelector('.answer-skeleton')''')
        expect(page.locator('#openaiResponse .collapsible-content')).to_contain_text('another token')
        expect(page.locator('.is-direct .answer-reader-body[data-provider="OpenAI"]')).to_contain_text('another token')
        # A comparison continues nothing: no history above it.
        expect(page.locator('#threadHistory .thread-history-turn')).to_have_count(0)
    finally:
        context.close()


def test_auth_module_failure_exposes_usable_login_dialog(browser, phase4_server):
    context = browser.new_context(viewport={"width": 1280, "height": 820})
    context.add_init_script(
        "localStorage.setItem('id_token', 'stale-token');"
        "window.AUTH_BOOTSTRAP_TIMEOUT_MS = 30;"
    )
    context.route("**/static/firebase.js*", lambda route: route.abort())
    context.route("**/static/dist/firebase.*.js", lambda route: route.abort())
    context.route(
        "https://cloud.umami.is/**",
        lambda route: route.fulfill(content_type="application/javascript", body="/* e2e */"),
    )
    page = context.new_page()
    try:
        page.goto(phase4_server + "/app", wait_until="domcontentloaded")
        assert page.evaluate(
            "() => typeof window.App?.emailVerification"
        ) == "object"
        login = page.locator("#authTopLoginBtn")
        expect(login).to_be_visible(timeout=5000)
        expect(page.locator("#loginContainer .login-skeleton")).to_have_count(0)

        login.click()
        modal = page.get_by_role("dialog", name="Log in to consens.io")
        expect(modal).to_be_visible()
        expect(page.locator("#loginError")).to_contain_text("Logging in isn’t possible right now")
        expect(page.locator("#closeLoginModal")).to_be_focused()

        page.keyboard.press("Escape")
        expect(modal).to_be_hidden()
        expect(login).to_be_focused()
    finally:
        context.close()


@pytest.mark.parametrize("width", [1280, 1000])
def test_watch_feature_nudge_never_raises_answer_over_fixed_composer(browser, phase4_server, width):
    """Regression fuer den ersten Watch-Hinweis am fertigen Consensus-Fuss.

    Der Hinweis muss selbst ueber dem Composer schweben. Die Antwort-Huelle
    darf dafuer keinen hoeheren Stacking-Level bekommen, sonst uebermalt ihr
    Text das fixe Eingabefeld, bis der Hinweis geschlossen wird.

    1280 px: der Watch-Knopf steht im Antwort-Fuss direkt ueber dem Composer
    (der urspruengliche Fehlerfall). Bis 1099 px zieht mobile-header.js ihn in
    die Kopfzeile. Die Antwort wird ueber den echten Weg aufgedeckt: von Hand
    gesetzte Klassen liessen `is-hidden` stehen, die Kopfzeile versteckte den
    Knopf, und der Hinweis blendet sich ohne sichtbaren Anker zu Recht aus.
    """

    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({"width": width, "height": 800})
        page.evaluate(
            """() => {
              localStorage.removeItem("consensio.watchFeatureNudge.dismissed.v1");
              localStorage.removeItem("consensio.watchFeatureNudge.runs.v1");
              window.exitHeroMode();
              window.revealConsensusOutput();
              document.getElementById("consensusAnswerBody").innerHTML =
                Array.from({ length: 20 }, (_, index) =>
                  `<p>Consensus answer line ${index + 1}: enough content to make the thread scroll.</p>`
                ).join("");
              // A saved answer draws its footer itself (firebase.js).
              window.updateAgentModeUI();
              window.App.consensusFooter.render();
              window.App.state.set("lastShareResultId", "phase4-nudge-result", "share");
              // Der Hinweis kommt erst ab der dritten abgeschlossenen Frage.
              window.App.watch.showFeatureNudge();
              window.App.watch.showFeatureNudge();
              window.App.watch.showFeatureNudge();
            }"""
        )
        expect(page.locator("#runProvenance")).to_be_visible()
        expect(page.locator("#consensusWatchButton")).to_be_visible()
        expect(page.locator("#watchFeatureNudge")).to_be_visible(timeout=3000)
        # Der Hinweis gehoert zum Watch-Knopf der Consensus-Antwort, nicht zum
        # Agent-Anker (#agentWatchAnchor) mit derselben Klasse.
        expect(page.locator(".watch-feature-anchor:has(#consensusWatchButton)")).to_have_class(
            re.compile(r"\bhas-feature-nudge\b")
        )
        # Beim Lesen laeuft die Antwort unter dem fixen Composer durch. Genau
        # dort zeigt sich eine angehobene Antwort-Huelle: ihr Text malt dann
        # ueber dem Eingabefeld. Am Ende des Threads liegt nichts darunter.
        reading = page.evaluate(
            """() => {
              const inputElement = document.querySelector(".input-section");
              const answerElement = document.getElementById("consensusAnswerBody");
              const before = answerElement.getBoundingClientRect();
              window.scrollBy(0, before.top + before.height / 2 - inputElement.getBoundingClientRect().top);
              const input = inputElement.getBoundingClientRect();
              const answer = answerElement.getBoundingClientRect();
              const x = Math.max(input.left, answer.left) + 10;
              const y = Math.max(input.top, answer.top) + 8;
              const painted = document.elementFromPoint(x, y);
              return {
                answerRunsUnderComposer: answer.top < input.top && answer.bottom > input.top + 8
                  && answer.left < input.right && answer.right > input.left,
                composerOwnsPaint: inputElement === painted || inputElement.contains(painted),
              };
            }"""
        )
        assert reading["answerRunsUnderComposer"] is True
        assert reading["composerOwnsPaint"] is True
        page.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
        page.wait_for_timeout(100)

        metrics = page.evaluate(
            """() => {
              const rect = selector => document.querySelector(selector).getBoundingClientRect();
              const overlaps = (a, b) =>
                a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
              const nudge = document.getElementById("watchFeatureNudge");
              const inputElement = document.querySelector(".input-section");
              const input = inputElement.getBoundingClientRect();
              const answer = rect("#consensusAnswerBody");
              const footer = rect("#runProvenance");
              const nudgeRect = nudge.getBoundingClientRect();
              const overlapX = Math.max(input.left, footer.left) + 10;
              const overlapY = Math.max(input.top, footer.top) + 2;
              const paintedAtOverlap = document.elementFromPoint(overlapX, overlapY);
              return {
                nudgeIsBodyLayer: nudge.parentElement === document.body,
                sectionRaised: document.querySelector(".consensus-section")
                  .classList.contains("has-watch-feature-nudge"),
                answerOverlapsComposer: overlaps(answer, input),
                footerComposerOverlap: Math.max(0, footer.bottom - input.top),
                composerOwnsOverlapPaint: inputElement === paintedAtOverlap
                  || inputElement.contains(paintedAtOverlap),
                nudgeOverlapsComposer: overlaps(nudgeRect, input),
                nudgeZ: Number(getComputedStyle(nudge).zIndex),
                composerZ: Number(getComputedStyle(document.querySelector(".input-section")).zIndex),
              };
            }"""
        )
        assert metrics["nudgeIsBodyLayer"] is True
        assert metrics["sectionRaised"] is False
        assert metrics["answerOverlapsComposer"] is False
        assert metrics["footerComposerOverlap"] < 20
        assert metrics["composerOwnsOverlapPaint"] is True
        assert metrics["nudgeOverlapsComposer"] is False
        assert metrics["nudgeZ"] > metrics["composerZ"]
    finally:
        context.close()


def test_account_a_late_bookmark_save_cannot_mutate_account_b(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.evaluate(
            """() => {
              const nativeFetch = window.fetch.bind(window);
              window.fetch = (input, options = {}) => {
                if (String(input) === "/bookmark" && options.method === "POST") {
                  return new Promise(resolve => {
                    window.__resolveAccountABookmark = () => resolve(new Response(JSON.stringify({
                      bookmark: { id: "account-a-bookmark", query: "A private question", responses: {} }
                    }), { status: 200, headers: { "Content-Type": "application/json" } }));
                  });
                }
                return nativeFetch(input, options);
              };
              window.__lateSave = window.saveBookmark(
                "A private question", "A private answer", "OpenAI", "normal"
              );
            }"""
        )
        page.wait_for_function("() => typeof window.__resolveAccountABookmark === 'function'")
        page.evaluate(
            """async () => {
              await window.__switchE2EUser(null);
              await window.__switchE2EUser("account-b");
              window.__resolveAccountABookmark();
              await window.__lateSave;
            }"""
        )

        assert page.evaluate("() => window.__consensioAuthState.uid") == "account-b"
        assert page.evaluate(
            "() => window.bookmarksData.some(item => item.id === 'account-a-bookmark')"
        ) is False
        expect(page.locator('[data-id="account-a-bookmark"]')).to_have_count(0)
    finally:
        context.close()


def test_account_a_share_response_cannot_overwrite_account_b_view(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.evaluate(
            """() => {
              const nativeFetch = window.fetch.bind(window);
              window.fetch = (input, options = {}) => {
                if (String(input) === "/api/my/shares") {
                  const authHeader = options.headers?.Authorization || "";
                  if (authHeader.includes("account-a")) {
                    return new Promise(resolve => {
                      window.__resolveAccountAShares = () => resolve(new Response(JSON.stringify({
                        site_url: "https://example.invalid",
                        shares: [{ share_id: "share-a", status: "active", path: "/a", question: "A private share" }]
                      }), { status: 200, headers: { "Content-Type": "application/json" } }));
                    });
                  }
                  return Promise.resolve(new Response(JSON.stringify({
                    site_url: "https://example.invalid",
                    shares: [{ share_id: "share-b", status: "active", path: "/b", question: "B share" }]
                  }), { status: 200, headers: { "Content-Type": "application/json" } }));
                }
                return nativeFetch(input, options);
              };
              window.openShareDialog("list");
            }"""
        )
        page.wait_for_function("() => typeof window.__resolveAccountAShares === 'function'")
        page.evaluate(
            """async () => {
              await window.__switchE2EUser(null);
              await window.__switchE2EUser("account-b");
              window.openShareDialog("list");
            }"""
        )
        expect(page.locator("#shareModalBody")).to_contain_text("B share")

        page.evaluate("() => window.__resolveAccountAShares()")
        page.wait_for_timeout(100)
        expect(page.locator("#shareModalBody")).to_contain_text("B share")
        expect(page.locator("#shareModalBody")).not_to_contain_text("A private share")
    finally:
        context.close()


def test_last_bookmark_click_wins_when_detail_responses_arrive_out_of_order(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.evaluate(
            """() => {
              const nativeFetch = window.fetch.bind(window);
              const responseFor = (id, question) => new Response(JSON.stringify({
                bookmark: {
                  id, query: question, title: question, mode: "normal",
                  responses: { OpenAI: "Model answer", consensus: "Consensus " + id },
                  sources: [], attachments: []
                }
              }), { status: 200, headers: { "Content-Type": "application/json" } });
              window.fetch = (input, options = {}) => {
                if (String(input) === "/bookmarks/bookmark_a") {
                  return new Promise(resolve => {
                    window.__resolveBookmarkA = () => resolve(responseFor("bookmark_a", "Question A"));
                  });
                }
                if (String(input) === "/bookmarks/bookmark_b") {
                  return Promise.resolve(responseFor("bookmark_b", "Question B"));
                }
                return nativeFetch(input, options);
              };
              window.__openA = window.openBookmark("bookmark_a");
            }"""
        )
        page.wait_for_function("() => typeof window.__resolveBookmarkA === 'function'")
        page.evaluate("() => { window.__openB = window.openBookmark('bookmark_b'); }")
        expect(page.locator("#threadAskText")).to_have_text("Question B")

        page.evaluate("() => window.__resolveBookmarkA()")
        page.wait_for_timeout(100)
        expect(page.locator("#threadAskText")).to_have_text("Question B")
        assert page.evaluate("() => window.App.bookmarkSession.currentId()") == "bookmark_b"
        assert page.evaluate("() => window.lastQuestion") == "Question B"
        assert page.evaluate("() => window.consensusCitationMeta?.question") == "Question B"
        expect(page.locator("#appToasts .toast")).to_have_count(0)
    finally:
        context.close()


def test_logged_out_watch_deep_link_survives_and_late_login_renders(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server, initial_uid=None, path="/app/watches")
    try:
        page.route(
            "**/api/my/watches",
            lambda route: _json(route, {
                "watches": [],
                "limits": {"plan": "free", "active_count": 0, "active_limit": 1},
            }),
        )
        page.route("**/api/my/watch-brief", lambda route: _json(route, {"brief": {}}))
        page.route("**/api/my/telegram", lambda route: _json(route, {"telegram": {}}))

        # A guest sees what a watch is, by example, and the way in (J3).
        expect(page.locator("#watchDashBody")).to_contain_text("What a watch looks like")
        expect(page.locator(".wd-item.is-example")).to_be_visible()
        expect(page.locator("#watchDashCreate")).to_have_text("Log in to start watching")
        assert page.url.endswith("/app/watches")

        page.evaluate("() => window.__switchE2EUser('account-b')")
        expect(page.locator("#watchDashCreate")).to_have_text("New watch", timeout=5000)
        expect(page.locator("#watchDashBody")).to_contain_text("Start from an example")
        assert page.url.endswith("/app/watches")
    finally:
        context.close()


def test_all_model_failures_end_in_error_without_consensus(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        consensus_requests = []
        page.on(
            "request",
            lambda request: consensus_requests.append(request.url)
            if request.url.endswith("/consensus") else None,
        )
        page.route(
            "**/prepare",
            lambda route: _json(route, {"system_prompt": "Prepared prompt"}),
        )
        page.route(
            "**/ask_*",
            lambda route: _json(route, {"error": "provider unavailable"}, status=500),
        )
        page.fill("#questionInput", "Why did every provider fail in this test?")
        page.evaluate("() => window.sendQuestion()")

        page.wait_for_function(
            """() => {
              const run = window.App.runRegistry.visible();
              return run?.status === 'failed'
                && run.error?.message === 'All selected model requests failed.';
            }""",
            timeout=30000,
        )
        assert consensus_requests == []
    finally:
        context.close()


# Holds every /ask_* request in the page until the test releases it. Compare
# is the browser's run besides Agent since 2026-10-25: no chat, no turn, no
# /consensus; each finished answer is saved to its run's bookmark.
RUN_GATE = """() => {
  const included = new Set(["OpenAI", "Mistral"]);
  window.App.modelPrefs.forEach(pref => {
    window.App.setModelSelectionState(pref, included.has(pref.key),
      {persist: false, syncCheckbox: true, animate: false});
  });
  window.updateQuestionInputAccess?.();
  const nativeFetch = window.fetch.bind(window);
  const held = [];
  const aborted = [];
  const calls = [];
  const response = data => new Response(JSON.stringify(data), {
    status: 200, headers: {"Content-Type": "application/json"}
  });
  window.fetch = (input, options = {}) => {
    const url = new URL(String(input), window.location.href);
    if (!url.pathname.startsWith("/ask_") && url.pathname !== "/consensus") return nativeFetch(input, options);
    const body = JSON.parse(options.body || "{}");
    const kind = url.pathname === "/consensus" ? "consensus" : "ask";
    return new Promise((resolve, reject) => {
      const entry = {kind, path: url.pathname, question: body.question, body, resolve, reject, settled: false};
      held.push(entry);
      calls.push({kind, path: entry.path, question: entry.question, body});
      const abort = () => {
        if (entry.settled) return;
        entry.settled = true;
        aborted.push(`${kind}|${entry.question}|${entry.path}`);
        reject(new DOMException("Aborted", "AbortError"));
      };
      if (options.signal?.aborted) abort();
      else options.signal?.addEventListener("abort", abort, {once: true});
    });
  };
  window.__runGate = {
    pending(question) {
      return held.filter(item => !item.settled && item.question === question).length;
    },
    resolveAsks(question) {
      held.filter(item => !item.settled && item.kind === "ask" && item.question === question)
        .forEach(item => {
          item.settled = true;
          const provider = item.path.replace("/ask_", "");
          item.resolve(response({response: `${question} ${provider} answer`, sources: [],
            usage_run_status: "consumed", free_usage_remaining: 2, limit: 3, deep_limit: 0}));
        });
    },
    aborted: () => aborted.slice(),
    calls: (kind, question) => calls.filter(item =>
      (!kind || item.kind === kind) && (!question || item.question === question))
  };
  window.__runPromises = [];
}"""


def _route_compare_runs(page, bookmark_bodies):
    def prepare_route(route):
        _json(route, {"system_prompt": "Prepared multi-run prompt", "usage_run_status": "reserved",
                      "free_usage_remaining": 3, "limit": 3, "deep_limit": 0})

    def model_bookmark_route(route):
        body = json.loads(route.request.post_data or "{}")
        bookmark_bodies.append(body)
        _json(route, {"bookmark": {"id": body.get("bookmarkId") or "missing-bookmark-id",
                                   "query": body.get("question") or "", "title": body.get("question") or "",
                                   "mode": body.get("mode") or "Standard",
                                   "responses": {body.get("modelName") or "Unknown": body.get("response") or ""},
                                   "sources": [], "attachments": []}})
    page.route("**/prepare", prepare_route)
    page.route("**/bookmark", model_bookmark_route)
    page.wait_for_function("() => window.App?.runRegistry && typeof window.sendQuestion === 'function'")
    page.evaluate("() => window.App.runMode.set('compare')")
    page.evaluate(RUN_GATE)
    assert page.evaluate("() => window.App.getSelectedModelCount()") == 2


def _start_compare_run(page, question, *, new_chat=False):
    if new_chat:
        page.evaluate("() => document.getElementById('newRunButton').click()")
        page.wait_for_timeout(500)  # leave the intentional duplicate-click window
    page.evaluate(
        """question => {
          const input = document.getElementById("questionInput");
          input.value = question;
          input.dispatchEvent(new Event("input", {bubbles: true}));
          window.__runPromises.push(window.sendQuestion());
        }""",
        question,
    )
    page.wait_for_function("question => window.__runGate.pending(question) === 2", arg=question)
    return page.evaluate(
        "question => window.App.runRegistry.list().find(run => run.question === question).runId", question)


def test_two_runs_keep_payloads_views_and_cancel_controllers_isolated(
    browser, phase4_server
):
    """Reverse completion order must never mix two live RunContexts."""

    context, page = _real_firebase_page(browser, phase4_server)
    bookmark_bodies = []
    try:
        _route_compare_runs(page, bookmark_bodies)
        question_a = "Parallel isolation run A"
        question_b = "Parallel isolation run B"
        run_a = _start_compare_run(page, question_a)
        run_b = _start_compare_run(page, question_b, new_chat=True)
        assert run_a != run_b
        assert page.evaluate("() => window.App.runRegistry.activeCount()") == 2
        expect(page.locator("[data-run-id]")).to_have_count(2)
        page.evaluate("() => window.loadBookmarks()")
        expect(page.locator("[data-run-id]")).to_have_count(2)

        page.locator(f'[data-run-id="{run_a}"]').click()
        assert page.evaluate("() => window.App.runRegistry.visible().runId") == run_a
        expect(page.locator("#threadAskText")).to_have_text(question_a)
        expect(page.locator(f'[data-run-id="{run_a}"]')).to_have_attribute("role", "button")

        # B finishes in the background; A on screen shows none of it.
        page.evaluate("question => window.__runGate.resolveAsks(question)", question_b)
        page.wait_for_function("id => window.App.runRegistry.get(id).status === 'succeeded'", arg=run_b)
        expect(page.locator("#openaiResponse")).not_to_contain_text(question_b)
        expect(page.locator("#threadAskText")).to_have_text(question_a)

        # Cancelling A stops only A's requests.
        expect(page.locator("#sendButton")).to_have_attribute("aria-label", "Cancel this run")
        page.click("#sendButton")
        page.wait_for_function("id => window.App.runRegistry.get(id).status === 'canceled'", arg=run_a)
        assert page.evaluate("id => App.runRegistry.get(id).status", run_b) == "succeeded"
        assert page.evaluate("() => App.runRegistry.activeCount()") == 0
        aborted = page.evaluate("() => window.__runGate.aborted()")
        assert sorted(aborted) == [f"ask|{question_a}|/ask_mistral", f"ask|{question_a}|/ask_openai"]
        expect(page.locator(f'[data-run-id="{run_a}"]')).to_contain_text("Stopped")

        page.locator(f'[data-run-id="{run_b}"]').click()
        assert page.evaluate("() => window.App.runRegistry.visible().runId") == run_b
        expect(page.locator("#threadAskText")).to_have_text(question_b)
        expect(page.locator("#openaiResponse")).to_contain_text(f"{question_b} openai answer")
        expect(page.locator("#mistralResponse")).to_contain_text(f"{question_b} mistral answer")
        expect(page.locator("#consensusOutput")).to_be_hidden()

        # Each run asked with its own question, and nothing asked for a consensus.
        for question in (question_a, question_b):
            calls = page.evaluate("question => window.__runGate.calls('ask', question)", question)
            assert sorted(call["path"] for call in calls) == ["/ask_mistral", "/ask_openai"]
            assert all(call["body"]["run_mode"] == "compare" for call in calls)
        assert page.evaluate("() => window.__runGate.calls('consensus')") == []
        # Only B's finished answers are saved, each to B's bookmark.
        assert sorted((body["question"], body["modelName"]) for body in bookmark_bodies) == [
            (question_b, "Mistral"), (question_b, "OpenAI")]
        assert len({body["bookmarkId"] for body in bookmark_bodies}) == 1
    finally:
        context.close()


def test_two_runs_finish_reverse_order_behind_a_saved_bookmark(
    browser, phase4_server
):
    """Both runs finish and persist without replacing the saved chat view."""

    context, page = _real_firebase_page(browser, phase4_server)
    saved_id = "saved_bookmark_a"
    saved_question = "Saved bookmark A question"
    saved_consensus = "Saved bookmark A consensus"
    saved_turn = {"id": "b" * 32, "status": "completed", "position": 1, "question": saved_question,
                  "mode": "Standard", "execution_mode": "consensus", "consensus": saved_consensus,
                  "sources": [], "model_answers": {
                      "OpenAI": {"provider": "OpenAI", "model_label": "Saved OpenAI", "answer": "Saved bookmark A OpenAI answer"},
                      "Mistral": {"provider": "Mistral", "model_label": "Saved Mistral", "answer": "Saved bookmark A Mistral answer"}}}
    saved_bookmark = {"id": saved_id, "query": saved_question, "title": "Saved bookmark A", "mode": "Standard",
                      "chat_id": "a" * 32, "responses": {"consensus": saved_consensus}}
    bookmark_bodies = []
    try:
        page.route(f"**/bookmarks/{saved_id}/conversation*",
                   lambda route: _json(route, {"chat_id": "a" * 32, "turns": [saved_turn], "has_more": False}))
        page.route(f"**/bookmarks/{saved_id}", lambda route: _json(route, {"bookmark": saved_bookmark}))
        _route_compare_runs(page, bookmark_bodies)
        question_a = "Reverse order run A"
        question_b = "Reverse order run B"
        run_a = _start_compare_run(page, question_a)
        run_b = _start_compare_run(page, question_b, new_chat=True)

        page.evaluate("id => window.openBookmark(id)", saved_id)
        expect(page.locator("#threadAskText")).to_have_text(saved_question)
        expect(page.locator("#consensusAnswerBody")).to_contain_text(saved_consensus)
        assert page.evaluate("() => window.App.runRegistry.visible()") is None

        # B first, then A: both finish in the background.
        page.evaluate("question => window.__runGate.resolveAsks(question)", question_b)
        page.wait_for_function("id => window.App.runRegistry.get(id).status === 'succeeded'", arg=run_b)
        page.evaluate("question => window.__runGate.resolveAsks(question)", question_a)
        page.wait_for_function("id => window.App.runRegistry.get(id).status === 'succeeded'", arg=run_a)

        # The saved chat stays as it was.
        assert page.evaluate("() => window.App.runRegistry.visible()") is None
        expect(page.locator("#threadAskText")).to_have_text(saved_question)
        expect(page.locator("#consensusAnswerBody")).to_contain_text(saved_consensus)
        expect(page.locator("#openaiResponse .collapsible-content")).to_contain_text("Saved bookmark A OpenAI answer")
        expect(page.locator("#runProvenance")).to_be_visible()

        # Each run saved its own answers to its own bookmark.
        page.wait_for_function("() => window.App.runRegistry.list().every(run => run.persistence.pendingWrites === 0)")
        saved = sorted((body["question"], body["modelName"]) for body in bookmark_bodies)
        assert saved == [(question_a, "Mistral"), (question_a, "OpenAI"),
                         (question_b, "Mistral"), (question_b, "OpenAI")]
        by_question = {}
        for body in bookmark_bodies:
            by_question.setdefault(body["question"], set()).add(body["bookmarkId"])
        assert all(len(ids) == 1 for ids in by_question.values())
        assert by_question[question_a] != by_question[question_b]
        assert saved_id not in by_question[question_a] | by_question[question_b]

        page.locator(f'[data-run-id="{run_a}"]').click()
        expect(page.locator("#threadAskText")).to_have_text(question_a)
        expect(page.locator("#openaiResponse")).to_contain_text(f"{question_a} openai answer")
        expect(page.locator("#consensusOutput")).to_be_hidden()
        expect(page.locator("#threadHistory .thread-history-turn")).to_have_count(0)
    finally:
        context.close()


def test_compare_is_six_answers_only(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    model_bookmark_bodies = []
    bookmark_responses = {}
    bookmark_labels = {}
    saved_bookmark = {}

    def model_bookmark_route(route):
        body = json.loads(route.request.post_data or "{}")
        model_bookmark_bodies.append(body)
        bookmark_responses[body["modelName"]] = body["response"]
        bookmark_labels[body["modelName"]] = body.get("modelLabel")
        saved_bookmark.update({
            "id": body.get("bookmarkId") or "direct-comparison-bookmark",
            "query": body["question"],
            "title": body["question"],
            "mode": body.get("mode") or "Standard",
            "responses": dict(bookmark_responses),
            "model_labels": dict(bookmark_labels),
            "sources": body.get("sources") or [],
            "attachments": body.get("attachments") or [],
        })
        _json(route, {"bookmark": saved_bookmark})

    try:
        consensus_requests = []
        page.on(
            "request",
            lambda request: consensus_requests.append(request.url)
            if request.url.endswith("/consensus") else None,
        )
        page.route(
            "**/prepare",
            lambda route: _json(route, {"system_prompt": "Prepared prompt"}),
        )
        page.route(
            "**/ask_*",
            lambda route: _json(route, {
                "response": "Direct answer from " + route.request.url.rsplit("_", 1)[-1],
                "answer_receipt": "receipt:" + route.request.url.rsplit("_", 1)[-1],
                "sources": [],
            }),
        )
        page.route("**/bookmark", model_bookmark_route)
        mode = page.locator("#runModeSelect")
        # Without Agent access an account starts in Compare.
        expect(mode).to_have_value("compare")
        page.locator("#attachTrigger").click()
        page.locator('#runModeControl [data-value="compare"]').click()
        expect(mode).to_have_value("compare")
        expect(page.locator("#runModeSetting")).to_have_value("compare")
        page.fill("#questionInput", "Give me six direct answers only.")
        page.evaluate("() => window.sendQuestion()")

        for response_id in (
            "openaiResponse", "mistralResponse", "claudeResponse",
            "geminiResponse", "deepseekResponse", "grokResponse",
        ):
            expect(page.locator(f"#{response_id}")).to_contain_text(
                "Direct answer from", timeout=10000
            )
            provider = page.locator(f"#{response_id}").get_attribute('data-model')
            answer = page.locator(f'.is-direct .answer-reader-body[data-provider="{provider}"]')
            expect(answer).to_be_visible()
            expect(answer).to_contain_text('Direct answer from')

        page.wait_for_function(
            "() => {"
            " const run = window.App.runRegistry.visible();"
            " return run?.status === 'succeeded'"
            "   && run.persistence.pendingWrites === 0;"
            "}"
        )
        assert consensus_requests == []
        assert {body["modelName"] for body in model_bookmark_bodies} == {
            "OpenAI", "Mistral", "Anthropic", "Gemini", "DeepSeek", "Grok",
        }
        assert all(
            body["question"] == "Give me six direct answers only."
            for body in model_bookmark_bodies
        )
        assert page.locator("body").evaluate(
            "el => !el.classList.contains('is-hero')"
            " && el.classList.contains('direct-comparison-active')"
            " && !el.classList.contains('agent-mode-enabled')"
        )
        # Direct comparison still has no consensus pipeline, but since the
        # 2026-08-31 thread contract it keeps the submitted question visible.
        expect(page.locator("#threadAsk")).to_be_visible()
        expect(page.locator("#threadAskText")).to_contain_text(
            "Give me six direct answers only."
        )
        expect(page.locator("#consensusRun")).to_have_count(0)
        expect(page.locator("#consensusOutput")).to_be_hidden()
        expect(page.locator("#consensusAnswerBody .cx-claim")).to_have_count(0)
        expect(page.locator("#differencesCards")).to_be_hidden()
        # The Compare run itself records that no consensus was asked for.
        assert page.evaluate("App.runRegistry.visible().config.autoConsensus") is False
        expected_labels = page.evaluate("""() => Object.fromEntries(
            App.runRegistry.visible().config.providers.map(p => [p.provider, p.modelLabel]))""")
        assert bookmark_labels == expected_labels
        assert all(label and label != provider for provider, label in bookmark_labels.items())
        page.route(f"**/bookmarks/{saved_bookmark['id']}",
                   lambda route: _json(route, {"bookmark": saved_bookmark}))
        # A choice for the next run must never replace saved answer provenance.
        page.evaluate("""() => App.modelPrefs.forEach(pref => {
            document.getElementById(pref.textId).textContent = 'Different next-run model';
            const select = document.getElementById(pref.selectId);
            select.selectedIndex = select.options.length - 1;
        })""")
        page.evaluate("id => window.openBookmark(id)", saved_bookmark["id"])
        for provider, label in expected_labels.items():
            caption = page.locator('.answer-reader-answer').filter(
                has=page.locator(f'.answer-reader-body[data-provider="{provider}"]')
            ).locator('.answer-reader-caption')
            expect(caption).to_be_visible()
            expect(caption).to_have_text(label)
    finally:
        context.close()


def test_attachment_filter_blocks_one_model_run_before_prepare(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        requests = []
        page.on(
            "request",
            lambda request: requests.append(request.url)
            if any(part in request.url for part in ("/prepare", "/ask_")) else None,
        )
        page.evaluate(
            """() => {
              // Attachments are Plus/Pro-gated independently from the
              // isUserPro frontier-model flag.
              window.App.state.set("isUserPro", true, "userTier");
              window.App.state.set("isUserPlus", true, "userTier");
              for (const id of [
                "selectOpenAI", "selectMistral", "selectClaude",
                "selectGemini", "selectDeepSeek", "selectGrok"
              ]) document.getElementById(id).checked = false;
              document.getElementById("selectOpenAI").checked = true;
              document.getElementById("selectDeepSeek").checked = true;
              window.pendingAttachments = [{
                name: "brief.pdf", mime: "application/pdf", size: 9, data: "JVBERi0xLjcK"
              }];
              window.renderAttachmentChips();
              // Simulate stale external state after the attachment renderer disabled it.
              document.getElementById("selectDeepSeek").checked = true;
            }"""
        )
        page.fill("#questionInput", "Can this filtered run start?")
        page.evaluate("() => window.sendQuestion()")

        expect(page.locator("#appToasts .toast")).to_contain_text(
            "Choose at least two compatible models"
        )
        assert requests == []
    finally:
        context.close()


def test_watched_navigation_closes_the_shared_modal(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.route(
            "**/api/my/watches",
            lambda route: _json(route, {
                "watches": [],
                "limits": {"plan": "free", "active_count": 0, "active_limit": 1},
            }),
        )
        page.route("**/api/my/watch-brief", lambda route: _json(route, {"brief": {}}))
        page.route("**/api/my/telegram", lambda route: _json(route, {"telegram": {}}))

        page.evaluate(
            "() => { window.App.state.set('lastShareResultId', 'phase4-result', 'share'); window.openShareDialog('confirm'); }"
        )
        expect(page.locator("#shareModal")).to_be_visible()
        page.click("#watchListLink")

        expect(page.locator("#shareModal")).to_be_hidden()
        expect(page.locator("#watchDashboard")).to_be_visible()
        assert page.url.endswith("/app/watches")
    finally:
        context.close()


def test_cancel_during_token_resolution_gives_the_question_back_and_creates_no_usage_run(
    browser, phase4_server
):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.evaluate(
            """() => {
              document.getElementById("selectOpenAI").checked = true;
              document.getElementById("selectMistral").checked = true;
              document.getElementById("questionInput").value = "What changed since yesterday?";
              window.App.runMode.set('compare');
              let release;
              const pending = new Promise(resolve => { release = resolve; });
              window.auth.currentUser.getIdToken = () => pending;
              window.__releaseSlowToken = () => release("token-account-a");
              window.__slowSend = window.sendQuestion();
              window.__slowSend.then(() => { window.__slowSendDone = true; });
            }"""
        )
        page.wait_for_function("() => window.isQueryRequestRunning() === true")
        page.evaluate("() => window.cancelCurrentQuery()")
        page.evaluate("() => window.__releaseSlowToken()")
        page.wait_for_function("() => window.__slowSendDone === true")

        # Nothing went out: no usage run, nothing running, the question is
        # back in the field.
        assert page.evaluate("() => window.App.usageRun?.current?.key || null") is None
        assert page.evaluate("() => window.isQueryRequestRunning()") is False
        expect(page.locator("#questionInput")).to_have_value("What changed since yesterday?")
    finally:
        context.close()


def test_late_watch_create_cannot_overwrite_newer_share_modal(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.route(
            "**/api/my/watches",
            lambda route: _json(route, {
                "watches": [],
                "limits": {"plan": "free", "active_count": 0, "active_limit": 5},
            }),
        )
        page.route("**/api/my/telegram", lambda route: _json(route, {"telegram": {}}))
        page.evaluate(
            """() => {
              const nativeFetch = window.fetch.bind(window);
              window.fetch = (input, options = {}) => {
                if (String(input) === "/api/watch" && options.method === "POST") {
                  return new Promise(resolve => {
                    window.__resolveWatchCreate = () => resolve(new Response(JSON.stringify({
                      watch: {
                        id: "watch-race", interval: "weekly", run_weekday: "monday",
                        run_time: "09:00", timezone: "Europe/Berlin", query_first: true,
                        share_path: "/s/watch-race", visibility: "private",
                        email_mode: "changes_only", email_enabled: true,
                        telegram_enabled: false
                      }
                    }), { status: 200, headers: { "Content-Type": "application/json" } }));
                  });
                }
                return nativeFetch(input, options);
              };
              window.openWatchDialog("create", {
                question: "Has this policy changed since last week?"
              });
            }"""
        )
        page.click("#watchConfirmBtn")
        page.wait_for_function("() => typeof window.__resolveWatchCreate === 'function'")

        page.evaluate("() => window.openShareDialog('confirm')")
        expect(page.locator("#shareModalTitle")).to_have_text(
            "Share this answer publicly"
        )
        page.evaluate("() => window.__resolveWatchCreate()")
        page.wait_for_timeout(150)

        expect(page.locator("#shareModalTitle")).to_have_text(
            "Share this answer publicly"
        )
        expect(page.locator("#shareModalBody")).not_to_contain_text(
            "Your Watch is active"
        )
    finally:
        context.close()


def test_watch_create_is_not_sent_after_modal_changes_during_token_wait(
    browser, phase4_server
):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.route(
            "**/api/my/watches",
            lambda route: _json(route, {
                "watches": [],
                "limits": {"plan": "free", "active_count": 0, "active_limit": 5},
            }),
        )
        page.route("**/api/my/telegram", lambda route: _json(route, {"telegram": {}}))
        page.evaluate(
            """() => window.openWatchDialog("create", {
              question: "Has this policy changed since last week?"
            })"""
        )
        page.wait_for_selector("#watchConfirmBtn")
        page.evaluate(
            """() => {
              let release;
              const pending = new Promise(resolve => { release = resolve; });
              window.auth.currentUser.getIdToken = () => pending;
              window.__releaseWatchToken = () => release("token-account-a");
              window.__watchPostSent = false;
              const nativeFetch = window.fetch.bind(window);
              window.fetch = (input, options = {}) => {
                if (String(input) === "/api/watch" && options.method === "POST") {
                  window.__watchPostSent = true;
                }
                return nativeFetch(input, options);
              };
            }"""
        )
        page.click("#watchConfirmBtn")
        page.evaluate("() => window.openShareDialog('confirm')")
        page.evaluate("() => window.__releaseWatchToken()")
        page.wait_for_timeout(100)

        assert page.evaluate("() => window.__watchPostSent") is False
        expect(page.locator("#shareModalTitle")).to_have_text(
            "Share this answer publicly"
        )
    finally:
        context.close()


def test_failed_utc_usage_refresh_retries_until_authoritative_success(
    browser, phase4_server
):
    context, page = _real_firebase_page(
        browser,
        phase4_server,
        init_script="window.USAGE_REFRESH_RETRY_MS = 25;",
    )
    try:
        page.evaluate(
            """() => {
              window.App.renderUsageDisplay({
                remaining: 0, deepRemaining: 0, totalLimit: 3, deepLimit: 0
              });
              window.__usageRefreshCalls = 0;
              window.refreshUsageData = async () => {
                window.__usageRefreshCalls += 1;
                if (window.__usageRefreshCalls === 1) return false;
                window.App.renderUsageDisplay({
                  remaining: 3, deepRemaining: 0, totalLimit: 3, deepLimit: 0
                });
                return true;
              };

              const OriginalDate = window.Date;
              const realStartedAt = OriginalDate.now();
              const today = new OriginalDate();
              const fakeStartedAt = OriginalDate.UTC(
                today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate() + 1,
                0, 0, 1
              );
              class NextUtcDayDate extends OriginalDate {
                constructor(...args) {
                  super(...(args.length
                    ? args
                    : [fakeStartedAt + (OriginalDate.now() - realStartedAt)]));
                }
                static now() {
                  return fakeStartedAt + (OriginalDate.now() - realStartedAt);
                }
                static UTC(...args) { return OriginalDate.UTC(...args); }
                static parse(value) { return OriginalDate.parse(value); }
              }
              window.Date = NextUtcDayDate;
            }"""
        )

        page.wait_for_function("() => window.__usageRefreshCalls >= 2", timeout=5000)
        assert page.evaluate(
            "() => window.App.usageLimit.preflight({ useOwnKeys: false })"
        ) is None
    finally:
        context.close()


def test_template_visibility_classes_remain_overridable_by_ui_controls(
    browser, phase4_server
):
    context, page = _real_firebase_page(
        browser, phase4_server, initial_uid=None
    )
    try:
        page.click("#authTopSignupBtn")
        expect(page.locator("#loginModal")).to_be_visible()
        expect(page.locator("#authTabRegister")).to_have_attribute("aria-selected", "true")
        expect(page.locator("#loginPassword")).to_be_hidden()
        expect(page.locator("#forgotPasswordButton")).to_be_hidden()
        expect(page.locator("#confirmRegisterButton")).to_be_visible()
        expect(page.locator("#singleMailNote")).to_be_visible()

        page.click("#authTabLogin")
        expect(page.locator("#loginPassword")).to_be_visible()
        expect(page.locator("#forgotPasswordButton")).to_be_visible()
        expect(page.locator("#confirmRegisterButton")).to_be_hidden()
        expect(page.locator("#singleMailNote")).to_be_hidden()
        page.click("#closeLoginModal")

        page.evaluate("() => document.getElementById('editSystemPromptBtn').click()")
        expect(page.locator("#systemPromptModal")).to_be_visible()
        page.click("#closeSystemPromptModal")
        expect(page.locator("#systemPromptModal")).to_be_hidden()

        page.evaluate("() => document.getElementById('editSystemPromptBtn').click()")
        page.click("#settingsTabConnections")
        expect(page.locator("#apiSettingsArea")).to_be_hidden()
        page.evaluate("() => document.getElementById('apiSettingsToggle').click()")
        expect(page.locator("#apiSettingsArea")).to_be_visible()
    finally:
        context.close()


def test_key_claim_fallback_cleans_orphan_markdown_and_renders_math(
    browser, phase4_server
):
    """Legacy-Anker mit einem Split in **fett** bleiben lesbar; LaTeX nutzt
    auch in der Fallback-Liste denselben KaTeX-Pfad wie der Konsenstext."""
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({"width": 390, "height": 844})
        page.evaluate(
            """(anchors) => {
              // Der browser-only Lauf laedt bewusst keine externen CDN-Skripte.
              // Der Stub prueft deterministisch, dass der echte gemeinsame
              // ConsensusMath-Pfad das vorbereitete Inline-LaTeX weiterreicht.
              window.__claimMathInputs = [];
              window.marked = {
                parseInline: (source) => {
                  if (source === "**40 Mrd. $ ARR**") return "<strong>40 Mrd. $ ARR</strong>";
                  if (source.includes("literal")) return "**literal**";
                  if (source === "`value ** 2`") return "<code>value ** 2</code>";
                  if (source.startsWith("Die **mehr als")) {
                    return "Die <strong>mehr als 40 Mrd. $ ARR</strong> sind das annualisierte aktuelle Umsatztempo im spaeteren Zeitraum.";
                  }
                  if (source.includes("approx")) return anchors.math;
                  return source;
                }
              };
              window.DOMPurify = {sanitize: (html) => html};
              window.renderMathInElement = (root) => {
                window.__claimMathInputs.push(root.textContent);
                if (!root.textContent.includes("\\(")) return;
                const rendered = document.createElement("span");
                rendered.className = "katex";
                rendered.textContent = "17,5 %";
                root.replaceChildren(rendered);
              };
              window.revealConsensusOutput?.();
              document.getElementById("consensusAnswerBody").innerHTML =
                "<p>Something else entirely.</p>";
              window.renderConsensusInsights({
                claims: [
                  {anchor: anchors.validBold, agree: [{model: "OpenAI"}], dissent: []},
                  {anchor: anchors.markdown, agree: [{model: "OpenAI"}], dissent: []},
                  {anchor: anchors.escapedStars, agree: [{model: "OpenAI"}], dissent: []},
                  {anchor: anchors.code, agree: [{model: "OpenAI"}], dissent: []},
                  {anchor: anchors.literalStar, agree: [{model: "OpenAI"}], dissent: []},
                  {anchor: anchors.longText, agree: [{model: "OpenAI"}], dissent: []},
                  {anchor: anchors.math, agree: [{model: "OpenAI"}], dissent: []}
                ],
                differences: [],
                models_compared: ["OpenAI"]
              }, 1);
            }""",
            {
                "validBold": "**40 Mrd. $ ARR**",
                "markdown": "$ in Q1** gegenueber **6,7 Mrd.",
                "escapedStars": r"\*\*literal\*\*",
                "code": "`value ** 2`",
                "literalStar": "Preis * Menge = Umsatz",
                "longText": (
                    "Die **mehr als 40 Mrd. $ ARR** sind das annualisierte "
                    "aktuelle Umsatztempo im spaeteren Zeitraum."
                ),
                "math": r"\(\frac{6{,}7}{5{,}7} - 1 \approx 17{,}5\%\)",
            },
        )

        fallback = page.locator("#consensusClaimsFallback")
        rows = fallback.locator(".claims-fallback-row")
        expect(rows).to_have_count(7)
        expect(rows.nth(0).locator("strong")).to_have_text("40 Mrd. $ ARR")
        assert "**" not in rows.nth(1).inner_text()
        expect(rows.nth(2).locator(".claims-fallback-text")).to_have_text("**literal**")
        expect(rows.nth(3).locator("code")).to_have_text("value ** 2")
        expect(rows.nth(4).locator(".claims-fallback-text")).to_have_text(
            "Preis * Menge = Umsatz"
        )
        expect(rows.nth(5).locator("strong")).to_have_text("mehr als 40 Mrd. $ ARR")
        assert page.evaluate("() => window.__claimMathInputs.at(-1)") == (
            r"\(\frac{6{,}7}{5{,}7} - 1 \approx 17{,}5\%\)"
        )
        expect(
            rows.nth(6).locator(".katex")
        ).to_have_count(1)
        assert r"\approx" not in fallback.inner_text()
        layout = page.evaluate(
            """() => {
              const box = document.getElementById("consensusClaimsFallback");
              const bounds = box.getBoundingClientRect();
              return {
                scrollWidth: box.scrollWidth,
                clientWidth: box.clientWidth,
                badgesInside: Array.from(box.querySelectorAll(".claim-badge"))
                  .every(badge => badge.getBoundingClientRect().right <= bounds.right + 1)
              };
            }"""
        )
        assert layout["scrollWidth"] <= layout["clientWidth"] + 1
        assert layout["badgesInside"] is True

        # Derselbe sichtbare Schutz greift auch dann, wenn marked/DOMPurify
        # nicht vom CDN geladen werden konnten.
        page.evaluate(
            """(anchors) => {
              window.marked = undefined;
              window.DOMPurify = undefined;
              window.renderConsensusInsights({
                claims: [
                  {anchor: anchors.markdown, agree: [{model: "OpenAI"}], dissent: []},
                  {anchor: anchors.math, agree: [{model: "OpenAI"}], dissent: []}
                ],
                differences: [],
                models_compared: ["OpenAI"]
              }, 1);
            }""",
            {
                "markdown": "$ in Q1** gegenueber **6,7 Mrd.",
                "math": r"\(\frac{6{,}7}{5{,}7} - 1 \approx 17{,}5\%\)",
            },
        )
        rows = fallback.locator(".claims-fallback-row")
        expect(rows).to_have_count(2)
        assert "**" not in rows.nth(0).inner_text()
        expect(rows.nth(1).locator(".katex")).to_have_count(1)
    finally:
        context.close()
