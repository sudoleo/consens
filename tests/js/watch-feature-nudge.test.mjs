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
            <h2>Consensus Answer</h2>
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
    ["static/js/watch-state.js", "static/js/watch.js"],
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
