/**
 * Audit instead of comparison (Agent): the comparison models review
 * the finished answer and mark passages with notes (agent_audit.py). The page
 * shows them with the shared markers (renderStoredAuditMarks): wrong red,
 * doubtful amber, incomplete grey, the quoted words carrying the colour, the
 * notes in the mark's card. Unmarked text stays plain: no green, no counts.
 */
import { afterEach, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

let opened = [];
afterEach(() => {
  opened.forEach(dom => dom.window.close());
  opened = [];
});

function boot(html, mode = null) {
  const env = loadScripts(["static/js/user-settings.js", "static/js/consensus-anchor.js", "static/js/consensus-insights.js"], {
    body: `<select id="consensusHighlightsSelect">
        <option value="all">All checks</option><option value="contradictions">Contradictions only</option>
        <option value="concerns">Disagreements</option><option value="critical">Critical</option><option value="none">None</option>
      </select>
      <div id="consensusAnswerBody" class="consensus-answer-body">${html}</div>
      <div id="consensusClaimsFallback" class="consensus-claims-fallback" hidden></div>
      <div id="claimPopover" hidden></div><div id="claimSheetBackdrop" hidden></div>`,
    before(window) {
      if (mode) window.localStorage.setItem("consensio.consensusHighlightMode.v1", mode);
      window.App = window.App || {};
      window.App.consensusBodyEl = () => window.document.getElementById("consensusAnswerBody");
      window.matchMedia = query => ({ matches: false, media: query, addEventListener() {}, removeEventListener() {} });
    }
  });
  opened.push(env.dom);
  env.window.Element.prototype.scrollIntoView = function () {};
  return env;
}

const ANSWER = "<p>The Eiffel Tower is 330 metres tall. It was built in 1889 for the World's Fair. "
  + "Tickets to the top cost 14 euros.</p>";
const AUDIT = {
  claims: [
    { anchor: "It was built in 1889 for the World's Fair.", kind: "incomplete", audit: true, agree: [], dissent: [
      { model: "OpenAI", kind: "incomplete", note: "Name the fair: the Exposition Universelle." }] },
    { anchor: "Tickets to the top cost 14 euros.", kind: "wrong", audit: true, agree: [], dissent: [
      { model: "Anthropic", kind: "wrong", note: "The top costs 36.10 euros.",
        source: "https://www.toureiffel.paris/en/rates", target: "14 euros" },
      { model: "OpenAI", kind: "doubtful", note: "Too low.", target: "14 euros" }] },
  ],
  unplaced: [{ model: "OpenAI", kind: "wrong", note: "Not in the answer.", quote: "It is 400 metres tall" }],
};

function marks(document) {
  return [...document.getElementById("consensusAnswerBody").querySelectorAll(".cx-claim")];
}

it("marks reviewed sentences by kind, colours the quoted words and keeps unmarked text plain", () => {
  const { window, document } = boot(ANSWER);
  const body = document.getElementById("consensusAnswerBody");
  const fallback = document.getElementById("consensusClaimsFallback");
  expect(window.renderStoredAuditMarks(body, AUDIT)).toBe(true);
  const [built, tickets] = marks(document);
  expect(built.textContent).toBe("It was built in 1889 for the World's Fair.");
  expect([...built.classList]).toEqual(expect.arrayContaining(["cx-claim", "is-minor", "is-audit"]));
  expect([...tickets.classList]).toEqual(expect.arrayContaining(["is-major", "is-audit", "has-spot"]));
  expect([...body.querySelectorAll(".cx-spot")].map(spot => spot.textContent)).toEqual(["14 euros"]);
  // No mark on the unmarked sentence, no green and no support counts.
  expect(marks(document)).toHaveLength(2);
  expect(body.querySelector(".is-unanimous, .claim-badge")).toBeNull();
  expect(tickets.getAttribute("role")).toBe("button");
  expect(tickets.getAttribute("aria-label")).toContain("Wrong: 2 reviewers object");
  // A note whose passage the answer does not hold has no mark, and nothing
  // stands for it under the answer: Notes lists it (agent-review.js).
  expect(body.textContent).not.toContain("It is 400 metres tall");
  expect(fallback.hidden).toBe(true);
  expect(fallback.childNodes).toHaveLength(0);
});

it("opens a card with every reviewer's note, its kind and its source", () => {
  const { window, document } = boot(ANSWER);
  const body = document.getElementById("consensusAnswerBody");
  window.renderStoredAuditMarks(body, AUDIT, { openNotes() { window.notesOpened = true; } });
  marks(document)[1].click();
  const pop = document.getElementById("claimPopover");
  expect(pop.hidden).toBe(false);
  const card = pop.querySelector(".cx-card-audit");
  expect(card.textContent).toContain("In the answer");
  expect(card.textContent).toContain("14 euros");
  const sides = [...card.querySelectorAll(".cx-card-side[data-kind]")];
  expect(sides.map(side => [side.dataset.kind, side.querySelector(".cx-card-claim").textContent])).toEqual([
    ["wrong", "The top costs 36.10 euros."], ["doubtful", "Too low."]]);
  expect(sides.map(side => side.querySelector(".cx-card-tag").textContent)).toEqual(["Wrong", "Doubtful"]);
  const source = card.querySelector("a.cx-card-source");
  expect(source.href).toBe("https://www.toureiffel.paris/en/rates");
  expect(source.textContent).toBe("toureiffel.paris");
  expect(sides[1].querySelector("a")).toBeNull();
  card.querySelector('.cx-card-action[data-section="differences"]').click();
  expect(window.notesOpened).toBe(true);
});

it("shows every reviewer's mark among the disagreements and only a wrong one among the contradictions", () => {
  for (const [mode, shown] of [["concerns", 2], ["all", 2], ["contradictions", 1], ["critical", 1]]) {
    const { window, document } = boot(ANSWER, mode);
    window.renderStoredAuditMarks(document.getElementById("consensusAnswerBody"), AUDIT);
    expect(marks(document).filter(mark => !mark.classList.contains("is-marker-filtered")).length, mode).toBe(shown);
  }
});

it("never links a source that is no web address", () => {
  const { window, document } = boot(ANSWER);
  const audit = { claims: [{ ...AUDIT.claims[1], dissent: [{ model: "OpenAI", kind: "wrong", note: "Bad link.",
    source: "javascript:alert(1)", target: "14 euros" }] }], unplaced: [] };
  window.renderStoredAuditMarks(document.getElementById("consensusAnswerBody"), audit);
  marks(document)[0].click();
  expect(document.querySelector("#claimPopover a.cx-card-source")).toBeNull();
});

// One mark over several sentences (agent_audit.place_marks: the same mark
// number on each) the page cannot find on every sentence: it marks the
// sentences it finds; none found, it stands only under Notes, like a note
// without a place, and nothing is listed under the answer.
it("marks the sentences of a note it finds, and lists nothing under the answer for those it does not", () => {
  const note = { model: "OpenAI", kind: "doubtful", note: "Both sentences are doubtful.", mark: 7 };
  const audit = (first, second) => ({ unplaced: [], claims: [first, second].map(anchor =>
    ({ anchor, kind: "doubtful", audit: true, agree: [], dissent: [{ ...note, target: anchor }] })) });
  const shown = (first, second) => {
    const { window, document } = boot(ANSWER);
    const fallback = document.getElementById("consensusClaimsFallback");
    window.renderStoredAuditMarks(document.getElementById("consensusAnswerBody"), audit(first, second));
    return [marks(document).length, fallback.hidden, fallback.childNodes.length];
  };
  expect(shown("The Eiffel Tower is 330 metres tall.", "It opened in 1890 for visitors.")).toEqual([1, true, 0]);
  expect(shown("The bridge is 30 metres long.", "It opened in 1890 for visitors.")).toEqual([0, true, 0]);
});

// Settings › Agent › Pass notes to the agent (agent_review_feedback.py):
// every mark names its finding. A sentence the agent corrected keeps no mark
// (the server drops its claim; a review that still holds it shows none
// either), one whose finding it disputed keeps its mark, and its card adds
// the agent's reason after the reviewers' notes.
it("keeps a disputed finding's mark with the agent's reason and shows none for a corrected one", () => {
  const { window, document } = boot(ANSWER);
  const audit = structuredClone(AUDIT);
  audit.claims[0].dissent[0].finding = "s1";
  audit.claims[1].dissent.forEach(item => { item.finding = "s2"; });
  audit.unplaced = [];
  audit.feedback = { status: "done", counts: { delivered: 2, corrected: 1, disputed: 1, cut: 0 }, findings: [
    { id: "s1", on: "answer", kind: "incomplete", voices: 1, hard: true, state: "corrected",
      before: "It was built in 1889 for the World's Fair.", after: "It was built in 1889 for the Exposition Universelle." },
    { id: "s2", on: "answer", kind: "wrong", voices: 2, hard: true, state: "disputed",
      reason: "The site lists 14 euros for the second floor, which the answer names." }] };
  const body = document.getElementById("consensusAnswerBody");
  expect(window.renderStoredAuditMarks(body, audit)).toBe(true);
  expect(marks(document).map(mark => mark.textContent)).toEqual(["Tickets to the top cost 14 euros."]);
  expect(body.textContent).not.toContain("The agent disagrees");
  marks(document)[0].click();
  const card = document.querySelector("#claimPopover .cx-card-audit");
  const sides = [...card.querySelectorAll(".cx-card-side")];
  const reply = sides.at(-1);
  expect(reply.classList.contains("cx-card-reply")).toBe(true);
  expect(reply.querySelector(".cx-card-claim").textContent).toBe("The site lists 14 euros for the second floor, which the answer names.");
  expect(reply.querySelector(".cx-card-tag").textContent).toBe("The agent disagrees");
  // The reviewers' notes stand before it, as without the setting.
  expect(card.textContent).toContain("The top costs 36.10 euros.");
});

it("draws the marks of findings the agent left open as before, and says on the card it has not checked them", () => {
  const plain = boot(ANSWER), passed = boot(ANSWER);
  const audit = structuredClone(AUDIT);
  plain.window.renderStoredAuditMarks(plain.document.getElementById("consensusAnswerBody"), AUDIT);
  // A pass that ran out of time: the same marks; the card adds one quiet line.
  audit.claims.forEach((claim, index) => claim.dissent.forEach(item => { item.finding = `s${index + 1}`; }));
  audit.feedback = { status: "done", skipped: "no_time", counts: {}, findings: [
    { id: "s1", on: "answer", kind: "incomplete", voices: 1, hard: false, state: "open", delivered: "final" },
    { id: "s2", on: "answer", kind: "wrong", voices: 2, hard: true, state: "open", delivered: "final" }] };
  passed.window.renderStoredAuditMarks(passed.document.getElementById("consensusAnswerBody"), audit);
  expect(passed.document.getElementById("consensusAnswerBody").innerHTML)
    .toBe(plain.document.getElementById("consensusAnswerBody").innerHTML);
  marks(passed.document)[1].click();
  marks(plain.document)[1].click();
  const card = passed.document.querySelector("#claimPopover .cx-card-audit");
  const note = card.querySelector(".cx-card-note");
  expect(note.textContent).toBe("Not checked by the agent: the correction did not finish.");
  expect(card.querySelector(".cx-card-reply")).toBeNull();
  note.remove();
  expect(passed.document.getElementById("claimPopover").innerHTML).toBe(plain.document.getElementById("claimPopover").innerHTML);
  // Without findings for the agent the card has no such line.
  expect(plain.document.querySelector("#claimPopover .cx-card-note")).toBeNull();
});

// One finding of the reviewers (one mark over three table cells, or a
// sentence two reviewers mark) is one passage with findings for the agent:
// one hover, one card, one tab stop, in its most serious colour. Without them
// each sentence keeps its own mark, as place_marks puts them.
const CELLS = "<table><thead><tr><th>Plan</th><th>Price</th><th>Seats</th></tr></thead>"
  + "<tbody><tr><td>Basic plan.</td><td>12 euros a month.</td><td>Two seats.</td></tr></tbody></table>";
function cellsAudit(feedback) {
  const note = { model: "DeepSeek", kind: "incomplete", note: "The price leaves out VAT.", mark: 7, finding: "s7" };
  const audit = { unplaced: [], claims: ["Basic plan.", "12 euros a month.", "Two seats."].map((anchor, index) => ({
    anchor, kind: index === 1 ? "doubtful" : "incomplete", audit: true, agree: [],
    dissent: [index === 1 ? { ...note, kind: "doubtful" } : { ...note }] })) };
  if (feedback) audit.feedback = { status: "done", counts: {}, findings: [
    { id: "s7", on: "answer", kind: "doubtful", voices: 1, hard: false, state: "open", delivered: "cut" }] };
  return audit;
}
it("shows a finding over several table cells as one passage, and leaves the marks without findings as they were", () => {
  const off = boot(CELLS);
  off.window.renderStoredAuditMarks(off.document.getElementById("consensusAnswerBody"), cellsAudit(false));
  const separate = marks(off.document);
  expect(separate).toHaveLength(3);
  expect(new Set(separate.map(mark => mark.cxGroup)).size).toBe(3);
  expect(separate.filter(mark => mark.getAttribute("role") === "button")).toHaveLength(3);

  const { window, document } = boot(CELLS);
  window.renderStoredAuditMarks(document.getElementById("consensusAnswerBody"), cellsAudit(true));
  const cells = marks(document);
  expect(cells).toHaveLength(3);
  expect(new Set(cells.map(mark => mark.cxGroup)).size).toBe(1);
  expect(cells.filter(mark => mark.getAttribute("role") === "button")).toHaveLength(1);
  expect(cells.every(mark => mark.classList.contains("is-split") && !mark.classList.contains("is-minor"))).toBe(true);
  cells[2].click();
  const card = document.querySelector("#claimPopover .cx-card-audit");
  expect(card.querySelectorAll(".cx-card-side[data-kind]")).toHaveLength(1);
  expect(card.textContent).toContain("The price leaves out VAT.");
  expect(card.querySelector(".cx-card-note").textContent).toBe("Not checked by the agent: past its limit for one answer.");
});

// The hover preview of a coloured sentence says what the agent made of its
// finding, as its card does: its reason, or that it has not checked it and
// why, where that is known. (The reason is a real one, from Max's run of
// 2026-11-13.)
const REASON = "Der neue Boden wurde 2021 beschlossen und 2023 in seinem ersten Abschnitt fertig; der Satz meint diesen Abschnitt, den die Seite des Parks so nennt.";
function verdictAudit(finding, feedback = {}) {
  const audit = structuredClone(AUDIT);
  audit.unplaced = [];
  audit.claims[1].dissent.forEach(item => { item.finding = "s2"; });
  audit.feedback = { status: "done", counts: {}, findings: finding ? [{ id: "s2", on: "answer", kind: "wrong", voices: 2,
    hard: true, ...finding }] : [], ...feedback };
  return audit;
}
function preview(audit) {
  const { window, document } = boot(ANSWER);
  window.renderStoredAuditMarks(document.getElementById("consensusAnswerBody"), audit);
  const mark = marks(document).find(span => span.textContent.startsWith("Tickets"));
  return mark.cxGroup.controls[0].preview({ interactive: false });
}
it("says on the hover preview of a mark whether and how the agent looked at its finding", () => {
  const disputed = preview(verdictAudit({ state: "disputed", delivered: "final", reason: REASON }));
  expect(disputed.querySelector(".cx-card-reply .cx-card-tag").textContent).toBe("The agent disagrees");
  expect(disputed.querySelector(".cx-card-reply .cx-card-claim").textContent).toBe(REASON);
  expect(disputed.querySelector(".cx-card-note")).toBeNull();
  const note = audit => preview(audit).querySelector(".cx-card-note").textContent;
  expect(note(verdictAudit({ state: "open", delivered: "cut" }))).toBe("Not checked by the agent: past its limit for one answer.");
  expect(note(verdictAudit({ state: "open" }))).toBe("Not checked by the agent: it can't change this spot without breaking the formatting.");
  expect(note(verdictAudit({ state: "open", delivered: "final" }, { skipped: "failed" })))
    .toBe("Not checked by the agent: the correction did not finish.");
  expect(note(verdictAudit({ state: "open", delivered: "final" }, { skipped: "stopped" })))
    .toBe("Not checked by the agent: the correction was stopped.");
  // The pass read it and left it as it was, without a word: no reason to give.
  expect(note(verdictAudit({ state: "open", delivered: "final" }))).toBe("Not checked by the agent.");
  // A run that ended in the middle of the pass.
  expect(note(verdictAudit({ state: "checking", delivered: "final" }, { status: "checking" })))
    .toBe("Not checked by the agent: the correction did not finish.");
  // Without findings for the agent: the preview as it always was.
  const plain = preview({ ...structuredClone(AUDIT), unplaced: [] });
  expect(plain.querySelector(".cx-card-note, .cx-card-reply")).toBeNull();
});

// While the agent checks findings: their sentences carry the loader's sweep,
// nothing else; the text stays as it is and nothing becomes a control.
it("sweeps exactly the sentences of the findings the agent checks", () => {
  const { window, document } = boot(ANSWER);
  const body = document.getElementById("consensusAnswerBody");
  const audit = structuredClone(AUDIT);
  audit.claims[0].dissent.forEach(item => { item.finding = "s1"; });
  audit.claims[1].dissent.forEach(item => { item.finding = "s2"; });
  const text = body.textContent;
  expect(window.renderAuditChecking(body, audit, new Set(["s2"]))).toBe(1);
  const swept = [...body.querySelectorAll(".cx-claim")];
  expect(swept.map(span => span.textContent)).toEqual(["Tickets to the top cost 14 euros."]);
  expect(swept[0].className).toBe("cx-claim is-agent-checking");
  expect(swept[0].hasAttribute("role") || swept[0].hasAttribute("tabindex")).toBe(false);
  expect(body.textContent).toBe(text);
  const still = boot(ANSWER);
  const stillBody = still.document.getElementById("consensusAnswerBody");
  still.window.renderAuditChecking(stillBody, audit, new Set(["s1", "s2"]), { still: true });
  expect([...stillBody.querySelectorAll(".cx-claim")].map(span => span.classList.contains("is-still"))).toEqual([true, true]);
});

// A table body cell is a place of its own for the agent's correction: the
// sweep stays inside the cell it checks, and the table keeps its cells.
it("sweeps a table cell the agent checks, and only that cell", () => {
  const { window, document } = boot(CELLS);
  const body = document.getElementById("consensusAnswerBody");
  const cells = [...body.querySelectorAll("th, td")];
  const audit = { unplaced: [], claims: [{ anchor: "12 euros a month.", kind: "wrong", audit: true, agree: [],
    dissent: [{ model: "OpenAI", kind: "wrong", note: "It costs 15 euros.", mark: 1, finding: "s1" }] }] };
  expect(window.renderAuditChecking(body, audit, new Set(["s1"]))).toBe(1);
  const swept = [...body.querySelectorAll(".cx-claim.is-agent-checking")];
  expect(swept.map(span => [span.textContent, span.closest("td")?.cellIndex])).toEqual([["12 euros a month.", 1]]);
  expect([...body.querySelectorAll("th, td")]).toEqual(cells);
  expect([...body.querySelectorAll("tr")].map(row => row.cells.length)).toEqual([3, 3]);
});
