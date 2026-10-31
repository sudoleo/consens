// static/demo.js

window.App.state.set("spinnerHTML", `
  <span class="thinking-wrap" role="status" aria-live="polite" aria-busy="true">
    <span class="thinking typing-indicator" data-text="Typing" aria-label="Typing">Typing<span class="typing-dots" aria-hidden="true"><span>.</span><span>.</span><span>.</span></span></span>
  </span>
`, "runUi");
if (!Array.isArray(window.currentEvidenceSources)) {
  window.App.state.set("currentEvidenceSources", [], "evidence");
}

/* === DEMO: Data & Utilities =======================================
   Das Szenario ist eine Entscheidung, fuer die man sich im echten Leben
   eine zweite und dritte Meinung holt: eine Waermepumpe im Haus von 1978
   mit den alten Heizkoerpern. Sie kostet fuenfstellig, und die Fachleute
   sind sich wirklich uneins. Seit 2026-10-31 spielt die Demo den einen
   Modus des Agenten: Eine KI arbeitet, die gewaehlten KIs folgen ihrer
   Arbeit und pruefen ihre Antwort. Der Agent fragt sie einmal (hier lohnen
   unabhaengige Antworten), schreibt die Antwort selbst, und die Pruefer
   haben drei Anmerkungen: eine falsche Stelle (der Agent hat die Hausdaten
   der Frage verwechselt), eine zweifelhafte und eine unvollstaendige. Kein
   Score. Quellenlisten gibt es bewusst nicht: erfundene Belege waeren die
   schlechtere Demo.
   ================================================================= */
// A German page shows the scenario in German: every text of it through the
// dictionary (docs/i18n.md), markup through i18n.js's own rules. Anchors and
// quoted words are entries of their own, each a passage of the German
// answer, so the marks still find their place. Names and numbers have no
// entry and stay. Values the app reads are no text and stay English: a
// note of kind "falsch" is none, and its red mark would be gone.
const DEMO_VALUE_FIELDS = new Set(["kind", "model", "models", "provider"]);
function demoInPageLanguage(value) {
  const t = window.App?.t;
  if (window.App?.lang !== "de" || !t) return value;
  const markup = text => {
    const holder = document.createElement("div");
    holder.innerHTML = text;
    window.App.i18n?.translate?.(holder);
    return holder.innerHTML;
  };
  const walk = item => {
    if (typeof item === "string") {
      if (/<[a-z][^>]*>/i.test(item)) return markup(item);
      return item.split("\n\n").map(part => t(part)).join("\n\n");
    }
    if (Array.isArray(item)) return item.map(walk);
    if (item && typeof item === "object") return Object.fromEntries(Object.entries(item).map(([key, entry]) =>
      [key, DEMO_VALUE_FIELDS.has(key) ? entry : walk(entry)]));
    return item;
  };
  return walk(value);
}

const DEMO_SCENARIO_PROMPT = demoInPageLanguage(
  "Our house is from 1978 and still has the original radiators. Can a heat pump heat it properly, or do we need new radiators first?\n\n" +
  "Detached, 140 m², walls insulated in 2015, original double glazing. The gas boiler currently runs at 70 °C.");

// Die Hausdaten werden nicht getippt, sondern eingefuegt, so wie man sie
// aus einer Notiz oder dem Energieausweis uebernimmt.
const DEMO_TYPED_QUESTION = DEMO_SCENARIO_PROMPT.split("\n")[0];

const DEMO_MODELS = ["OpenAI", "Mistral", "Anthropic", "Gemini", "DeepSeek", "Grok"];

const DEMO_DATA = demoInPageLanguage({
  delays: { OpenAI: 1400, Mistral: 2500, Anthropic: 2900, Gemini: 3600, DeepSeek: 4300, Grok: 5000 },
  responses: {
    OpenAI:
`<div class="ai-block">
  <p>Short version: very likely yes, and probably without replacing most of the radiators.</p>
  <h4>Why the house is a better candidate than it sounds</h4>
  <ul>
    <li>The 2015 wall insulation matters more than the 1978 build date. Heat loss, not age, decides whether a heat pump copes.</li>
    <li>Radiators from the 1970s were sized for an uninsulated house, so many of them are now larger than the room needs.</li>
  </ul>
  <h4>What I would do</h4>
  <ul>
    <li>Get a room-by-room heat-loss calculation before anyone quotes a size.</li>
    <li>This winter, turn the boiler down to 50 °C for a cold week. Rooms that stay warm keep their radiators.</li>
    <li>Replace only the radiators in rooms that fall short, and size the heat pump from the calculation, not from the old boiler.</li>
  </ul>
  <h4>Where I would not chase the last degree</h4>
  <p>Running at 55 °C instead of 45 °C costs a few percent on the annual bill, and replacing every radiator to get there costs more than that difference will save in a decade.</p>
  <p>I would also take the gas boiler out completely. A backup boiler keeps a gas connection, a standing charge and a second service visit for the few days a well-sized heat pump handles anyway.</p>
</div>`,

    Mistral:
`<div class="ai-block">
  <p>Work through it in this order.</p>
  <ol>
    <li>Heat-loss calculation for every room. Without it, every answer you get, including this one, is a guess.</li>
    <li>Run the boiler at 50 °C for a cold week, so you know which rooms are the weakest before anyone quotes.</li>
    <li>Replace the radiators in every room you use daily with larger or fan-assisted ones. That is what lets the heat pump run at 45 °C or below.</li>
    <li>Size the heat pump from the calculation. The old boiler’s 24 kW says nothing about what the house needs.</li>
    <li>Keep the gas boiler connected for the first winter as a backup. If the heat pump never needs it, remove it the following summer.</li>
  </ol>
  <p>Every degree of flow temperature costs roughly two to three percent of efficiency. The radiators are a one-off cost; the flow temperature is paid every winter.</p>
</div>`,

    Anthropic:
`<div class="ai-block">
  <p>What actually decides this</p>
  <p>The question is not whether the radiators are old but whether they can deliver each room’s heat loss at a low flow temperature. A radiator does not care how old it is; it cares how warm the water is. At 70 °C your radiators deliver roughly twice what they deliver at 50 °C, which is why a house that is warm today can still be cold with a heat pump.</p>
  <ul>
    <li>Start with a room-by-room heat-loss calculation. The 2015 wall insulation probably brought the total down a lot, but the calculation is what tells you where.</li>
    <li>Run the boiler at 50 °C for a cold week and note which rooms stay warm. Those radiators can stay.</li>
    <li>Plan for 45 °C rather than 55 °C. The efficiency difference is around a quarter, and you pay it every winter for twenty years.</li>
    <li>Size the heat pump from the calculation, not from the boiler it replaces.</li>
    <li>Do not keep the gas boiler as a backup. Two systems mean two service contracts, and a backup tends to become the system that runs whenever it is cold.</li>
  </ul>
  <p>The radiators that pass your test are often more than people expect, because 1970s radiators were sized for a house with no insulation at all.</p>
</div>`,

    Gemini:
`<div class="ai-block">
  <p>How it looks from the installer’s side</p>
  <ul>
    <li><b>The 1978 build date</b>: matters less than you think. With the walls insulated in 2015, the house loses far less heat than it was designed for.</li>
    <li><b>The original radiators</b>: often oversized for today’s heat loss, because they were chosen for an uninsulated house. Many will cope at 55 °C.</li>
    <li><b>The test you can do now</b>: set the boiler to 50 °C on a cold week. Every room that stays warm is a room you do not need to touch.</li>
    <li><b>The quote</b>: ask for a room-by-room heat-loss calculation, and for the heat pump to be sized from it.</li>
    <li><b>The flow temperature</b>: 55 °C is a reasonable target here. The step down to 45 °C is worth a few percent, and it usually means replacing radiators that work.</li>
    <li><b>The gas boiler</b>: keeping it as a backup for the coldest days is a cheap safety net in the first winter, while you learn how the house behaves.</li>
  </ul>
  <p>What is missing from the question: the hot water. A cylinder that is reheated to 60 °C for hygiene can cost more efficiency than the radiator question, and nobody asks about it.</p>
</div>`,

    DeepSeek:
`<div class="ai-block">
  <p>Before you commit</p>
  <h4>Check</h4>
  <ul>
    <li>Has anyone calculated the heat loss room by room? If the installer sized it from your boiler, ask again.</li>
    <li>What is the heat pump’s efficiency at 35 °C and at 55 °C? The datasheet gives both, and the gap is usually around a quarter.</li>
  </ul>
  <h4>Fix</h4>
  <ul>
    <li>Size the heat pump from the calculation, not from the old boiler’s output.</li>
    <li>Replace the radiators in the rooms you heat most, so the system can run at 45 °C or below.</li>
    <li>Insulate the loft if it has not been done. It is the cheapest kilowatt you will ever save.</li>
  </ul>
  <h4>Do not</h4>
  <ul>
    <li>Do not rely on a boiler test alone. A boiler at 50 °C on a mild day says little about a heat pump at minus ten.</li>
    <li>Do not keep the gas boiler as a backup. You keep the standing charge and lose the reason you switched.</li>
  </ul>
</div>`,

    Grok:
`<div class="ai-block">
  <p>Plain take: yes, it will work, and the radiator panic is mostly overblown.</p>
  <ul>
    <li>Your radiators were sized for 1978. Your walls are from 2015. That gap is your margin.</li>
    <li>Turn the boiler down to 50 °C on the next cold week. If you are comfortable, you have your answer for most rooms.</li>
    <li>Swap the one or two radiators that cannot keep up, ideally for fan-assisted ones, and leave the rest alone.</li>
    <li>Run it at 55 °C if that keeps the house warm. Chasing 45 °C with new radiators everywhere saves less than the radiators cost.</li>
    <li>Keep the gas boiler for one winter. If the heat pump never calls for it, take it out in spring.</li>
  </ul>
  <p>Two things I would insist on: a room-by-room heat-loss calculation, and a heat pump sized from it rather than from the old boiler. An oversized heat pump cycles on and off, and that wears it out faster than a cold January.</p>
</div>`
  },
  // The agent's own answer, written after it asked the AIs once. The first
  // line is its verdict (bold in the chat, demoAgentAnswer). One sentence
  // mixes up the house's data (the walls were insulated in 2015, the
  // windows are the original glazing): the reviewers' wrong note is about it.
  answer:
`<div class="ai-answer">
  <p>Probably yes, with a few radiators changed, not all of them.</p>
  <p>The walls and windows were renewed in 2015, and that matters more than the year the house was built. What nobody can tell you from here is which rooms fall short, and that is the whole question.</p>
  <h4>Do this first</h4>
  <ul>
    <li>Get a room-by-room heat-loss calculation before anyone quotes a heat pump size.</li>
    <li>Test it this winter: turn the boiler down to 50 °C for a cold week and note which rooms stay warm.</li>
    <li>Rooms that stay warm keep their radiators; only the rooms that fall short need larger or fan-assisted ones.</li>
    <li>Have the heat pump sized from the calculation, not from the old boiler’s output.</li>
  </ul>
  <h4>Decide for yourself</h4>
  <ul>
    <li>The answers I asked for split on the target flow temperature: keep most radiators and run at 55 °C, or replace more of them to run at 45 °C or below.</li>
    <li>They also disagree on what that costs you: estimates for the efficiency gap between 55 °C and 45 °C range from a few percent to about a quarter.</li>
  </ul>
  <p>Both come down to the same trade: what you spend once on radiators against what you spend every winter on electricity.</p>
</div>`,

  // What the reviewers note on that answer, in the review's own shape
  // (agent_audit.place_marks): the sentence it concerns (anchor), the
  // quoted words in it (target), its kind and the reviewer's note. Each
  // reviewer one note; a reviewer the Daily lineup does not have stays out.
  notes: [
    {
      model: "OpenAI",
      kind: "wrong",
      anchor: "The walls and windows were renewed in 2015, and that matters more than the year the house was built.",
      target: "walls and windows were renewed in 2015",
      note: "The question says only the walls were insulated in 2015. The windows are still the original double glazing."
    },
    {
      model: "DeepSeek",
      kind: "doubtful",
      anchor: "Test it this winter: turn the boiler down to 50 °C for a cold week and note which rooms stay warm.",
      target: "for a cold week",
      note: "A boiler at 50 °C on a mild day says little about a heat pump at minus ten. Run the test in the coldest week you get, and let the calculation decide."
    },
    {
      model: "Anthropic",
      kind: "incomplete",
      anchor: "Have the heat pump sized from the calculation, not from the old boiler’s output.",
      target: "Have the heat pump sized from the calculation",
      note: "Hot water is missing. A cylinder reheated to 60 °C for hygiene changes what the heat pump has to deliver, so ask how the quote handles it."
    }
  ]
});

// Six authored viewpoints are instantiated for the configured Daily families.
// Keep every answer and reviewer's note attached to the same viewpoint if an
// admin changes a preset family (for example Claude -> Kimi). These are
// local demo fixtures.
function buildDemoDataForModels(models) {
  const replacements = models.filter(model => !DEMO_MODELS.includes(model));
  const mapping = Object.fromEntries(DEMO_MODELS.map(model => [model,
    models.includes(model) ? model : replacements.shift()]));
  function remap(value) {
    if (typeof value === 'string') return mapping[value] || value;
    if (Array.isArray(value)) return value.map(remap);
    if (value && typeof value === 'object') return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [mapping[key] || key, remap(item)]));
    return value;
  }
  return remap(DEMO_DATA);
}
let activeDemoData = DEMO_DATA;
let activeDemoModels = DEMO_MODELS;

/* === DEMO: Timing & Typing Configuration =============================== */
const DEMO_PHASES = {
  preType: true,
  order: ["OpenAI", "Anthropic", "Gemini", "Mistral", "DeepSeek", "Grok"],
  // Obergrenze fuer die getippte Frage (ohne den eingefuegten Entwurf).
  typeChars: 140,
  typeSpeed: 40,
  gapBetweenModels: 540,
  pauseAfterTypingAll: 650
};

const DEMO_DELAY_BOOST_MS = 1800;

Object.keys(activeDemoData.delays).forEach(key => {
  activeDemoData.delays[key] = (activeDemoData.delays[key] || 1500) + DEMO_DELAY_BOOST_MS;
});

const MODEL_TO_BOX = {
  OpenAI: "openaiResponse",
  Mistral: "mistralResponse",
  Anthropic: "claudeResponse",
  Gemini: "geminiResponse",
  DeepSeek: "deepseekResponse",
  Grok: "grokResponse"
};

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

// Staffel-Startzeiten + Tempo für das Token-Streaming der Demo-Antworten.
const DEMO_STREAM_STARTS = { OpenAI: 500, Anthropic: 1150, Gemini: 1800, Mistral: 2450, DeepSeek: 3100, Grok: 3750 };
const DEMO_RESPONSE_STREAM = { wordsPerTick: 2, tickMs: 55 };

// Läuft hoch, sobald ein neuer Demo-Durchlauf startet, damit alte
// Streaming-Timer aus einem vorherigen Lauf sauber abbrechen.
let demoRunId = 0;

// Zerlegt eine HTML-Antwort in Tokens: Tags bleiben ganz, Text wird in
// Wörter/Whitespace gesplittet, damit beim schrittweisen Aufbau nie ein
// halbes Tag im DOM landet.
function tokenizeForStream(html) {
  const tokens = [];
  const re = /<[^>]+>|[^<]+/g;
  let match;
  while ((match = re.exec(html))) {
    const part = match[0];
    if (part[0] === "<") {
      tokens.push(part);
    } else {
      const pieces = part.match(/\s+|[^\s]+/g) || [];
      for (const piece of pieces) tokens.push(piece);
    }
  }
  return tokens;
}

// Convert authored demo fragments into the same Markdown payload as a real
// model. Raw spinner/HTML markup must never become an answer in the reader.
function demoResponseMarkdown(html) {
  const fragment = document.createElement('div');
  fragment.innerHTML = html;
  function read(node) {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent.trim() ? node.textContent.replace(/\s+/g, ' ') : '';
    const text = Array.from(node.childNodes).map(read).join('');
    const tag = node.tagName?.toLowerCase();
    if (/^h[1-6]$/.test(tag || '')) return `\n\n${'#'.repeat(Number(tag[1]))} ${text.trim()}\n\n`;
    if (tag === 'li') {
      const marker = node.parentElement?.tagName === 'OL'
        ? `${Array.from(node.parentElement.children).indexOf(node) + 1}.` : '-';
      return `${marker} ${text.trim()}\n`;
    }
    if (['p', 'ul', 'ol', 'div'].includes(tag)) return `\n\n${text.trim()}\n\n`;
    if (tag === 'br') return '\n';
    if (tag === 'b' || tag === 'strong') return `**${text}**`;
    if (tag === 'em' || tag === 'i') return `*${text}*`;
    return text;
  }
  return read(fragment).replace(/\n{3,}/g, '\n\n').trim();
}

// Baut die Antwort wortweise auf – wie ein echter Streaming-Response.
// Tags zählen nicht gegen das Wort-Budget, der Browser schließt offene
// Tags beim Zuweisen von innerHTML automatisch, daher bleibt das Markup gültig.
function streamDemoInto(outputEl, html, runId, opts = {}) {
  return new Promise(resolve => {
    if (!outputEl) { resolve(); return; }
    const wordsPerTick = opts.wordsPerTick || 3;
    const tickMs = opts.tickMs || 38;
    const tokens = tokenizeForStream(html || "");
    let index = 0;
    let acc = "";
    outputEl.innerHTML = "";
    outputEl.classList.add("is-streaming");

    const finish = () => {
      outputEl.classList.remove("is-streaming");
      resolve();
    };

    const tick = () => {
      if (runId !== demoRunId) { finish(); return; }
      let added = 0;
      while (index < tokens.length && added < wordsPerTick) {
        const token = tokens[index++];
        acc += token;
        if (token[0] !== "<" && token.trim()) added++;
      }
      outputEl.innerHTML = acc;
      const box = outputEl.closest('.response-box');
      if (box) {
        box.dataset.responseState = 'streaming';
        box.dataset.consensusAnswer = demoResponseMarkdown(acc);
      }
      if (typeof outputEl.scrollTop === "number") outputEl.scrollTop = outputEl.scrollHeight;
      if (index < tokens.length) {
        setTimeout(tick, tickMs);
      } else {
        finish();
      }
    };

    tick();
  });
}

function getDemoStorage() {
  try {
    return window.localStorage || null;
  } catch (e) {
    return null;
  }
}

function showPostDemoLoginPrompt() {
  const prompt = document.getElementById("postDemoLoginPrompt");
  if (!prompt || window.auth?.currentUser) return;

  prompt.hidden = false;
  prompt.classList.remove("is-visible");
  requestAnimationFrame(() => prompt.classList.add("is-visible"));
  window.trackAppEvent?.("app_demo_login_prompt_shown");
}

function shouldAvoidDemoInputFocus() {
  return window.matchMedia?.("(hover: none) and (pointer: coarse)")?.matches ||
    window.matchMedia?.("(max-width: 768px)")?.matches;
}

async function typeIntoInput(inputEl, text, speed = 14, options = {}) {
  if (!inputEl) return;
  const allowFocus = options.allowFocus ?? !shouldAvoidDemoInputFocus();
  if (allowFocus) {
    inputEl.focus({ preventScroll: true });
  } else if (document.activeElement === inputEl) {
    inputEl.blur();
  }

  inputEl.value = "";
  inputEl.dispatchEvent(new Event("input", { bubbles: true }));
  for (let i = 0; i < text.length; i++) {
    inputEl.value += text[i];
    inputEl.dispatchEvent(new Event("input", { bubbles: true }));
    const jitter = Math.random() * 6 - 3;
    await sleep(Math.max(4, speed + jitter));
    if (typeof inputEl.scrollTop === "number") inputEl.scrollTop = inputEl.scrollHeight;
  }

  if (!allowFocus && document.activeElement === inputEl) {
    inputEl.blur();
  }
}

function getBox(model) {
  const id = window.App.modelPrefs.find(pref => pref.key === model)?.responseId || MODEL_TO_BOX[model];
  const box = document.getElementById(id);
  if (!box || box.classList.contains("excluded") || box.style.display === "none") return null;
  return box;
}

function setSpinnerEl(box) {
  delete box.dataset.consensusAnswer;
  delete box.dataset.responseError;
  delete box.dataset.responseSkipped;
  box.dataset.responseState = 'pending';
  const p = box.querySelector(".collapsible-content");
  if (p) p.innerHTML = window.spinnerHTML;
}

window.setSpinnerEl = setSpinnerEl;

function renderDemoModelResponse(model, outputEl) {
  const markdown = demoResponseMarkdown(activeDemoData.responses[model] || "");
  const box = outputEl.closest('.response-box');
  if (box) box.dataset.responseState = 'complete';
  // Ohne Quellen, aber ueber denselben Weg wie eine echte Antwort: der
  // Renderer legt nebenbei die Kopier-/Bestantwort-Daten am Kasten ab.
  if (window.renderModelResponseWithSources) {
    window.renderModelResponseWithSources(outputEl, markdown, []);
    return;
  }
  if (window.injectMarkdown) window.injectMarkdown(outputEl, markdown);
}

/* === DEMO: Agent turn ===================================================
   Agent is where every question starts, so the demo plays an Agent turn on
   the real Agent surfaces, in the one mode every account has since
   2026-10-31: one AI does the work, the AIs of the Daily lineup follow it
   and review its answer. The activity line and its notes
   (agent-activity.js), the reviewers and the AIs it asks beside the clock
   and in the panel (App.agentDelegation.demo, sessions of kind "audit" and
   "comparison"), the streamed answer (markdown-stream.js), then the review
   of exactly that text (agent-review.js, a review of mode "audit"): the
   reviewers' marks in the answer, Notes and the Answers of the AIs it
   asked under it. No score. The run is local and scripted from the same
   fixtures as the Compare demo: no request, no bookmark, no vote.
   agent-chat.js keeps the answer panel on screen while the demo owns it
   (App.agentChat.demoView), also for guests.
   ======================================================================= */
const DEMO_AGENT_ID = "demo";
const DEMO_AGENT_HASH = "demo-answer-v1";
const DEMO_AGENT_STEPS = {
  plan: 900,            // first progress note; the reviewers start following
  round: 2300,          // the reviewers' first round on the work so far
  compare: 2700,        // compare_models: the agent asks the AIs once
  modelSpread: 4400,    // the last answer lands this long after compare
  afterCompare: 900,    // progress note, then the answer starts streaming
  review: 2600          // the reviewers' final review of the fixed answer
};
const DEMO_AGENT_STREAM = { wordsPerTick: 3, tickMs: 42 };
const DEMO_AGENT_NOTES = demoInPageLanguage({
  plan: "Whether this works depends on the heat loss of each room, not on the year the house was built. Installers genuinely disagree here, so I will ask the other AIs for independent answers before I answer.",
  compared: "They agree it can work. They split on the flow temperature and on what it costs, so the answer has to say so instead of picking a side."
});
// A reviewer's round without a note, in the words of agent_audit.review_text.
// The panel compares it as a value (agent-delegation.js NO_OBJECTION), so it
// is never translated.
const DEMO_NO_OBJECTIONS = "No objections.";

// The agent writes its own answer: the fixture as Markdown, the verdict in
// its first line bold.
function demoAgentAnswer() {
  return demoResponseMarkdown(activeDemoData.answer || "").replace(/^(.+)$/m, "**$1**");
}
function demoAgentModels() {
  return activeDemoModels.map(key => {
    const pref = window.App.modelPrefs.find(item => item.key === key);
    const select = pref && document.getElementById(pref.selectId);
    const option = select?.selectedOptions?.[0];
    return {
      key,
      provider: pref?.provider || key.toLowerCase(),
      label: (option?.textContent || "").trim() || pref?.label || key,
      model: select?.value || "",
      text: demoResponseMarkdown(activeDemoData.responses[key] || "")
    };
  });
}
// The reviewers' notes of the lineup on screen, numbered like the review's
// marks (agent_audit.place_marks `mark`).
function demoAgentNotes(models) {
  const keys = new Set(models.map(model => model.key));
  return (activeDemoData.notes || []).filter(note => keys.has(note.model))
    .map((note, index) => ({ ...note, mark: index + 1 }));
}
// compare_models as the review carries it (agent_comparison.py _rebuild):
// running until the first answer, partial while others still answer.
function demoAgentComparison(models, answered) {
  const pending = models.filter(model => !answered.includes(model));
  return {
    id: "demo-comparison",
    question: DEMO_TYPED_QUESTION,
    context: DEMO_SCENARIO_PROMPT.split("\n\n")[1] || "",
    asked: models.map(model => model.provider),
    status: !answered.length ? "running" : pending.length ? "partial" : "succeeded",
    answers: answered.map(model => ({
      provider: model.provider, provider_label: model.key,
      model: { label: model.label, model: model.model }, text: model.text, sources: []
    })),
    failed_models: [],
    ...(pending.length ? { pending_models: pending.map(model => ({ label: model.label, model: model.model })) } : {})
  };
}
// The review a real turn carries (agent_review, agent_comparison.snapshot):
// mode "audit", the reviewers, the comparison, once fixed the answer's
// version, and once reviewed the notes on its sentences.
function demoAgentReview({ models, comparison, status, answer = "", notes = null }) {
  const review = {
    version: 1, mode: "audit", status, answer_version: 0, answer_hash: "",
    comparisons: comparison ? [comparison] : [], versions: [],
    audit: {
      reviewers: models.map(model => ({
        provider: model.provider, provider_label: model.key,
        model: { label: model.label, model: model.model }, status: notes ? "completed" : "running"
      }))
    }
  };
  if (answer) {
    review.answer_version = 1;
    review.answer_hash = DEMO_AGENT_HASH;
    review.versions = [{ id: 1, text: answer, hash: DEMO_AGENT_HASH, status }];
  }
  if (notes) {
    const claims = [];
    for (const note of notes) {
      let claim = claims.find(item => item.anchor === note.anchor);
      if (!claim) {
        claim = { anchor: note.anchor, audit: true, kind: note.kind, agree: [], dissent: [] };
        claims.push(claim);
      }
      claim.dissent.push({ model: note.model, kind: note.kind, note: note.note, target: note.target, mark: note.mark });
    }
    Object.assign(review.audit, { claims, unplaced: [], process: [] });
  }
  return review;
}
// renderAnswer() in agent-chat.js, for a run that is not in the registry:
// the growing text through the streaming renderer, the final text once.
function showDemoAgentAnswer(body, text, streaming) {
  if (!body) return;
  const mode = streaming && window.renderMarkdownStream ? "stream" : "full";
  const entering = !body.dataset.markdown?.trim() && Boolean(text.trim());
  body.dataset.markdown = text;
  body.dataset.renderMode = mode;
  if (mode === "stream") window.renderMarkdownStream(body, text);
  else {
    window.resetMarkdownStream?.(body);
    window.injectMarkdown?.(body, text, []);
  }
  body._agentRenderSerial = (body._agentRenderSerial || 0) + 1;
  if (entering) window.App.agentActivity?.reveal(body);
}
function clearDemoAgentAnswer() {
  const body = document.getElementById("agentAnswerBody");
  if (!body) return;
  window.resetMarkdownStream?.(body);
  delete body.dataset.markdown;
  delete body.dataset.renderMode;
  body.classList.remove("is-answer-checking", "is-answer-check-done");
  body.replaceChildren();
  window.App.agentReview?.render(body, null, { key: DEMO_AGENT_ID });
  window.App.agentDelegation?.demo?.(null);
}
// The calls behind the turn, as agent-delegation.js shows a real one: the
// reviewers from the first step (one session each, its rounds and its final
// review), the AIs the agent asked once it asks; a reviewer and its answer
// share one icon. Token counts are estimated from the fixture texts (about
// 4 characters per token), so the panel reads like a run without claiming a
// measured one.
const DEMO_AGENT_PROMPT_TOKENS = 1180;
function demoAgentUsage(input, output) {
  return { input_tokens: DEMO_AGENT_PROMPT_TOKENS + Math.round(input.length / 4),
    output_tokens: Math.round(output.length / 4), complete: true };
}
// A reviewer's final review in the words of agent_audit.review_text.
function demoFinalReview(notes) {
  return notes.length
    ? notes.map(note => `- **${note.kind}** · “${note.target}”: ${note.note}`).join("\n")
    : DEMO_NO_OBJECTIONS;
}
function demoAgentCalls({ models, rounds, asked, answered, answer, reviewed, notes }) {
  const reviewers = models.map(model => {
    const own = notes.filter(note => note.model === model.key);
    const messages = [...rounds, ...(reviewed ? [{ kind: "result", text: demoFinalReview(own), created_at: reviewed }] : [])];
    return {
      id: `demo-review-${model.key}`, kind: "audit", title: `Review · ${model.label}`,
      status: reviewed ? "completed" : "working", created_at: rounds.started,
      model: { label: model.label, model: model.model, provider: model.key }, messages,
      usage: reviewed ? demoAgentUsage(answer, messages.at(-1).text) : null
    };
  });
  const comparisons = asked ? models.map(model => {
    const done = answered.includes(model);
    return {
      id: `demo-${model.key}`, kind: "comparison", title: `Comparison 1 · ${model.label}`,
      status: done ? "completed" : "working", created_at: asked,
      model: { label: model.label, model: model.model, provider: model.key },
      text: done ? model.text : "", usage: done ? demoAgentUsage(DEMO_SCENARIO_PROMPT, model.text) : null
    };
  }) : [];
  const metered = [...reviewers, ...comparisons].filter(call => call.usage);
  const usage = metered.length ? {
    input_tokens: metered.reduce((n, call) => n + call.usage.input_tokens, 0),
    output_tokens: metered.reduce((n, call) => n + call.usage.output_tokens, 0),
    complete: true, measured_calls: metered.length, unmetered_calls: 0
  } : null;
  return { agents: [...reviewers, ...comparisons], usage };
}

async function runAgentDemoFlow() {
  const App = window.App;
  window.hideConsensusOutput?.();
  const runId = ++demoRunId;
  const live = () => runId === demoRunId;
  const sendBtn = document.getElementById("sendButton");
  if (sendBtn) sendBtn.disabled = true;
  App.state.set("currentEvidenceSources", [], "evidence");

  const qi = document.getElementById("questionInput");
  if (DEMO_PHASES.preType && qi) {
    await typeIntoInput(qi, DEMO_TYPED_QUESTION.slice(0, DEMO_PHASES.typeChars), DEMO_PHASES.typeSpeed);
    await sleep(340);
    qi.value = DEMO_SCENARIO_PROMPT;
    qi.dispatchEvent(new Event("input", { bubbles: true }));
    await sleep(DEMO_PHASES.pauseAfterTypingAll);
  }
  if (!live()) return;

  // Sent: the question moves into the thread, the composer empties, and the
  // Agent's answer surface takes over below it. As in a real chat the field
  // is typed into where it stands and only glides down when it is sent;
  // leaving the hero before typing made it jump down first.
  window.exitHeroMode?.();
  App.state.set("lastQuestion", DEMO_SCENARIO_PROMPT, "run");
  App.setThreadQuestion?.(DEMO_SCENARIO_PROMPT);
  if (qi) {
    qi.value = "";
    qi.dispatchEvent(new Event("input", { bubbles: true }));
    window.syncDemoChipState?.();
  }
  clearDemoAgentAnswer();
  const host = App.agentChat?.demoView?.(true);
  const body = document.getElementById("agentAnswerBody");
  const models = demoAgentModels();
  const notes = demoAgentNotes(models);
  const answer = demoAgentAnswer();
  const started = Date.now();
  const iso = ms => new Date(started + ms).toISOString();
  const events = [];
  // The reviewers' rounds on the work so far; `started` dates their sessions.
  const rounds = [];
  rounds.started = iso(DEMO_AGENT_STEPS.plan);
  const answered = [];
  let review = null;
  let answerText = "";
  let running = true;
  let following = false;
  let asked = "";
  let reviewed = "";

  const paint = () => {
    if (!live() || !host) return;
    App.agentActivity?.render(host, {
      events, review, running, answerText,
      responding: Boolean(answerText),
      status: running ? "running" : "succeeded",
      elapsedMs: Date.now() - started
    });
    // The reviewers follow from the first step, as in a real turn.
    if (following && document.body.classList.contains("agent-demo-active")) {
      App.agentDelegation?.demo?.({ turnId: `demo-${runId}`, running,
        ...demoAgentCalls({ models, rounds, asked, answered, answer, reviewed, notes: reviewed ? notes : [] }) });
    }
  };
  const at = async ms => {
    const wait = started + ms - Date.now();
    if (wait > 0) await sleep(wait);
    return live();
  };
  const round = ms => rounds.push({ kind: "round", text: DEMO_NO_OBJECTIONS, created_at: iso(ms) });
  paint();

  if (!await at(DEMO_AGENT_STEPS.plan)) return;
  events.push({ version: 1, kind: "progress", id: "demo-plan", text: DEMO_AGENT_NOTES.plan });
  following = true;
  paint();
  if (!await at(DEMO_AGENT_STEPS.round)) return;
  round(DEMO_AGENT_STEPS.round);
  paint();

  // compare_models: the AIs answer independently, each on its own beat.
  if (!await at(DEMO_AGENT_STEPS.compare)) return;
  const compareTool = { version: 1, kind: "tool", id: "demo-compare", name: "compare_models", status: "running" };
  events.push(compareTool);
  asked = iso(DEMO_AGENT_STEPS.compare);
  review = demoAgentReview({ models, comparison: demoAgentComparison(models, answered), status: "required" });
  paint();
  const order = DEMO_PHASES.order.filter(key => models.some(model => model.key === key))
    .concat(models.map(model => model.key).filter(key => !DEMO_PHASES.order.includes(key)));
  for (let i = 0; i < order.length; i++) {
    const landing = DEMO_AGENT_STEPS.compare + Math.round(DEMO_AGENT_STEPS.modelSpread * ((i + 1) / order.length) ** 1.15);
    if (!await at(landing)) return;
    answered.push(models.find(model => model.key === order[i]));
    review = demoAgentReview({ models, comparison: demoAgentComparison(models, answered), status: "required" });
    paint();
  }
  compareTool.status = "succeeded";
  events.push({ version: 1, kind: "progress", id: "demo-compared", text: DEMO_AGENT_NOTES.compared });
  round(DEMO_AGENT_STEPS.compare + DEMO_AGENT_STEPS.modelSpread);
  paint();

  // The answer, written in its own step after the comparison.
  if (!await at(DEMO_AGENT_STEPS.compare + DEMO_AGENT_STEPS.modelSpread + DEMO_AGENT_STEPS.afterCompare)) return;
  events.push({ version: 1, kind: "status", id: "demo-status", status: "responding" });
  const tokens = answer.match(/\s+|[^\s]+/g) || [];
  let index = 0;
  while (index < tokens.length) {
    let added = 0;
    while (index < tokens.length && added < DEMO_AGENT_STREAM.wordsPerTick) {
      const token = tokens[index++];
      answerText += token;
      if (token.trim()) added++;
    }
    showDemoAgentAnswer(body, answerText, true);
    paint();
    await sleep(DEMO_AGENT_STREAM.tickMs);
    if (!live()) return;
  }
  showDemoAgentAnswer(body, answerText, false);

  // The reviewers review exactly this text: the row under it stands with
  // Notes waiting, a quiet sheen passes over the answer (agent-chat.js
  // setAnswerChecking), the head says "Reviewing".
  const comparison = demoAgentComparison(models, answered);
  const reviewTool = { version: 1, kind: "tool", id: "demo-review", name: "audit_answer", status: "running" };
  events.push(reviewTool);
  review = demoAgentReview({ models, comparison, status: "running", answer: answerText });
  body?.classList.add("is-answer-checking");
  App.agentReview?.render(body, review, { key: DEMO_AGENT_ID, question: DEMO_SCENARIO_PROMPT });
  paint();
  await sleep(DEMO_AGENT_STEPS.review);
  if (!live()) return;

  reviewTool.status = "succeeded";
  reviewed = new Date().toISOString();
  review = demoAgentReview({ models, comparison, status: "succeeded", answer: answerText, notes });
  running = false;
  paint();
  if (body) {
    body.classList.remove("is-answer-checking");
    body.classList.add("is-answer-check-done");
    setTimeout(() => body.classList.remove("is-answer-check-done"), 450);
  }
  // Demo results are a local preview: no bookmark, no vote, no telemetry.
  App.agentReview?.render(body, review, { key: DEMO_AGENT_ID, question: DEMO_SCENARIO_PROMPT, reveal: true });
  if (sendBtn) sendBtn.disabled = false;
  showPostDemoLoginPrompt();
}

// A new chat leaves the demo: the scripted turn stops and the panel is released.
document.getElementById("newRunButton")?.addEventListener("click", () => {
  if (!document.body.classList.contains("agent-demo-active")) return;
  demoRunId++;
  clearDemoAgentAnswer();
  window.App.agentChat?.demoView?.(false);
  const sendBtn = document.getElementById("sendButton");
  if (sendBtn) sendBtn.disabled = false;
});

// demo.js loads before the app bundle. The landing-page auto-start can fire
// before app-core.js has run on a slow connection, so wait for it first.
function whenAppReady() {
  if (window.App?.modelPrefs || document.readyState === "complete") return Promise.resolve();
  return new Promise(resolve => {
    document.addEventListener("DOMContentLoaded", resolve, { once: true });
    window.addEventListener("load", resolve, { once: true });
  });
}

async function runDemoFlow() {
  await whenAppReady();
  // The demonstration always uses the complete Daily lineup (the app's default
  // preset), not the intersection of its fixture authors with a previous
  // Open Models/Custom choice.
  // Shown only: it does not become the visitor's (or the account's) choice.
  window.App.previewConsensusPreset?.('fast');
  window.App.answerReader?.reset?.();
  const daily = window.CONSENSUS_PRESETS?.find(preset => preset.id === 'fast');
  activeDemoModels = (window.App.modelPrefs || []).filter(pref => daily?.models?.[pref.provider]).map(pref => pref.key);
  activeDemoData = buildDemoDataForModels(activeDemoModels);
  // Agent (the default, also for guests who come from the landing page)
  // plays an Agent turn (its reviewers and the AIs it asks are this lineup);
  // a chosen Compare plays the lineup's answer windows side by side.
  if (window.App?.runMode?.preference?.() === "agent" && window.App.agentChat?.demoView) {
    return runAgentDemoFlow();
  }
  window.enterDirectComparisonView?.();
  const runId = ++demoRunId;
  const sendBtn = document.getElementById("sendButton");
  if (sendBtn) sendBtn.disabled = true;
  // A saved Consensus answer that was on screen leaves.
  window.hideConsensusOutput?.();

  window.App.state.set("currentEvidenceSources", [], "evidence");
  window.renderEvidenceSources?.([]);

  const qi = document.getElementById("questionInput");
  if (qi && !qi.value.trim()) qi.value = DEMO_SCENARIO_PROMPT;

  if (DEMO_PHASES.preType) {
    const qiEl = document.getElementById("questionInput");
    await typeIntoInput(
      qiEl,
      DEMO_TYPED_QUESTION.slice(0, DEMO_PHASES.typeChars),
      DEMO_PHASES.typeSpeed
    );
    // Den Entwurf tippt niemand ab; er wird eingefuegt. Deshalb erscheint er
    // in einem Zug, mit einer kurzen Pause davor, damit sichtbar bleibt, dass
    // Frage und Nachricht zwei verschiedene Dinge sind.
    if (qiEl) {
      await sleep(340);
      qiEl.value = DEMO_SCENARIO_PROMPT;
      qiEl.dispatchEvent(new Event("input", { bubbles: true }));
    }
    await sleep(DEMO_PHASES.pauseAfterTypingAll);
  }

  // Die fertig getippte Frage wird jetzt "abgeschickt": Sie wandert in den
  // Thread-Kopf und verschwindet wie bei einem echten Lauf aus dem Composer.
  // Erst danach beginnen Fortschrittsanzeige und Modell-Spinner.
  window.App.state.set("lastQuestion", DEMO_SCENARIO_PROMPT, "run");
  window.App?.setThreadQuestion?.(DEMO_SCENARIO_PROMPT);
  if (qi) {
    qi.value = "";
    qi.dispatchEvent(new Event("input", { bubbles: true }));
    window.syncDemoChipState?.();
  }

  window.setAgentModeStatus?.("running");
  activeDemoModels.forEach(key => {
    const box = getBox(key);
    if (box) setSpinnerEl(box);
  });

  // Jede Modellantwort läuft zeitversetzt als Streaming-Response ein und wird
  // danach sauber gerendert (für [S1]-Quellenlinks und Copy-Buttons).
  await Promise.all(activeDemoModels.map(model =>
    new Promise(resolve => {
      const start = DEMO_STREAM_STARTS[model] ?? (activeDemoData.delays[model] || 1800);
      setTimeout(async () => {
        const box = getBox(model);
        const p = box?.querySelector(".collapsible-content");
        if (!p) { resolve(); return; }
        await streamDemoInto(p, activeDemoData.responses[model] || "", runId, DEMO_RESPONSE_STREAM);
        if (runId === demoRunId) renderDemoModelResponse(model, p);
        resolve();
      }, start);
    })
  ));

  if (runId !== demoRunId) return;

  // Compare ends after the lineup's answers.
  window.setAgentModeStatus?.("complete");
  showPostDemoLoginPrompt();

  if (sendBtn) sendBtn.disabled = false;
}

// "Try the demo" stands in the template (index.html), hidden; app-bootstrap.js
// shows it in the first frame unless this browser has used or typed past it
// (demoChipDismissed), so the composer never swaps Send for it in front of
// the reader. This wires it up once and keeps the offer in step with the
// field. It stays a one-time offer: the first keystroke retires it for
// good, and it fades out while Send fades in at the same end of the row
// (Apple-Audit B13).
const DEMO_SWAP_MS = 180;
function demoMotionAllowed() {
  return !window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
}

// Whatever appears in the send slot fades in where the other one stood.
function fadeInSlot(node) {
  if (!node || !demoMotionAllowed() || typeof node.animate !== "function") return;
  node.animate([{ opacity: 0, transform: "scale(.92)" }, { opacity: 1, transform: "none" }],
    { duration: DEMO_SWAP_MS, easing: "cubic-bezier(.22, 1, .36, 1)" });
}

function retireDemoChip(btn, storage) {
  storage?.setItem("demoChipDismissed", "1");
  if (!btn.isConnected || btn.classList.contains("is-leaving")) return;
  const sendBtn = document.getElementById("sendButton");
  if (!demoMotionAllowed() || typeof btn.animate !== "function") {
    btn.remove();
    return;
  }
  // Out of the row while it fades (composer.css .demo-chip.is-leaving), so
  // Send takes its place at once and nothing beside it moves.
  btn.classList.add("is-leaving");
  btn.tabIndex = -1;
  fadeInSlot(sendBtn);
  btn.animate([{ opacity: 1, transform: "none" }, { opacity: 0, transform: "scale(.96)" }],
    { duration: DEMO_SWAP_MS - 40, easing: "cubic-bezier(.4, 0, 1, 1)", fill: "forwards" })
    .finished.catch(() => {}).then(() => btn.remove());
}

function createStartDemoChip() {
  const storage = getDemoStorage();
  const container = document.querySelector(".chat-input-container");
  const btn = container?.querySelector(".demo-chip");
  if (!btn) return;
  if (storage?.getItem("demoChipDismissed")) {
    btn.remove();
    return;
  }
  if (btn.dataset.wired) return;
  btn.dataset.wired = "true";
  btn.hidden = false;
  const questionInput = document.getElementById("questionInput");

  let chipShown = null;
  const syncChipState = () => {
    if (!btn.isConnected || btn.classList.contains("is-leaving")) return;
    const hasQuestionText = Boolean(questionInput?.value.length);
    container.classList.toggle("has-question-input", hasQuestionText);
    btn.tabIndex = hasQuestionText ? -1 : 0;
    // A filled-in example or draft hands the slot to Send and back; only a
    // change, never the first sync, moves anything.
    if (chipShown !== null && chipShown === hasQuestionText) {
      fadeInSlot(hasQuestionText ? document.getElementById("sendButton") : btn);
    }
    chipShown = !hasQuestionText;
  };

  window.syncDemoChipState = syncChipState;

  if (questionInput) {
    questionInput.addEventListener("input", event => {
      if (questionInput.value.length && event.isTrusted) {
        retireDemoChip(btn, storage);
        container.classList.add("has-question-input");
        return;
      }
      syncChipState();
    });
    questionInput.addEventListener("change", syncChipState);
  }

  btn.addEventListener("click", async () => {
    storage?.setItem("demoChipDismissed", "1");
    btn.remove();
    await runDemoFlow();
  });

  syncChipState();
}

window.runDemoFlow = runDemoFlow;
window.createStartDemoChip = createStartDemoChip;
createStartDemoChip();

/* === DEMO: Auto-Start von der Landingpage (/app?demo=1) ================ */
// Der Hero der Landingpage verlinkt auf /app?demo=1: Die Demo startet dann
// automatisch in der echten App-Oberfläche, statt auf der Landingpage einen
// zweiten App-Nachbau zu pflegen. Nach der Demo ist der Nutzer bereits in der
// App und sieht den bestehenden Post-Demo-Login-Prompt.
function maybeAutoStartDemo() {
  let shouldStart = false;
  try {
    const params = new URLSearchParams(window.location.search);
    if (params.get("demo") === "1") {
      shouldStart = true;
      // Parameter entfernen, damit Reload/Bookmark die Demo nicht erneut startet.
      params.delete("demo");
      const query = params.toString();
      window.history.replaceState(
        null, "",
        window.location.pathname + (query ? "?" + query : "") + window.location.hash
      );
    }
  } catch (e) {
    return;
  }
  if (!shouldStart) return;

  // Auto-Start ersetzt den Chip-Klick: Chip einmalig als erledigt markieren.
  getDemoStorage()?.setItem("demoChipDismissed", "1");

  const start = () => {
    document.querySelector(".chat-input-container .demo-chip")?.remove();
    window.trackAppEvent?.("app_demo_autostart", { source: "landing" });
    // Kurze Pause: Erst rendert der Hero, dann beginnt die Demo zu tippen.
    // Das Tippen selbst überbrückt die restliche Initialisierung der App.
    setTimeout(() => runDemoFlow(), 450);
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
}
maybeAutoStartDemo();

// Whoever just watched the demo is most likely new: open on "Sign up".
document.getElementById("postDemoLoginButton")?.addEventListener("click", event => {
  if (window.App?.openAuthModal) {
    window.App.openAuthModal("register", event.currentTarget, "post_demo");
    return;
  }
  const modal = document.getElementById("loginModal");
  if (!modal || !window.App?.modalDialog) return;

  window.App.modalDialog.open(modal, { opener: event.currentTarget, focus: document.getElementById("loginEmail") });
  window.trackAppEvent?.("auth_modal_open", { source: "post_demo" });
});

function toggleSettingsCollapse(contentId, arrowId) {
  const content = document.getElementById(contentId);
  const arrow = document.getElementById(arrowId);
  if (!content) return;

  // The initial closed state comes from a template CSS class. Inspect the
  // effective value so the first click opens it even before an inline value
  // has ever been written.
  const opening = window.getComputedStyle(content).display === "none";
  if (opening) {
    content.style.display = "block";
    if (arrow) arrow.classList.add("rotated");
    if (arrow) arrow.innerHTML = "&#9650;";
  } else {
    content.style.display = "none";
    if (arrow) arrow.classList.remove("rotated");
    if (arrow) arrow.innerHTML = "&#9660;";
  }
  // The header is a role=button: screen readers hear open or closed from it.
  document.querySelector(`[aria-controls="${contentId}"]`)?.setAttribute("aria-expanded", String(opening));
}

window.toggleSettingsCollapse = toggleSettingsCollapse;
