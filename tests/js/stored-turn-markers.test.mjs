/**
 * Inline-Marken eines archivierten Turns.
 *
 * Sobald eine Follow-up-Frage gestellt wird, rutscht die fertige Antwort in
 * #threadHistory und wird aus differences_data neu verankert. Der Widerspruch
 * muss diesen Umzug ueberleben: bis 2026-08-22 bekam der strittige Satz dort
 * nur noch sein Claim-Badge ("1 of 6 models support this", bernstein) und las
 * sich damit als blosse Stuetzungsquote statt als roter Widerspruch.
 */

import { beforeEach, describe, expect, it } from "vitest";

import { loadScripts } from "./helpers/appWindow.mjs";

const ANSWER = "The tower is 330 m tall. A ticket costs 29 euros.";
const DISPUTED = "A ticket costs 29 euros.";

const DIFFERENCES_DATA = {
  models_compared: ["OpenAI", "Gemini", "Anthropic"],
  claims: [
    {
      anchor: DISPUTED,
      agree: [{ model: "OpenAI", quote: "29 euros" }],
      dissent: [
        { model: "Gemini", quote: "35 euros" },
        { model: "Anthropic", quote: "22 euros" }
      ]
    }
  ],
  differences: [
    {
      claim: "the ticket price",
      type: "contradiction",
      severity: "major",
      consensus_anchor: DISPUTED,
      positions: [
        { models: ["OpenAI"], stance: "29 euros", quote: "29 euros" },
        { models: ["Gemini", "Anthropic"], stance: "more than 29 euros", quote: "35 euros" }
      ]
    }
  ]
};

function boot() {
  const { window, document } = loadScripts([
    "static/js/user-settings.js", "static/js/consensus-anchor.js",
    "static/js/consensus-insights.js"
  ], {
    body: `
      <article class="thread-history-turn" data-turn-id="t1">
        <div class="consensus-answer-body thread-history-answer-body"><p>${ANSWER}</p></div>
        <div class="consensus-claims-fallback" hidden></div>
        <div class="thread-history-panels"></div>
      </article>
      <div id="differencesCards"></div>
      <div id="claimPopover" hidden></div><div id="claimSheetBackdrop" hidden></div>
    `
  });
  // jsdom kennt kein Scrollen; die Marke ruft es beim Oeffnen der Karte auf.
  window.Element.prototype.scrollIntoView = function () {};
  const body = document.querySelector(".thread-history-answer-body");
  const fallback = document.querySelector(".consensus-claims-fallback");
  return { window, document, body, fallback };
}

// Die Karten baut consensus-run.js erst NACH dem Verankern in die Schublade
// des Turns -- genau diese Reihenfolge bildet der Helfer nach.
function appendStoredCards(window, document, data) {
  const turn = document.querySelector(".thread-history-turn");
  const panel = document.createElement("div");
  panel.className = "thread-history-panel";
  panel.id = "threadHistoryPanel-1";
  panel.hidden = true;
  const tab = document.createElement("button");
  tab.className = "consensus-tab";
  tab.setAttribute("aria-expanded", "false");
  tab.setAttribute("aria-controls", panel.id);
  const cards = document.createElement("div");
  cards.className = "differences-cards thread-history-differences";
  window.renderStoredDifferenceCards(cards, data);
  panel.appendChild(cards);
  turn.querySelector(".thread-history-panels").append(tab, panel);
  return { tab, panel, cards };
}

describe("renderStoredConsensusClaims", () => {
  let ctx;
  beforeEach(() => {
    ctx = boot();
    ctx.window.renderStoredConsensusClaims(ctx.body, DIFFERENCES_DATA, ctx.fallback, []);
  });

  it("keeps the contradiction line on the disputed sentence", () => {
    const marks = ctx.body.querySelectorAll(".cx-claim.is-major");

    expect(marks.length).toBeGreaterThan(0);
    expect(marks[0].textContent).toContain("ticket costs 29 euros");
  });

  it("does not downgrade the contradiction to a support ratio", () => {
    expect(ctx.body.querySelector(".claim-badge")).toBe(null);
    expect(ctx.body.textContent).not.toContain("support this");
    expect(ctx.body.querySelector("[role='button']").getAttribute("aria-label"))
      .toContain("contradict");
  });

  it("opens the difference card of its own turn from the mark's card, not the live footer", () => {
    const { tab, panel, cards } = appendStoredCards(ctx.window, ctx.document, DIFFERENCES_DATA);
    const liveCards = ctx.document.getElementById("differencesCards");

    ctx.body.querySelector(".cx-claim.is-major")
      .dispatchEvent(new ctx.window.MouseEvent("click", { bubbles: true }));
    // The click pins the mark's card: the two sides, and its topic leads on.
    const popover = ctx.document.getElementById("claimPopover");
    expect(popover.hidden).toBe(false);
    expect([...popover.querySelectorAll(".cx-card-claim")].map(el => el.textContent))
      .toEqual(["29 euros", "more than 29 euros"]);
    expect(panel.hidden).toBe(true);
    popover.querySelector("button.cx-card-title").click();

    expect(popover.hidden).toBe(true);
    expect(panel.hidden).toBe(false);
    expect(tab.getAttribute("aria-expanded")).toBe("true");
    expect(cards.querySelector(".diff-card").classList.contains("is-focused")).toBe(true);
    expect(liveCards.querySelector(".is-focused")).toBe(null);
  });
});

describe('real archived drawer row', () => {
  it('keeps all drawers in one row, toggles only its own panel and allocates unique IDs', () => {
    const { window, document } = loadScripts(['static/js/user-settings.js', 'static/js/consensus-anchor.js', 'static/js/consensus-insights.js', 'static/js/consensus-run.js'], {
      body: '<div id="threadHistory" hidden></div><div id="differencesCards"></div>'
        + '<div id="claimPopover" hidden></div><div id="claimSheetBackdrop" hidden></div>',
      before(window) { window.App = {}; window.Element.prototype.scrollIntoView = () => {}; },
    });
    const data = { question: 'What does the tower cost?', consensus: ANSWER, differences_data: DIFFERENCES_DATA,
      sources: [{ title: 'Price list', url: 'https://example.org/prices' }],
      model_answers: { OpenAI: { answer: '29 euros', model_label: 'OpenAI' } } };
    window.App.followup.renderStoredTurns([{ ...data, turn_id: 'first' }, { ...data, turn_id: 'second' }]);
    const turns = [...document.querySelectorAll('.thread-history-turn')];
    expect(turns).toHaveLength(2);
    const ids = [...document.querySelectorAll('[id]')].map(el => el.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const turn of turns) {
      const tabs = [...turn.querySelector('.thread-history-tabs').children];
      expect(tabs.map(tab => tab.querySelector('.consensus-tab-label').dataset.short)).toEqual(['Differences', 'Answers', 'Sources']);
      expect(turn.querySelector('.thread-history-details')).toBeNull();
      for (const tab of tabs) {
        expect(tab.classList.contains('consensus-tab')).toBe(true);
        expect(tab.classList.contains('consensus-evidence-action')).toBe(true);
        const panel = document.getElementById(tab.getAttribute('aria-controls'));
        expect(turn.contains(panel)).toBe(true);
        expect(panel.hidden).toBe(true);
        tab.click(); expect(panel.hidden).toBe(false); expect(tab.getAttribute('aria-expanded')).toBe('true');
        expect(document.querySelectorAll('.thread-history-panel:not([hidden])')).toHaveLength(1);
        tab.click(); expect(panel.hidden).toBe(true); expect(tab.getAttribute('aria-expanded')).toBe('false');
      }
    }
    turns[1].querySelector('.cx-claim.is-major').click();
    document.querySelector('#claimPopover button.cx-card-title').click();
    expect(turns[1].querySelector('.diff-card.is-focused')).not.toBeNull();
    expect(turns[0].querySelector('.diff-card.is-focused')).toBeNull();
    expect(document.getElementById('differencesCards').children).toHaveLength(0);
    window.close();
  });
});

describe("renderStoredConsensusClaims without differences", () => {
  it("still shows the support ratio for a merely split claim", () => {
    const ctx = boot();

    ctx.window.renderStoredConsensusClaims(
      ctx.body,
      { ...DIFFERENCES_DATA, differences: [] },
      ctx.fallback,
      []
    );

    const badge = ctx.body.querySelector(".claim-badge");
    expect(badge).not.toBe(null);
    expect(badge.getAttribute("aria-label")).toContain("1 of 3 models support this");
  });
});

describe("difference cards in the detail panel", () => {
  const MIXED = {
    models_compared: ["OpenAI", "Gemini", "Anthropic"],
    claims: [],
    differences: [
      { claim: "the tower height", type: "contradiction", severity: "minor",
        consensus_anchor: "The tower is 330 m tall.",
        positions: [{ models: ["OpenAI"], stance: "330 m", quote: "330 m" },
          { models: ["Gemini"], stance: "324 m", quote: "324 m" }] },
      { claim: "what visitors should focus on", type: "emphasis",
        positions: [{ models: ["Anthropic"], stance: "The view" }, { models: ["OpenAI"], stance: "The history" }] },
      DIFFERENCES_DATA.differences[0]
    ]
  };

  it("orders critical first, names severity in one word and keeps the data index", () => {
    const ctx = boot();
    const cards = ctx.document.createElement("div");
    ctx.window.renderStoredDifferenceCards(cards, MIXED);
    const all = [...cards.querySelectorAll(".diff-card")];
    expect(all.map(card => card.querySelector(".diff-type-tag").textContent)).toEqual(["Critical", "Minor", "Emphasis"]);
    expect(all.map(card => card.dataset.differenceIndex)).toEqual(["2", "0", "1"]);
    expect(all.map(card => card.querySelector(".sev-dot").className)).toEqual(["sev-dot is-crit", "sev-dot is-warn", "sev-dot is-info"]);
    // Behind a critical contradiction the smaller ones wait in one closed group.
    const group = cards.querySelector("details.diff-more");
    expect(group.open).toBe(false);
    expect(group.querySelector(".diff-more-summary").textContent).toBe("2 smaller differences");
    expect([...group.querySelectorAll(".diff-card")]).toEqual(all.slice(1));
    expect(cards.lastElementChild).toBe(group);
    expect(cards.textContent).not.toContain("Contradiction ·");
    // The full meaning stays available to screen readers and as a tooltip.
    expect(all[0].querySelector(".diff-card-tags").textContent).toBe("Critical contradiction:");
    expect(all[0].querySelector(".diff-type-tag").title).toBe("Critical contradiction");
  });

  it("puts each position's models on one line, as jump links only when an answer is reachable", () => {
    const ctx = boot();
    const cards = ctx.document.createElement("div");
    ctx.window.renderStoredDifferenceCards(cards, DIFFERENCES_DATA);
    const positions = cards.querySelectorAll(".diff-position");
    expect(cards.querySelector(".diff-position-links")).toBe(null);
    expect([...positions[1].querySelectorAll(".diff-position-label .diff-position-name")].map(n => n.textContent))
      .toEqual(["Gemini", "Anthropic"]);
    expect(cards.querySelector(".diff-jump-link")).toBe(null);

    const opened = [];
    const navigation = { canOpen: model => model !== "Anthropic", open: (model, quote) => opened.push([model, quote]) };
    ctx.window.renderStoredDifferenceCards(cards, DIFFERENCES_DATA, { answerNavigation: navigation, modelLabel: m => m + " Pro" });
    const head = cards.querySelectorAll(".diff-position")[1].querySelector(".diff-position-label");
    const [gemini, anthropic] = head.children;
    expect(gemini.tagName).toBe("BUTTON");
    expect(gemini.classList.contains("diff-jump-link")).toBe(true);
    expect(gemini.querySelector(".diff-position-name").textContent).toBe("Gemini Pro");
    expect(gemini.getAttribute("aria-label")).toBe("Open the full answer from Gemini Pro");
    expect(anthropic.tagName).toBe("SPAN");
    gemini.click();
    expect(opened).toEqual([["Gemini", "35 euros"]]);
  });

  it("sets a contradiction's claims against each other, the answer's side first", () => {
    const ctx = boot();
    const cards = ctx.document.createElement("div");
    ctx.document.body.appendChild(cards);
    const data = structuredClone(DIFFERENCES_DATA);
    data.differences[0].positions[1].in_answer = true;
    ctx.window.renderStoredDifferenceCards(cards, data);
    const sides = cards.querySelector(".diff-sides");
    // Always one above the other, so two and three sides look alike.
    expect(sides.className).toBe("diff-sides is-versus");
    expect([...sides.children].map(el => el.className))
      .toEqual(["diff-position is-answer", "diff-versus-mark", "diff-position"]);
    expect(sides.querySelector(".diff-versus-mark").textContent).toBe("vs");
    const [answer, other] = sides.querySelectorAll(".diff-position");
    expect(answer.querySelector(".diff-position-answer").textContent).toBe("In the answer");
    expect(answer.querySelector(".diff-position-stance").textContent).toBe("more than 29 euros");
    expect(other.querySelector(".diff-position-answer")).toBe(null);
    // Several models: icons and a count; one model: its name.
    expect(answer.querySelector(".diff-position-label").classList.contains("is-group")).toBe(true);
    expect(answer.querySelector(".diff-position-count").textContent).toBe("2 models");
    expect(other.querySelector(".diff-position-count")).toBe(null);
    // The claim first, then one quiet line: who, the answer's side, the quote toggle.
    expect([...answer.children].map(el => el.className))
      .toEqual(["diff-position-stance", "diff-position-meta", "diff-position-quote"]);
    expect([...answer.querySelector(".diff-position-meta").children].map(el => el.className))
      .toEqual(["diff-position-label is-group", "diff-position-answer", "diff-quote-toggle"]);
    // The quote waits behind a toggle.
    const toggle = answer.querySelector(".diff-quote-toggle");
    const quote = answer.querySelector(".diff-position-quote");
    expect(quote.hidden).toBe(true);
    toggle.click();
    expect(quote.hidden).toBe(false);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(toggle.textContent).toBe("Hide quote");
    toggle.click();
    expect(quote.hidden).toBe(true);
  });

  it("shows the same claim once, with every model on its first side only", () => {
    // Live 2026-10-21: the answer's claim for Luna, the same claim again for
    // two models, then the rival claim. Saved chats still carry that shape.
    const ctx = boot();
    const cards = ctx.document.createElement("div");
    const data = {
      models_compared: ["OpenAI", "Gemini", "Anthropic", "Grok"],
      differences: [{
        claim: "Shoe for maximum cushioning", type: "contradiction", severity: "major",
        positions: [
          { models: ["OpenAI"], stance: "The Hyperboost Edge is the pick for maximum cushioning.", quote: "", in_answer: true },
          { models: ["Gemini", "Anthropic", "OpenAI"], stance: "the hyperboost edge is the pick for  maximum cushioning",
            quote: "Hyperboost Edge" },
          { models: ["Grok", "Gemini"], stance: "The Supernova Rise 3 is the pick.", quote: "Supernova Rise 3" }
        ]
      }]
    };
    const saved = structuredClone(data);
    ctx.window.renderStoredDifferenceCards(cards, data);
    const sides = cards.querySelector(".diff-sides");
    expect([...sides.children].map(el => el.className))
      .toEqual(["diff-position is-answer", "diff-versus-mark", "diff-position"]);
    const [answer, other] = sides.querySelectorAll(".diff-position");
    expect(answer.querySelector(".diff-position-stance").textContent)
      .toBe("The Hyperboost Edge is the pick for maximum cushioning.");
    expect([...answer.querySelectorAll(".diff-position-name")].map(n => n.textContent))
      .toEqual(["OpenAI", "Gemini", "Anthropic"]);
    expect(answer.querySelector(".diff-position-count").textContent).toBe("3 models");
    // The first quote there is backs the merged side.
    expect(answer.querySelector(".diff-position-quote").textContent).toBe("Hyperboost Edge");
    expect([...other.querySelectorAll(".diff-position-name")].map(n => n.textContent)).toEqual(["Grok"]);
    // The saved data itself stays as it was (Resolve keys on it).
    expect(data).toEqual(saved);
  });

  it("gives sides that turn out to be one claim no versus", () => {
    const ctx = boot();
    const cards = ctx.document.createElement("div");
    ctx.window.renderStoredDifferenceCards(cards, {
      models_compared: ["OpenAI", "Gemini"],
      differences: [{ claim: "price", type: "contradiction", severity: "minor",
        positions: [{ models: ["OpenAI"], stance: "29 euros.", in_answer: true }, { models: ["Gemini"], stance: "29 Euros" }] }]
    });
    const sides = cards.querySelector(".diff-sides");
    expect(sides.className).toBe("diff-sides");
    expect(sides.querySelector(".diff-versus-mark")).toBe(null);
    expect(sides.querySelectorAll(".diff-position")).toHaveLength(1);
    expect(sides.querySelector(".diff-position-count").textContent).toBe("2 models");
  });

  it("says each claim once in differences saved before the versus format", () => {
    const ctx = boot();
    const cards = ctx.document.createElement("div");
    ctx.window.renderStoredDifferenceCards(cards, {
      models_compared: ["Grok", "Gemini", "DeepSeek"],
      differences: [{
        claim: "Model F beschreibt sinkende Frontier-Preise, während die Synthese steigende Frontier-Tokenpreise meldet.",
        type: "contradiction", severity: "major",
        positions: [
          { models: ["Grok"], stance: "Model F sagt, die Frontier-Preise seien 2026 stark gesunken.", quote: "−67 bis −75 %" },
          { models: ["Gemini", "DeepSeek"], stance: "Die Synthese sagt, dass die Frontier-Tokenpreise stiegen.", quote: "+66,7 % YoY" }
        ] }]
    }, { modelLabel: name => name === "Grok" ? "Grok 4.3" : name });
    const claim = cards.querySelector(".diff-card-claim");
    // The label gets its real name; the narrative heading only shows while closed.
    expect(claim.textContent).toBe("Grok 4.3 beschreibt sinkende Frontier-Preise, während die Synthese steigende Frontier-Tokenpreise meldet.");
    expect(claim.classList.contains("is-narrative")).toBe(true);
    // "The synthesis" is the answer itself: its side comes first. After "dass" the
    // rest is no sentence on its own, so the sentence stays and names its speaker.
    const [answer, other] = cards.querySelectorAll(".diff-position");
    expect(answer.classList.contains("is-answer")).toBe(true);
    expect(answer.querySelector(".diff-position-stance").textContent).toBe("Die Antwort sagt, dass die Frontier-Tokenpreise stiegen.");
    expect(other.querySelector(".diff-position-stance").textContent).toBe("Die Frontier-Preise seien 2026 stark gesunken.");
  });

  it("names a judge label everywhere once one side gives it away", () => {
    const ctx = boot();
    const cards = ctx.document.createElement("div");
    ctx.window.renderStoredDifferenceCards(cards, {
      models_compared: ["Kimi", "Muse", "GLM"],
      differences: [
        { claim: "Mistral Medium 3.5 darf nicht pauschal als offen eingestuft werden.", type: "contradiction", severity: "major",
          positions: [{ models: ["Kimi"], stance: "Model A stuft Mistral insgesamt als Open-Weight ein." },
            { models: ["Muse", "GLM"], stance: "Nur ältere Mistral-Modelle sind offen." }] },
        { claim: "Model A behauptet, DeepSeek V4 Pro sei offen, während der Konsens das nicht belegt sieht.", type: "contradiction",
          severity: "minor", positions: [{ models: ["Muse", "Kimi"], stance: "Model A hält DeepSeek V4 Pro für offen." },
            { models: ["GLM"], stance: "Unklar, sagt auch Model Q." }] }
      ]
    }, { modelLabel: name => name === "Kimi" ? "Kimi K2.6" : name });
    const [first, second] = cards.querySelectorAll(".diff-card");
    expect(first.querySelector(".diff-position-stance").textContent).toBe("Kimi K2.6 stuft Mistral insgesamt als Open-Weight ein.");
    // The mapping holds across the list: the same judge run used the same labels.
    expect(second.querySelector(".diff-card-claim").textContent)
      .toBe("Kimi K2.6 behauptet, DeepSeek V4 Pro sei offen, während der Konsens das nicht belegt sieht.");
    expect(second.querySelector(".diff-card-claim").classList.contains("is-narrative")).toBe(true);
    expect([...second.querySelectorAll(".diff-position-stance")].map(el => el.textContent))
      .toEqual(["Kimi K2.6 hält DeepSeek V4 Pro für offen.", "Unklar, sagt auch Model Q."]);
  });

  it("keeps a short topic heading that merely names a model", () => {
    const ctx = boot();
    const cards = ctx.document.createElement("div");
    ctx.window.renderStoredDifferenceCards(cards, {
      models_compared: ["OpenAI", "Gemini"],
      differences: [{ claim: "Reichweite des Tesla Model S", type: "contradiction", severity: "minor",
        positions: [{ models: ["OpenAI"], stance: "Rund 600 km." }, { models: ["Gemini"], stance: "Rund 700 km." }] }]
    });
    expect(cards.querySelector(".diff-card-claim").classList.contains("is-narrative")).toBe(false);
  });

  it("gives a different emphasis no versus and no answer placeholder", () => {
    const ctx = boot();
    const cards = ctx.document.createElement("div");
    ctx.window.renderStoredDifferenceCards(cards, {
      models_compared: ["OpenAI", "Gemini"],
      differences: [{ claim: "focus", type: "emphasis",
        positions: [{ models: ["OpenAI"], stance: "The view" }, { models: ["Gemini"], stance: "", quote: "The history" }] }]
    });
    const sides = cards.querySelector(".diff-sides");
    expect(sides.className).toBe("diff-sides");
    expect(sides.querySelector(".diff-versus-mark")).toBe(null);
    expect(sides.querySelector(".diff-position-answer")).toBe(null);
    // Without a stance the quote itself is the claim, shown once.
    expect([...sides.querySelectorAll(".diff-position-stance")].map(el => el.textContent)).toEqual(["The view", "The history"]);
    expect(sides.querySelector(".diff-quote-toggle")).toBe(null);
  });

  it("opens the card of the clicked marker by data index, not by card position", () => {
    const ctx = boot();
    ctx.window.renderStoredConsensusClaims(ctx.body, MIXED, ctx.fallback, []);
    const { cards } = appendStoredCards(ctx.window, ctx.document, MIXED);
    cards.querySelectorAll(".diff-card").forEach(card => { card.open = false; });
    // The critical finding is the third entry of the data but the first card.
    ctx.body.querySelector(".cx-claim.is-major")
      .dispatchEvent(new ctx.window.MouseEvent("click", { bubbles: true }));
    ctx.document.querySelector("#claimPopover button.cx-card-title").click();
    const focused = cards.querySelector(".diff-card.is-focused");
    expect(focused.dataset.differenceIndex).toBe("2");
    expect(focused).toBe(cards.querySelector(".diff-card"));
    expect(focused.querySelector(".diff-type-tag").textContent).toBe("Critical");
    expect(focused.open).toBe(true);
  });
});
