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
    browser, app_server, initial_uid="account-a", path="/app", init_script=None, *, has_touch=False
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
    page.goto(app_server + path, wait_until="domcontentloaded")
    page.wait_for_function(
        "() => window.__consensioAuthState?.known === true"
        " && typeof window.openShareDialog === 'function'"
    )
    return context, page


def test_followup_stream_preserves_history_and_model_loading_nodes(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.evaluate('''() => {
          const registry = window.App.runRegistry;
          const run = registry.create({question:'Second question', config:{agentMode:true,
            providers:[{provider:'OpenAI',modelLabel:'OpenAI'}, {provider:'Gemini',modelLabel:'Gemini'}]}});
          run.historyTurns.push({turn_id:'first',question:'First question',
            consensus:'A completed answer with **Markdown** and a source. [S1]',
            differences:'A completed comparison.', sources:[{id:'S1',url:'https://example.com',title:'Source'}]});
          run.modelResults = {OpenAI:{status:'streaming',streamText:'A new answer'}, Gemini:{status:'pending'}};
          run.phase = 'answers';
          registry.setStatus(run.runId,'running');
          window.__followupRun = run;
          window.__followupHistory = document.querySelector('.thread-history-turn');
          window.__followupSpinner = document.querySelector('#geminiResponse .thinking-wrap');
          window.__followupBar = document.querySelector('#runDetail [data-box="openaiResponse"] i');
          window.__followupHistoryMutations = 0;
          new MutationObserver(records => { window.__followupHistoryMutations += records.length; })
            .observe(document.getElementById('threadHistory'), {childList:true,subtree:true});
        }''')
        expect(page.locator('#runDetail')).to_be_visible()
        assert page.evaluate('Boolean(window.__followupSpinner && window.__followupBar)')
        page.evaluate('''async () => {
          for (let i = 0; i < 12; i++) {
            window.__followupRun.modelResults.OpenAI.streamText += ' another token';
            window.App.runRegistry.renderVisible();
            await new Promise(resolve => setTimeout(resolve, 120));
          }
        }''')
        assert page.evaluate('''() => window.__followupHistory === document.querySelector('.thread-history-turn')
          && window.__followupSpinner === document.querySelector('#geminiResponse .thinking-wrap')
          && window.__followupBar === document.querySelector('#runDetail [data-box="openaiResponse"] i')
          && window.__followupHistoryMutations === 0''')
        assert page.evaluate("parseFloat(window.__followupBar.style.getPropertyValue('--p')) > 12")
        expect(page.locator('#openaiResponse .collapsible-content')).to_contain_text('another token')
    finally:
        context.close()


def test_consensus_stream_keeps_claims_and_cards_through_the_final_frame(browser, phase4_server):
    """Claims and difference cards survive the final (replayed) frame, and new
    consensus prose never turns a numeric [1] into a citation."""
    context, page = _real_firebase_page(browser, phase4_server,
        init_script="localStorage.setItem('consensio.consensusHighlightMode.v1','all')")
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        # Raw: the SSE frame's "\n" must reach JavaScript as an escape.
        page.evaluate(r"""() => {
          const registry=App.runRegistry;
          const source={id:'S1',url:'https://example.invalid/prices',title:'Original source'};
          const run=registry.create({question:'What does the plan cost?',config:{agentMode:true,
            consensusModel:'Gemini',providers:[{provider:'OpenAI',modelLabel:'OpenAI'},{provider:'Gemini',modelLabel:'Gemini'}]}});
          run.chatSession=null;run.evidenceSources=[source];
          run.modelResults={OpenAI:{status:'complete',text:'20 euros [S1]',sources:[source]},Gemini:{status:'complete',text:'30 euros [S1]',sources:[source]}};
          registry.setStatus(run.runId,'running');window.__streamRun=run;
          window.__streamText='The plan costs 20 euros. The list contains [1]. Both models describe a monthly subscription.';
          window.__streamDifferences={models_compared:['OpenAI','Gemini'],claims:[{anchor:'Both models describe a monthly subscription.',agree:['OpenAI','Gemini'],dissent:[],coverage:'supported'}],differences:[
            {claim:'The plan price',consensus_anchor:'The plan costs 20 euros.',type:'contradiction',severity:'major',positions:[
              {models:['OpenAI'],stance:'20 euros',quote:'20 euros'},{models:['Gemini'],stance:'30 euros',quote:'30 euros'}]},
            {claim:'Different emphasis',type:'emphasis',positions:[{models:['OpenAI'],stance:'Cost focus'},{models:['Gemini'],stance:'Flexibility focus'}]}]};
          const originalFetch=window.fetch;
          window.fetch=(url,options)=>{
            if(url!=='/consensus') return originalFetch(url,options);
            window.__streamPayload=JSON.parse(options.body);
            return Promise.resolve(new Response(new ReadableStream({start(controller){window.__stream=controller;}}),{headers:{'content-type':'text/event-stream'}}));
          };
          window.__streamSend=(name,data)=>window.__stream.enqueue(new TextEncoder().encode('event: '+name+'\ndata: '+JSON.stringify(data)+'\n\n'));
          window.__streamCompletion=App.executeConsensusRun(run);
        }""")
        page.wait_for_function('Boolean(window.__stream)')
        # The contradiction source check is gone: the request no longer asks for it.
        assert page.evaluate("'check_sources' in window.__streamPayload") is False
        page.evaluate("""() => {
          __streamSend('consensus.final',{text:__streamText});
          __streamSend('differences.final',{differences:'Price disagreement and different emphasis.',differences_data:__streamDifferences});
        }""")
        expect(page.locator('#consensusAnswerBody .cx-claim')).to_have_count(2)
        expect(page.locator('.diff-card')).to_have_count(2)
        expect(page.locator('#consensusAnswerBody .src-ref')).to_have_count(0)
        expect(page.locator('#consensusAnswerBody')).to_contain_text('[1]')
        page.evaluate("""() => {
          window.__streamClaim=document.querySelector('#consensusAnswerBody .cx-claim');
          window.__streamCards=[...document.querySelectorAll('.diff-card')];
          // A replay carries the authoritative saved answers; it must not
          // borrow model text from the local pre-recovery projection.
          const model_answers=Object.fromEntries(Object.entries(__streamRun.modelResults).map(([provider,result])=>[
            provider,{answer:result.text,model_label:provider,sources:result.sources}
          ]));
          __streamSend('final',{consensus_response:__streamText,differences:'Price disagreement and different emphasis.',differences_data:__streamDifferences,model_answers,chat_replayed:true});
          __stream.close();
        }""")
        page.wait_for_function("window.__streamRun.status === 'succeeded'")
        assert page.evaluate("__streamClaim===document.querySelector('#consensusAnswerBody .cx-claim') && __streamCards.every((card,index)=>card===document.querySelectorAll('.diff-card')[index])")
        assert page.evaluate("__streamRun.modelResults.OpenAI.text") == '20 euros [S1]'
        expect(page.locator('#consensusAnswerBody .src-ref')).to_have_count(0)
        assert not errors
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
        expect(page.locator("#loginError")).to_contain_text("temporarily unavailable")
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
              window.App.consensusPipeline.onConsensusEnd();
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
        expect(page.locator(".explanation-popup")).to_have_count(0)
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

        expect(page.locator("#watchDashBody")).to_contain_text(
            "Please log in to see your Consensus Watch dashboard."
        )
        assert page.url.endswith("/app/watches")

        page.evaluate("() => window.__switchE2EUser('account-b')")
        expect(page.locator("#watchDashCreate")).to_be_visible(timeout=5000)
        expect(page.locator("#watchDashBody")).to_contain_text("Tell us what you are waiting for.")
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


def test_two_runs_keep_payloads_views_and_cancel_controllers_isolated(
    browser, phase4_server
):
    """Reverse completion order must never mix two live RunContexts."""

    context, page = _real_firebase_page(browser, phase4_server)
    bookmark_state = {}
    consensus_bookmark_bodies = []
    chat_counter = 0
    turn_counter = 100

    def bookmark_document(body, consensus=False):
        bookmark_id = body.get("bookmarkId") or "missing-bookmark-id"
        state = bookmark_state.setdefault(bookmark_id, {
            "responses": {},
            "sources": [],
            "attachments": [],
        })
        if consensus:
            state["responses"].update(body.get("modelResponses") or {})
            state["responses"]["consensus"] = body.get("consensusText") or ""
            state["responses"]["differences"] = body.get("differencesText") or ""
            state["responses"]["differences_data"] = body.get("differencesData")
            state["sources"] = body.get("sources") or []
        else:
            state["responses"][body.get("modelName") or "Unknown"] = (
                body.get("response") or ""
            )
            state["sources"] = body.get("sources") or state["sources"]
            state["attachments"] = body.get("attachments") or state["attachments"]
        return {
            "id": bookmark_id,
            "query": body.get("question") or "",
            "title": body.get("question") or "",
            "mode": body.get("mode") or "Standard",
            "responses": dict(state["responses"]),
            "sources": list(state["sources"]),
            "attachments": list(state["attachments"]),
            "chat_id": body.get("chatId"),
            "turn_id": body.get("turnId"),
            "consensus_model": body.get("consensusModel") or "",
            "model_labels": body.get("modelLabels") or {},
        }

    def prepare_route(route):
        _json(route, {
            "system_prompt": "Prepared multi-run prompt",
            "usage_run_status": "reserved",
            "free_usage_remaining": 3,
            "limit": 3,
            "deep_limit": 0,
        })

    def create_chat_route(route):
        nonlocal chat_counter
        chat_counter += 1
        _json(route, {"chat": {"id": f"{chat_counter:032x}"}})

    def create_turn_route(route):
        nonlocal turn_counter
        turn_counter += 1
        _json(route, {"turn": {"id": f"{turn_counter:032x}", "status": "pending"}})

    def model_bookmark_route(route):
        body = json.loads(route.request.post_data or "{}")
        _json(route, {"bookmark": bookmark_document(body)})

    def consensus_bookmark_route(route):
        body = json.loads(route.request.post_data or "{}")
        consensus_bookmark_bodies.append(body)
        _json(route, {"bookmark": bookmark_document(body, consensus=True)})

    try:
        page.route("**/prepare", prepare_route)
        page.route("**/chats", create_chat_route)
        page.route("**/chats/*/turns", create_turn_route)
        page.route("**/bookmark", model_bookmark_route)
        page.route("**/bookmark/consensus", consensus_bookmark_route)

        page.wait_for_function(
            "() => window.App?.runRegistry"
            " && typeof window.sendQuestion === 'function'"
            " && typeof window.App.executeConsensusRun === 'function'"
        )
        page.evaluate(
            """() => {
              window.App.runMode.set('consensus');
              const included = new Set(["OpenAI", "Mistral"]);
              window.App.modelPrefs.forEach(pref => {
                window.App.setModelSelectionState(
                  pref,
                  included.has(pref.key),
                  {persist: false, syncCheckbox: true, animate: false}
                );
              });
              window.updateQuestionInputAccess?.();

              const nativeFetch = window.fetch.bind(window);
              const held = [];
              const aborted = [];
              const calls = [];
              const response = data => new Response(JSON.stringify(data), {
                status: 200,
                headers: {"Content-Type": "application/json"}
              });
              window.fetch = (input, options = {}) => {
                const url = new URL(String(input), window.location.href);
                const isAsk = url.pathname.startsWith("/ask_");
                const isConsensus = url.pathname === "/consensus";
                if (!isAsk && !isConsensus) return nativeFetch(input, options);
                const body = JSON.parse(options.body || "{}");
                const kind = isConsensus ? "consensus" : "ask";
                return new Promise((resolve, reject) => {
                  const entry = {
                    kind,
                    path: url.pathname,
                    question: body.question,
                    body,
                    resolve,
                    reject,
                    settled: false
                  };
                  held.push(entry);
                  calls.push({kind, path: entry.path, question: entry.question, body});
                  const abort = () => {
                    if (entry.settled) return;
                    entry.settled = true;
                    aborted.push(`${kind}|${entry.question}`);
                    reject(new DOMException("Aborted", "AbortError"));
                  };
                  if (options.signal?.aborted) abort();
                  else options.signal?.addEventListener("abort", abort, {once: true});
                });
              };
              window.__runGate = {
                pending(kind, question) {
                  return held.filter(item => !item.settled
                    && item.kind === kind && item.question === question).length;
                },
                resolveAsks(question) {
                  held.filter(item => !item.settled
                    && item.kind === "ask" && item.question === question)
                    .forEach(item => {
                      item.settled = true;
                      const provider = item.path.replace("/ask_", "");
                      item.resolve(response({
                        response: `${question} ${provider} answer`,
                        answer_receipt: `receipt:${question}:${provider}`,
                        sources: [],
                        usage_run_status: "consumed",
                        free_usage_remaining: 2,
                        limit: 3,
                        deep_limit: 0
                      }));
                    });
                },
                resolveConsensus(question) {
                  held.filter(item => !item.settled
                    && item.kind === "consensus" && item.question === question)
                    .forEach(item => {
                      item.settled = true;
                      item.resolve(response({
                        consensus_response: `Consensus for ${question}`,
                        differences: `Differences for ${question}`,
                        differences_data: null,
                        sources: [],
                        result_id: question.endsWith("B") ? "result-b" : "result-a",
                        chat_id: item.body.chat_id,
                        turn_id: item.body.turn_id,
                        chat_persisted: true,
                        chat_turn_state: "completed",
                        usage_run_status: "consumed",
                        free_usage_remaining: 1,
                        limit: 3,
                        deep_limit: 0
                      }));
                    });
                },
                aborted: () => aborted.slice(),
                calls: (kind, question) => calls.filter(item =>
                  (!kind || item.kind === kind) && (!question || item.question === question))
              };
              window.__runPromises = [];
            }"""
        )
        assert page.evaluate("() => window.App.getSelectedModelCount()") == 2

        question_a = "Parallel isolation run A"
        question_b = "Parallel isolation run B"

        page.evaluate(
            """question => {
              document.getElementById("questionInput").value = question;
              window.__runPromises.push(window.sendQuestion());
            }""",
            question_a,
        )
        page.wait_for_function(
            "question => window.__runGate.pending('ask', question) === 2",
            arg=question_a,
        )
        run_a = page.evaluate(
            "question => window.App.runRegistry.list()"
            ".find(run => run.question === question).runId",
            question_a,
        )

        page.evaluate("() => document.getElementById('newRunButton').click()")
        page.wait_for_timeout(500)  # leave the intentional duplicate-click window
        page.evaluate(
            """question => {
              const input = document.getElementById("questionInput");
              input.value = question;
              input.dispatchEvent(new Event("input", {bubbles: true}));
              window.__runPromises.push(window.sendQuestion());
            }""",
            question_b,
        )
        page.wait_for_function(
            "question => window.__runGate.pending('ask', question) === 2",
            arg=question_b,
        )
        run_b = page.evaluate(
            "question => window.App.runRegistry.list()"
            ".find(run => run.question === question).runId",
            question_b,
        )
        assert run_a != run_b
        assert page.evaluate("() => window.App.runRegistry.activeCount()") == 2
        expect(page.locator("[data-run-id]")).to_have_count(2)
        page.evaluate("() => window.loadBookmarks()")
        expect(page.locator("[data-run-id]")).to_have_count(2)

        page.locator(f'[data-run-id="{run_a}"]').click()
        assert page.evaluate("() => window.App.runRegistry.visible().runId") == run_a
        expect(page.locator("#threadAskText")).to_have_text(question_a)
        expect(page.locator(f'[data-run-id="{run_a}"]')).to_have_attribute("role", "button")

        page.evaluate("question => window.__runGate.resolveAsks(question)", question_b)
        page.wait_for_function(
            "question => window.__runGate.pending('consensus', question) === 1",
            arg=question_b,
        )
        assert page.evaluate(
            "id => ({status: App.runRegistry.get(id).status, phase: App.runRegistry.get(id).phase})",
            run_b,
        ) == {"status": "running", "phase": "consensus"}
        expect(page.locator("#openaiResponse")).not_to_contain_text(question_b)
        expect(page.locator("#consensusAnswerBody")).not_to_contain_text(
            f"Consensus for {question_b}"
        )

        page.evaluate("question => window.__runGate.resolveAsks(question)", question_a)
        page.wait_for_function(
            "question => window.__runGate.pending('consensus', question) === 1",
            arg=question_a,
        )
        expect(page.locator("#sendButton")).to_have_attribute("aria-label", "Cancel this run")
        page.click("#sendButton")
        page.wait_for_function(
            "id => window.App.runRegistry.get(id).status === 'canceled'",
            arg=run_a,
        )

        assert page.evaluate("id => App.runRegistry.get(id).status", run_b) == "running"
        assert page.evaluate("() => App.runRegistry.activeCount()") == 1
        aborted = page.evaluate("() => window.__runGate.aborted()")
        assert f"consensus|{question_a}" in aborted
        assert f"consensus|{question_b}" not in aborted
        expect(page.locator(f'[data-run-id="{run_a}"]')).to_contain_text("Canceled")
        expect(page.locator(f'[data-run-id="{run_b}"]')).to_contain_text(
            "Writing consensus"
        )

        page.evaluate("question => window.__runGate.resolveConsensus(question)", question_b)
        page.wait_for_function(
            "id => window.App.runRegistry.get(id).status === 'succeeded'",
            arg=run_b,
        )
        assert page.evaluate("() => window.App.runRegistry.visible().runId") == run_a
        expect(page.locator("#threadAskText")).to_have_text(question_a)
        expect(page.locator("#consensusAnswerBody")).not_to_contain_text(
            f"Consensus for {question_b}"
        )

        page.locator(f'[data-run-id="{run_b}"]').click()
        assert page.evaluate("() => window.App.runRegistry.visible().runId") == run_b
        expect(page.locator("#threadAskText")).to_have_text(question_b)
        expect(page.locator("#openaiResponse")).to_contain_text(
            f"{question_b} openai answer"
        )
        expect(page.locator("#mistralResponse")).to_contain_text(
            f"{question_b} mistral answer"
        )
        expect(page.locator("#consensusAnswerBody")).to_contain_text(
            f"Consensus for {question_b}"
        )

        calls_a = page.evaluate(
            "question => window.__runGate.calls('consensus', question)", question_a
        )
        calls_b = page.evaluate(
            "question => window.__runGate.calls('consensus', question)", question_b
        )
        assert len(calls_a) == len(calls_b) == 1
        # The server accepts receipts, never browser-supplied answer text.
        assert 'answers' not in calls_a[0]['body'] and 'answers' not in calls_b[0]['body']
        answers_a = calls_a[0]["body"]["answer_receipts"]
        answers_b = calls_b[0]["body"]["answer_receipts"]
        assert calls_a[0]["body"]["question"] == question_a
        assert answers_a == {"OpenAI": f"receipt:{question_a}:openai", "Mistral": f"receipt:{question_a}:mistral"}
        assert calls_b[0]["body"]["question"] == question_b
        assert answers_b == {"OpenAI": f"receipt:{question_b}:openai", "Mistral": f"receipt:{question_b}:mistral"}
        assert 'sources' not in calls_a[0]['body'] and 'sources' not in calls_b[0]['body']
        assert [body["question"] for body in consensus_bookmark_bodies] == [question_b]
    finally:
        context.close()


def test_two_runs_finish_reverse_order_behind_a_saved_bookmark(
    browser, phase4_server
):
    """Both runs finish and persist without replacing the saved chat view."""

    context, page = _real_firebase_page(browser, phase4_server)
    saved_bookmark_id = "saved_bookmark_a"
    saved_chat_id = "a" * 32
    saved_turn_id = "b" * 32
    saved_question = "Saved bookmark A question"
    saved_consensus = "Saved bookmark A consensus"
    saved_source = {
        "id": "S1",
        "title": "Saved bookmark A source",
        "url": "https://saved.example.invalid/a",
        "provider": "Saved",
    }
    saved_turn = {
        "id": saved_turn_id,
        "status": "completed",
        "position": 1,
        "question": saved_question,
        "mode": "Standard",
        "consensus_model": "saved-consensus-model",
        "consensus": saved_consensus,
        "differences": "Saved bookmark A differences",
        "differences_data": None,
        "sources": [saved_source],
        "attachments": [{
            "name": "saved-a.pdf",
            "mime": "application/pdf",
            "size": 321,
        }],
        "model_answers": {
            "OpenAI": {
                "provider": "OpenAI",
                "model_label": "Saved OpenAI",
                "answer": "Saved bookmark A OpenAI answer",
                "sources": [saved_source],
            },
            "Mistral": {
                "provider": "Mistral",
                "model_label": "Saved Mistral",
                "answer": "Saved bookmark A Mistral answer",
                "sources": [saved_source],
            },
        },
    }
    saved_bookmark = {
        "id": saved_bookmark_id,
        "query": saved_question,
        "title": "Saved bookmark A",
        "mode": "Standard",
        "created_at": "2026-08-24T08:00:00Z",
        "responses": {
            "OpenAI": "Saved bookmark A OpenAI answer",
            "Mistral": "Saved bookmark A Mistral answer",
            "consensus": saved_consensus,
            "differences": "Saved bookmark A differences",
            "differences_data": None,
        },
        "sources": [saved_source],
        "attachments": list(saved_turn["attachments"]),
        "chat_id": saved_chat_id,
        "turn_id": saved_turn_id,
        "consensus_model": "saved-consensus-model",
        "model_labels": {
            "OpenAI": "Saved OpenAI",
            "Mistral": "Saved Mistral",
        },
    }

    bookmark_state = {}
    model_bookmark_bodies = []
    consensus_bookmark_bodies = []
    turn_assignments = {}
    chat_counter = 0
    turn_counter = 200

    def bookmark_document(body, consensus=False):
        bookmark_id = body.get("bookmarkId") or "missing-bookmark-id"
        state = bookmark_state.setdefault(bookmark_id, {
            "responses": {},
            "sources": [],
            "attachments": [],
        })
        if consensus:
            state["responses"].update(body.get("modelResponses") or {})
            state["responses"]["consensus"] = body.get("consensusText") or ""
            state["responses"]["differences"] = body.get("differencesText") or ""
            state["responses"]["differences_data"] = body.get("differencesData")
            state["sources"] = body.get("sources") or []
        else:
            state["responses"][body.get("modelName") or "Unknown"] = (
                body.get("response") or ""
            )
            state["sources"] = body.get("sources") or state["sources"]
            state["attachments"] = body.get("attachments") or state["attachments"]
        return {
            "id": bookmark_id,
            "query": body.get("question") or "",
            "title": body.get("question") or "",
            "mode": body.get("mode") or "Standard",
            "responses": dict(state["responses"]),
            "sources": list(state["sources"]),
            "attachments": list(state["attachments"]),
            "chat_id": body.get("chatId"),
            "turn_id": body.get("turnId"),
            "consensus_model": body.get("consensusModel") or "",
            "model_labels": body.get("modelLabels") or {},
        }

    def prepare_route(route):
        _json(route, {
            "system_prompt": "Prepared reverse-order prompt",
            "usage_run_status": "reserved",
            "free_usage_remaining": 3,
            "limit": 3,
            "deep_limit": 0,
        })

    def create_chat_route(route):
        nonlocal chat_counter
        chat_counter += 1
        _json(route, {"chat": {"id": f"{chat_counter:032x}"}})

    def create_turn_route(route):
        nonlocal turn_counter
        body = json.loads(route.request.post_data or "{}")
        chat_id = route.request.url.split("/chats/", 1)[1].split("/", 1)[0]
        turn_counter += 1
        turn_id = f"{turn_counter:032x}"
        turn_assignments[body["question"]] = {
            "chat_id": chat_id,
            "turn_id": turn_id,
        }
        _json(route, {"turn": {"id": turn_id, "status": "pending"}})

    def model_bookmark_route(route):
        body = json.loads(route.request.post_data or "{}")
        model_bookmark_bodies.append(body)
        _json(route, {"bookmark": bookmark_document(body)})

    def consensus_bookmark_route(route):
        body = json.loads(route.request.post_data or "{}")
        consensus_bookmark_bodies.append(body)
        _json(route, {"bookmark": bookmark_document(body, consensus=True)})

    def assert_saved_view_unchanged(expected_snapshot):
        assert page.evaluate("() => window.__captureSavedBookmarkView()") == expected_snapshot
        assert page.evaluate("() => window.App.runRegistry.visible()") is None
        expect(page.locator("#threadAskText")).to_have_text(saved_question)
        expect(page.locator("#consensusAnswerBody")).to_contain_text(saved_consensus)
        expect(page.locator("#openaiResponse .collapsible-content")).to_contain_text(
            "Saved bookmark A OpenAI answer"
        )

    try:
        page.route("**/prepare", prepare_route)
        page.route("**/chats", create_chat_route)
        page.route("**/chats/*/turns", create_turn_route)
        page.route("**/bookmark", model_bookmark_route)
        page.route("**/bookmark/consensus", consensus_bookmark_route)
        page.route(
            f"**/bookmarks/{saved_bookmark_id}",
            lambda route: _json(route, {"bookmark": saved_bookmark}),
        )
        page.route(
            f"**/bookmarks/{saved_bookmark_id}/conversation?*",
            lambda route: _json(route, {
                "bookmark_id": saved_bookmark_id,
                "chat_id": saved_chat_id,
                "turns": [saved_turn],
                "next_cursor": None,
                "has_more": False,
            }),
        )

        page.wait_for_function(
            "() => window.App?.runRegistry"
            " && typeof window.sendQuestion === 'function'"
            " && typeof window.App.executeConsensusRun === 'function'"
        )
        page.evaluate(
            """() => {
              window.App.runMode.set('consensus');
              const included = new Set(["OpenAI", "Mistral"]);
              window.App.modelPrefs.forEach(pref => {
                window.App.setModelSelectionState(
                  pref,
                  included.has(pref.key),
                  {persist: false, syncCheckbox: true, animate: false}
                );
              });
              window.updateQuestionInputAccess?.();

              const nativeFetch = window.fetch.bind(window);
              const held = [];
              const calls = [];
              const response = data => new Response(JSON.stringify(data), {
                status: 200,
                headers: {"Content-Type": "application/json"}
              });
              const slug = question => question.toLowerCase().replace(/[^a-z0-9]+/g, "-");
              window.fetch = (input, options = {}) => {
                const url = new URL(String(input), window.location.href);
                const isAsk = url.pathname.startsWith("/ask_");
                const isConsensus = url.pathname === "/consensus";
                if (!isAsk && !isConsensus) return nativeFetch(input, options);
                const body = JSON.parse(options.body || "{}");
                const kind = isConsensus ? "consensus" : "ask";
                return new Promise((resolve, reject) => {
                  const entry = {
                    kind,
                    path: url.pathname,
                    question: body.question,
                    body,
                    resolve,
                    reject,
                    settled: false
                  };
                  held.push(entry);
                  calls.push({kind, path: entry.path, question: entry.question, body});
                  const abort = () => {
                    if (entry.settled) return;
                    entry.settled = true;
                    reject(new DOMException("Aborted", "AbortError"));
                  };
                  if (options.signal?.aborted) abort();
                  else options.signal?.addEventListener("abort", abort, {once: true});
                });
              };
              window.__runGate = {
                pending(kind, question) {
                  return held.filter(item => !item.settled
                    && item.kind === kind && item.question === question).length;
                },
                resolveAsks(question) {
                  held.filter(item => !item.settled
                    && item.kind === "ask" && item.question === question)
                    .forEach(item => {
                      item.settled = true;
                      const provider = item.path.replace("/ask_", "");
                      item.resolve(response({
                        response: `${question} ${provider} answer [S1]`,
                        answer_receipt: `receipt:${question}:${provider}`,
                        sources: [{
                          id: "S1",
                          title: `${question} ${provider} source`,
                          url: `https://runs.example.invalid/${slug(question)}/${provider}`,
                          provider
                        }],
                        usage_run_status: "consumed",
                        free_usage_remaining: 2,
                        limit: 3,
                        deep_limit: 0
                      }));
                    });
                },
                resolveConsensus(question) {
                  held.filter(item => !item.settled
                    && item.kind === "consensus" && item.question === question)
                    .forEach(item => {
                      item.settled = true;
                      item.resolve(response({
                        consensus_response: `Consensus for ${question}`,
                        differences: `Differences for ${question}`,
                        differences_data: null,
                        sources: [{
                          id: "S1",
                          title: `${question} consensus source`,
                          url: `https://runs.example.invalid/${slug(question)}/consensus`,
                          provider: "Consensus"
                        }],
                        result_id: `result-${slug(question)}`,
                        chat_id: item.body.chat_id,
                        turn_id: item.body.turn_id,
                        chat_persisted: true,
                        chat_turn_state: "completed",
                        usage_run_status: "consumed",
                        free_usage_remaining: 1,
                        limit: 3,
                        deep_limit: 0
                      }));
                    });
                },
                calls: (kind, question) => calls.filter(item =>
                  (!kind || item.kind === kind) && (!question || item.question === question))
              };
              window.__runPromises = [];
              window.__settledRunQuestions = [];
              window.__finishedRunQuestions = [];
              window.addEventListener("consensio:run-registry-change", event => {
                if (event.detail?.type === "finished"
                    && event.detail?.context?.status === "succeeded") {
                  window.__finishedRunQuestions.push(event.detail.context.question);
                }
              });
            }"""
        )
        assert page.evaluate("() => window.App.getSelectedModelCount()") == 2

        question_first = "Parallel completion run first"
        question_second = "Parallel completion run second"

        page.evaluate(
            """question => {
              const input = document.getElementById("questionInput");
              input.value = question;
              input.dispatchEvent(new Event("input", {bubbles: true}));
              const promise = window.sendQuestion();
              window.__runPromises.push(promise);
              promise.finally(() => window.__settledRunQuestions.push(question));
            }""",
            question_first,
        )
        page.wait_for_function(
            "question => window.__runGate.pending('ask', question) === 2",
            arg=question_first,
        )
        run_first = page.evaluate(
            "question => window.App.runRegistry.list()"
            ".find(run => run.question === question).runId",
            question_first,
        )

        page.evaluate("() => document.getElementById('newRunButton').click()")
        page.wait_for_timeout(500)  # run-start double-click fence
        page.evaluate(
            """question => {
              const input = document.getElementById("questionInput");
              input.value = question;
              input.dispatchEvent(new Event("input", {bubbles: true}));
              const promise = window.sendQuestion();
              window.__runPromises.push(promise);
              promise.finally(() => window.__settledRunQuestions.push(question));
            }""",
            question_second,
        )
        page.wait_for_function(
            "question => window.__runGate.pending('ask', question) === 2",
            arg=question_second,
        )
        run_second = page.evaluate(
            "question => window.App.runRegistry.list()"
            ".find(run => run.question === question).runId",
            question_second,
        )

        assert run_first != run_second
        assert page.evaluate(
            "ids => ids.every(id => {"
            " const run = window.App.runRegistry.get(id);"
            " return run?.basis === null && !run?.conversationLockKey;"
            "})",
            [run_first, run_second],
        ) is True
        assert page.evaluate("() => window.App.runRegistry.activeCount()") == 2

        page.evaluate("id => window.openBookmark(id)", saved_bookmark_id)
        page.wait_for_function(
            "expected => {"
            " const basis = window.App.runRegistry.getSelectedConversationBasis();"
            " return window.App.runRegistry.visible() === null"
            "   && window.App.bookmarkSession.currentId() === expected.bookmarkId"
            "   && window.App.chatSession.activeChatId === expected.chatId"
            "   && window.App.chatSession.activeTurnId === expected.turnId"
            "   && basis?.bookmarkId === expected.bookmarkId"
            "   && basis?.chatId === expected.chatId"
            "   && basis?.turnId === expected.turnId;"
            "}",
            arg={
                "bookmarkId": saved_bookmark_id,
                "chatId": saved_chat_id,
                "turnId": saved_turn_id,
            },
        )
        page.evaluate(
            """() => {
              const text = selector => document.querySelector(selector)?.textContent
                ?.replace(/\\s+/g, " ").trim() || "";
              window.__captureSavedBookmarkView = () => ({
                visibleRunId: window.App.runRegistry.snapshot().visibleRunId,
                basis: window.App.runRegistry.getSelectedConversationBasis(),
                bookmarkId: window.App.bookmarkSession.currentId(),
                chat: {
                  activeChatId: window.App.chatSession.activeChatId,
                  activeTurnId: window.App.chatSession.activeTurnId,
                  pendingChatId: window.App.chatSession.pendingChatId,
                  pendingTurnId: window.App.chatSession.pendingTurnId
                },
                followup: {
                  question: window.App.followup.lastExchange?.question || "",
                  consensus: window.App.followup.lastExchange?.consensus || "",
                  turnId: window.App.followup.lastExchange?.turn?.turn_id || ""
                },
                lastQuestion: window.lastQuestion,
                citationMeta: window.consensusCitationMeta,
                evidenceSources: window.currentEvidenceSources,
                consensusBookmarkPayload: window.lastConsensusBookmarkPayload,
                dom: {
                  question: text("#threadAskText"),
                  openai: text("#openaiResponse .collapsible-content"),
                  mistral: text("#mistralResponse .collapsible-content"),
                  consensus: text("#consensusAnswerBody"),
                  differences: text("#consensusResponse .consensus-differences p")
                }
              });
            }"""
        )
        saved_view_snapshot = page.evaluate(
            "() => window.__captureSavedBookmarkView()"
        )
        assert saved_view_snapshot["visibleRunId"] is None
        assert saved_view_snapshot["bookmarkId"] == saved_bookmark_id
        assert saved_view_snapshot["basis"]["key"] == f"chat:{saved_chat_id}"
        assert saved_view_snapshot["evidenceSources"] == [saved_source]
        assert_saved_view_unchanged(saved_view_snapshot)

        # The second-created run reaches terminal persistence before the first
        # run has even left its held model fan-out.
        page.evaluate(
            "question => window.__runGate.resolveAsks(question)", question_second
        )
        page.wait_for_function(
            "question => window.__runGate.pending('consensus', question) === 1",
            arg=question_second,
        )
        assert_saved_view_unchanged(saved_view_snapshot)
        page.evaluate(
            "question => window.__runGate.resolveConsensus(question)", question_second
        )
        page.wait_for_function(
            "id => {"
            " const run = window.App.runRegistry.get(id);"
            " return run?.status === 'succeeded'"
            "   && run.bookmark.uiReady === true"
            "   && run.persistence.consensusWrite === true"
            "   && run.persistence.pendingWrites === 0;"
            "}",
            arg=run_second,
        )
        assert page.evaluate(
            "id => window.App.runRegistry.get(id).status", run_first
        ) == "running"
        assert page.evaluate("() => window.__finishedRunQuestions") == [question_second]
        assert_saved_view_unchanged(saved_view_snapshot)

        page.evaluate(
            "question => window.__runGate.resolveAsks(question)", question_first
        )
        page.wait_for_function(
            "question => window.__runGate.pending('consensus', question) === 1",
            arg=question_first,
        )
        assert_saved_view_unchanged(saved_view_snapshot)
        page.evaluate(
            "question => window.__runGate.resolveConsensus(question)", question_first
        )
        page.wait_for_function(
            "id => {"
            " const run = window.App.runRegistry.get(id);"
            " return run?.status === 'succeeded'"
            "   && run.bookmark.uiReady === true"
            "   && run.persistence.consensusWrite === true"
            "   && run.persistence.pendingWrites === 0;"
            "}",
            arg=run_first,
        )
        page.wait_for_function("() => window.__settledRunQuestions.length === 2")
        assert page.evaluate("() => window.__finishedRunQuestions") == [
            question_second,
            question_first,
        ]
        assert page.evaluate("() => window.App.runRegistry.activeCount()") == 0
        assert_saved_view_unchanged(saved_view_snapshot)

        run_persistence = page.evaluate(
            """ids => Object.fromEntries(ids.map(id => {
              const run = window.App.runRegistry.get(id);
              return [run.question, {
                bookmarkId: run.bookmark.id,
                chatId: run.completedBasis.chatId,
                turnId: run.completedBasis.turnId,
                consensus: run.consensus.text,
                sources: run.consensus.sources
              }];
            }))""",
            [run_first, run_second],
        )
        assert set(bookmark_state) == {
            run_persistence[question_first]["bookmarkId"],
            run_persistence[question_second]["bookmarkId"],
        }
        assert saved_bookmark_id not in bookmark_state
        assert [body["question"] for body in consensus_bookmark_bodies] == [
            question_second,
            question_first,
        ]
        # Agent-mode answers stay local until the authoritative consensus
        # bookmark promotes the complete provider set atomically.
        assert model_bookmark_bodies == []

        for question in (question_first, question_second):
            slug = question.lower().replace(" ", "-")
            expected = run_persistence[question]
            assignment = turn_assignments[question]
            consensus_body = next(
                body for body in consensus_bookmark_bodies
                if body["question"] == question
            )

            assert consensus_body["bookmarkId"] == expected["bookmarkId"]
            assert consensus_body["chatId"] == assignment["chat_id"]
            assert consensus_body["turnId"] == assignment["turn_id"]
            assert consensus_body["chatId"] == expected["chatId"]
            assert consensus_body["turnId"] == expected["turnId"]
            assert consensus_body["previousQuestion"] == ""
            assert consensus_body["previousTurn"] is None
            # The compatibility fallback intentionally sends only identifiers
            # and small legacy text copies. Sources and model answers are
            # materialized server-side from the owner-bound completed run.
            assert "sources" not in consensus_body
            assert "modelResponses" not in consensus_body
            assert all(slug in source["url"] for source in expected["sources"])
            assert bookmark_state[expected["bookmarkId"]]["responses"][
                "consensus"
            ] == f"Consensus for {question}"
            assert assignment["chat_id"] != saved_chat_id
            assert assignment["turn_id"] != saved_turn_id

        consensus_calls = page.evaluate(
            "() => window.__runGate.calls('consensus').map(call => call.question)"
        )
        assert consensus_calls == [question_second, question_first]
    finally:
        context.close()


def test_missing_answer_receipts_remain_visible_but_never_start_consensus(browser, phase4_server):
    """Negative control for the receipt-bearing provider fixtures above."""
    context, page = _real_firebase_page(browser, phase4_server)
    consensus_calls = []
    try:
        page.route('**/prepare', lambda route: _json(route, {'system_prompt': 'Prepared prompt'}))
        page.route('**/ask_*', lambda route: _json(route, {'response': 'Unstored model answer', 'sources': []}))
        page.route('**/consensus', lambda route: (consensus_calls.append(route.request.post_data_json), _json(route, {})))
        page.locator('#questionInput').fill('Check the storage boundary')
        page.locator('#sendButton').click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'failed'")
        results = page.evaluate("() => Object.values(App.runRegistry.visible().modelResults).map(r => ({text:r.text,status:r.status,error:r.error,receipt:r.receipt}))")
        assert len(results) == 6
        assert all(item['text'] == 'Unstored model answer' and item['status'] == 'incomplete'
                   and item['receipt'] is None and 'could not be saved' in item['error'] for item in results)
        assert consensus_calls == []
        expect(page.locator('#consensusAnswerBody')).not_to_contain_text('Unstored model answer')
    finally:
        context.close()


def test_disabled_agent_mode_is_six_answers_only(browser, phase4_server):
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
        expect(mode).to_have_value("consensus")
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
        expect(page.locator("#consensusRun")).to_be_hidden()
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

        expect(page.locator(".explanation-popup")).to_contain_text(
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


def test_cancel_during_token_resolution_keeps_followup_and_creates_no_usage_run(
    browser, phase4_server
):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.evaluate(
            """() => {
              document.getElementById("selectOpenAI").checked = true;
              document.getElementById("selectMistral").checked = true;
              document.getElementById("questionInput").value = "What changed since yesterday?";
              window.App.runMode.set('consensus');
              window.App.runRegistry.selectConversationBasis({
                bookmarkId: "followup-bookmark",
                chatId: "a".repeat(32),
                turnId: "b".repeat(32),
                question: "Previous question",
                consensus: "Previous consensus",
                currentTurn: {
                  turn_id: "b".repeat(32),
                  question: "Previous question",
                  consensus: "Previous consensus",
                },
                title: "Previous question",
              });
              window.App.followup.offer("Previous question", "Previous consensus");
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

        # The selected Registry basis is the continuation authority. The
        # compatibility followup projection may be rebuilt while the canceled
        # run is removed, so it is not the state to assert here.
        selected_basis = page.evaluate(
            "() => window.App.runRegistry.getSelectedConversationBasis()"
        )
        assert selected_basis["key"] == "chat:" + "a" * 32
        assert selected_basis["question"] == "Previous question"
        assert selected_basis["consensus"] == "Previous consensus"
        assert page.evaluate("() => !!window.App.followup.spentExchange") is False
        assert page.evaluate("() => window.App.usageRun?.current?.key || null") is None
        assert page.evaluate("() => window.isQueryRequestRunning()") is False
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
            "Share this consensus publicly"
        )
        page.evaluate("() => window.__resolveWatchCreate()")
        page.wait_for_timeout(150)

        expect(page.locator("#shareModalTitle")).to_have_text(
            "Share this consensus publicly"
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
            "Share this consensus publicly"
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
