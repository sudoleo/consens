import { describe, expect, it, vi } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

/**
 * Der Hinweis "Keep this answer current" haengt am Watch-Knopf im Fuss der
 * Antwort. Er lebt als eigener Layer direkt unter <body>: Wenn stattdessen
 * die Consensus-Sektion ueber den fixierten Composer gehoben wird, malt auch
 * der Antworttext ueber das Eingabefeld.
 */
const BODY = `
  <div class="container">
    <div class="consensus-section">
      <div id="consensusOutput" class="consensus-output">
        <div class="consensus-box" id="consensusResponse">
          <div class="consensus-main">
            <h2>Consensus answer</h2>
            <div id="consensusAnswerBody" class="consensus-answer-body"></div>
            <div id="runProvenance" class="run-provenance consensus-footer">
              <span class="consensus-footer-actions" id="consensusFooterActions">
                <span class="consensus-copy-inline"></span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="input-section"></div>
  </div>
`;

function boot() {
  let queued = null;
  const harness = loadScripts(
    ["static/js/watch-state.js", "static/js/watch-fields.js", "static/js/watch.js"],
    {
      body: BODY,
      before(window) {
        // Der Hinweis kommt mit 650 ms Verzoegerung; hier wird er von Hand
        // ausgeloest, damit der Test nicht auf die Uhr wartet.
        window.setTimeout = fn => {
          queued = fn;
          return 7;
        };
        window.clearTimeout = () => {
          queued = null;
        };
        window.fetch = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
        window.auth = { currentUser: { uid: "nudge-user" } };
        window.lastShareResultId = "share-1";
        window.App = { watch: {} };
      }
    }
  );
  // Der Hinweis erscheint erst ab der dritten abgeschlossenen Frage: jeder
  // Lauf meldet sich, die ersten beiden zaehlen nur.
  const run = harness => {
    harness.window.App.watch.showFeatureNudge();
    queued?.();
  };
  return {
    ...harness,
    run: () => run(harness),
    fire: () => queued?.(),
    show: () => {
      run(harness);
      run(harness);
      run(harness);
    }
  };
}

describe("watch feature nudge", () => {
  it("haelt sich bis zur dritten Frage zurueck", () => {
    const { document, run } = boot();

    run();
    expect(document.getElementById("watchFeatureNudge")).toBeNull();
    run();
    expect(document.getElementById("watchFeatureNudge")).toBeNull();
    run();
    expect(document.getElementById("watchFeatureNudge")).not.toBeNull();
  });

  it("portaliert nur den Hinweis ueber den Composer, nie die Antwort", () => {
    const { document, show } = boot();
    show();

    const nudge = document.getElementById("watchFeatureNudge");
    expect(nudge).not.toBeNull();
    expect(nudge.parentElement).toBe(document.body);
    expect(document.querySelector(".watch-feature-anchor").classList.contains("has-feature-nudge"))
      .toBe(true);
    expect(document.querySelectorAll(".has-watch-feature-nudge").length).toBe(0);
    expect(nudge.style.top).not.toBe("");
    expect(nudge.style.left).not.toBe("");
  });

  it("scrollt mit der Seite und setzt sich nur an den Raendern nach", () => {
    // Fixiert und bei jedem Scroll-Event nachgesetzt, lief die Karte ihrem
    // Platz ein Bild hinterher und zitterte (Apple-Audit D8).
    const { window, document, show } = boot();
    window.innerWidth = 1200;
    window.innerHeight = 800;
    let scrollY = 0;
    const box = (top, height, left, width) => ({
      top, bottom: top + height, left, right: left + width, width, height, x: left, y: top
    });
    show();
    const nudge = document.getElementById("watchFeatureNudge");
    const anchor = document.querySelector(".watch-feature-anchor");
    anchor.getBoundingClientRect = () => box(900 - scrollY, 30, 900, 100);
    anchor.getClientRects = () => [box(900 - scrollY, 30, 900, 100)];
    nudge.getBoundingClientRect = () => box(0, 120, 0, 272);
    document.body.getBoundingClientRect = () => box(-scrollY, 3000, 0, 1200);
    document.querySelector(".input-section").getBoundingClientRect = () => box(700, 80, 300, 600);
    const scrollTo = y => {
      scrollY = y;
      document.dispatchEvent(new window.Event("scroll"));
    };

    // Below the composer the card waits above it, in page coordinates.
    scrollTo(0);
    expect([nudge.style.top, nudge.style.left]).toEqual(["572px", "728px"]);
    scrollTo(100);
    expect(nudge.style.top).toBe("672px");
    // Once it fits under its button, the page carries it: nothing to write.
    scrollTo(400);
    expect(nudge.style.top).toBe("940px");
    const observer = new window.MutationObserver(() => {});
    observer.observe(nudge, { attributes: true });
    scrollTo(450);
    scrollTo(500);
    expect(observer.takeRecords()).toEqual([]);
    expect(nudge.style.top).toBe("940px");
    observer.disconnect();
  });

  it("bietet im Agent-Modus eine Watch aus der Frage an", async () => {
    const { window, document, fire } = boot();
    const anchor = document.createElement("div");
    anchor.id = "agentWatchAnchor";
    document.body.appendChild(anchor);
    const source = { eligible: true, question: "Wann erscheint Version 3?", anchor };
    window.App.watch.showFeatureNudge(source);
    window.App.watch.showFeatureNudge(source);
    fire();
    expect(document.getElementById("watchFeatureNudge")).toBeNull();
    window.App.watch.showFeatureNudge(source);
    fire();
    expect(document.getElementById("watchFeatureNudge")).not.toBeNull();
    window.auth.currentUser.getIdToken = async () => "token";
    window.fetch = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({
      watch: { interval: "weekly", run_weekday: "monday", run_time: "09:00", timezone: "UTC" } }) }));
    document.getElementById("watchNudgeStart").click();
    await vi.waitFor(() => expect(window.fetch).toHaveBeenCalled());
    const body = JSON.parse(window.fetch.mock.calls[0][1].body);
    expect(body.question).toBe("Wann erscheint Version 3?");
    expect(body.result_id).toBeUndefined();
  });

  it("zeigt im Agent-Modus nichts ohne Quellen oder bei Folgefragen", () => {
    const { window, document, fire } = boot();
    const anchor = document.createElement("div");
    document.body.appendChild(anchor);
    for (let i = 0; i < 3; i += 1) {
      window.App.watch.showFeatureNudge({ eligible: false, question: "Frage zu Version 3?", anchor });
    }
    fire();
    expect(document.getElementById("watchFeatureNudge")).toBeNull();
  });

  it("nimmt die Markierung beim Schliessen wieder zurueck", () => {
    const { document, show } = boot();
    show();

    document.querySelector(".watch-feature-nudge-close").click();

    expect(document.getElementById("watchFeatureNudge")).toBeNull();
    expect(document.querySelector(".watch-feature-anchor").classList.contains("has-feature-nudge"))
      .toBe(false);
  });
});
