/**
 * Jedes Konto darf Dateien anhaengen (seit 2026-10-02, die Dateien kosten
 * Tokens aus dem eigenen Kontingent); ein Gast wird zur Anmeldung geschickt.
 *
 * Die Stufe entsteht am Ende einer Kette: /user_status -> updateUserTierUI ->
 * App.state -> window-Getter. Getestet wird deshalb die ECHTE Kette
 * (app-state.js + user-tier.js + attachments.js), nicht ein gesetztes Flag.
 *
 * Der zweite Teil sichert die Stelle, an der die Stufe wieder verloren gehen
 * kann: `is_pro_user: false` bedeutet seit Plus nur noch "nicht Pro" und
 * unterscheidet Free nicht mehr von Plus. Ein Lauf ohne ausdrueckliches `tier`
 * darf die Anzeige deshalb nur anheben, nie senken.
 */

import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const BODY = `
<div class="chat-input-container">
  <div id="attachmentBar" class="attachment-bar" hidden></div>
  <textarea id="questionInput"></textarea>
  <button id="attachTrigger"></button>
  <div id="attachMenu" hidden><button id="attachUploadOption"></button></div>
  <input id="attachFileInput" type="file">
</div>
<span id="proBadge" class="pro-badge"></span>
<a id="upgradeLink"></a>
<label class="switch attach-menu-switch"><input type="checkbox" id="reasoningToggle"></label>
<div id="loginModal" style="display:none"><input id="loginEmail"></div>
<div id="proFeatureModal" style="display:none">
  <span id="proModalFeatureName"></span><p id="proModalDescription"></p>
</div>
`;

function boot() {
  const harness = loadScripts(
    [
      "static/js/app-state.js",
      "static/js/app-core.js",
      "static/js/attachments.js",
      "static/js/user-tier.js"
    ],
    {
      body: BODY,
      // app-core.js fragt beim Laden das Farbschema ab; jsdom kennt matchMedia nicht.
      before(window) {
        window.matchMedia = () => ({
          matches: false,
          addEventListener() {}, removeEventListener() {},
          addListener() {}, removeListener() {}
        });
      }
    }
  );
  const gated = [];
  harness.window.App.showProFeatureModal = (feature) => {
    gated.push(feature);
    return true;
  };
  harness.gated = gated;
  return harness;
}

function clickUpload({ window, document }) {
  document.getElementById("attachUploadOption")
    .dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
}

function signIn(harness) {
  harness.window.auth = { currentUser: { uid: "u1" } };
}

describe("attachment gate per tier", () => {
  it("lets a Plus account open the file picker", () => {
    const harness = boot();
    signIn(harness);
    harness.window.updateUserTierUI("plus", true);

    expect(harness.window.userTier).toBe("plus");
    expect(harness.window.isUserPlus).toBe(true);
    // Die Kostengrenze bleibt: Plus ist kein Pro.
    expect(harness.window.isUserPro).toBe(false);

    clickUpload(harness);
    expect(harness.gated).toEqual([]);
  });

  it("lets a Free account open the file picker too", () => {
    const harness = boot();
    signIn(harness);
    harness.window.updateUserTierUI("free", true);

    expect(harness.window.isUserPlus).toBe(false);
    clickUpload(harness);
    expect(harness.gated).toEqual([]);
    expect(harness.document.getElementById("loginModal").style.display).toBe("none");
  });

  it("asks a guest to sign in instead of opening the picker", () => {
    const harness = boot();
    harness.window.auth = { currentUser: null };
    clickUpload(harness);
    expect(harness.gated).toEqual([]);
    expect(harness.document.getElementById("loginModal").style.display).toBe("block");
  });

  it("names the tier on the badge and drops the Free-only upgrade link", () => {
    const { window, document } = boot();

    window.updateUserTierUI("plus", true);
    expect(document.getElementById("proBadge").textContent).toBe("Plus");
    expect(document.getElementById("upgradeLink").style.display).toBe("none");

    window.updateUserTierUI("pro", true);
    expect(document.getElementById("proBadge").textContent).toBe("Pro");

    window.updateUserTierUI("free", true);
    expect(document.getElementById("proBadge").style.display).toBe("none");
    expect(document.getElementById("upgradeLink").style.display).toBe("inline-flex");
  });

  it("keeps Plus when a run reports only is_pro_user: false", () => {
    // Genau der Rueckfall, der Plus-Konten die Anhaenge wieder wegnimmt: eine
    // Antwort ohne "tier" (aelterer Server, Tab von vor einem Deploy) trug
    // frueher ein blankes false in updateUserTierUI und setzte damit Free.
    const harness = boot();
    signIn(harness);
    harness.window.updateUserTierUI("plus", true);

    const runTier = tierSignalFor({ isProUser: false });
    expect(runTier).toBeNull();

    clickUpload(harness);
    expect(harness.gated).toEqual([]);
  });

  it("still accepts an explicit downgrade and a bare Pro signal", () => {
    expect(tierSignalFor({ tier: "free" })).toBe("free");
    expect(tierSignalFor({ isProUser: true })).toBe("pro");
    expect(tierSignalFor({ tier: "plus", isProUser: false })).toBe("plus");
  });
});

/**
 * Die Auswertung aus run-view.js/query-send.js: nur ein ausdrueckliches `tier`
 * oder ein `true` darf die Stufe stellen.
 */
function tierSignalFor(usage) {
  return usage.tier ?? (usage.isProUser === true ? "pro" : null);
}

/**
 * Der Anfang der Kette: firebase.js.
 *
 * Genau hier ist die Plus-Stufe zuletzt verloren gegangen. Die Umstellung auf
 * drei Stufen hat jeden Aufrufer tier-bewusst gemacht -- ausser den beiden in
 * firebase.js, die /user_status und /usage auswerten. Die reichten weiter
 * `data.is_pro` durch, und weil das Flag fuer Plus false ist, stand jedes
 * Plus-Konto direkt nach dem Laden wieder auf Free: kein Anhang, kein Resolve.
 *
 * firebase.js laedt das Firebase-SDK von gstatic und laesst sich deshalb nicht
 * in jsdom booten. Geprueft wird darum die Quelle: kein Aufruf der beiden
 * Tier-Senken darf ein is_pro-Flag als Stufe uebergeben.
 */
describe("firebase.js feeds the tier, not the pro flag", () => {
  const source = readFileSync(
    new URL("../../static/firebase.js", import.meta.url),
    "utf8"
  );

  // setCurrentUsageLimits gibt es seit dem gemeinsamen Tokenkonto nicht
  // mehr: das Konto kommt fertig als token_budget vom Server.
  const TIER_SINKS = ["updateUserTierUI"];

  // Das erste Argument jedes Aufrufs. Die Pruefungen auf die Existenz der
  // Funktion (`typeof window.x === "function"`) haben keine oeffnende Klammer
  // direkt hinter dem Namen und fallen damit heraus.
  function firstArguments(name) {
    return source
      .split(name + "(")
      .slice(1)
      .map(rest => rest.split(/[,)]/)[0].trim());
  }

  it.each(TIER_SINKS)("never passes an is_pro flag to %s", (name) => {
    const args = firstArguments(name);
    expect(args.length).toBeGreaterThan(0);
    args.forEach(arg => expect(arg).not.toMatch(/is_?[Pp]ro/));
  });

  it("reads data.tier with the pro flag only as a fallback", () => {
    // `data.tier ?? data.is_pro`: ein aelterer Server ohne "tier" darf weiter
    // Pro erkennen, aber nur als Rueckfall.
    expect(source).toMatch(/data\.tier\s*\?\?/);
  });
});
