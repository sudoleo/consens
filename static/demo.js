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
   eine zweite und dritte Meinung holt und bei der ein Fehler Geld kostet:
   Soll ein Paar die Wohnung kaufen, in der es zur Miete wohnt, oder weiter
   mieten und die Differenz anlegen? Die Demo zeigt, was der Agent kann:
   einen Plan, der sich abhakt, eine Websuche mit echten
   Quellen, seinen Arbeitsplatz (Skript schreiben, rechnen, Ausgabe), ein
   Diagramm im Antworttext und eine Excel-Tabelle mit Vorschau neben dem
   Chat, die einmal gefragten KIs und die Pruefer, die der Arbeit folgen.
   Diagramm, Tabelle und jede Zahl stammen aus einem Modell
   (scripts/demo_assets.py, Dateien unter static/demo). Die Pruefer haben
   drei Anmerkungen: eine falsche Stelle, die das Ergebnis kippt (der Agent
   rechnet mit Sachsens alter Grunderwerbsteuer von 3,5 %, seit 2023 sind
   es 5,5 %), eine zweifelhafte und eine unvollstaendige. Kein Score. Die
   Quellen der Suche sind echte Seiten zum Thema; die Antwort zitiert sie
   nicht, erfundene Belege waeren die schlechtere Demo.
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

// The question, then the details pasted under it: each a sentence of the
// dictionary of its own, as demoInPageLanguage looks them up.
const DEMO_SCENARIO_PROMPT = demoInPageLanguage([
  "Should we buy the flat we rent, or keep renting and invest the difference?",
  "Leipzig, 82 m², built 1994. Our landlord offers it to us for €310,000, no agent. Rent is €925 cold. Equity €70,000, the bank offers 3.6% fixed for 15 years with 2% repayment. We plan to stay 12 years."
].join("\n\n"));

// Die Eckdaten werden nicht getippt, sondern eingefuegt, so wie man sie aus
// einer Notiz oder dem Angebot der Bank uebernimmt.
const DEMO_TYPED_QUESTION = DEMO_SCENARIO_PROMPT.split("\n")[0];

// The two reviewers' viewpoints first: whichever two families Daily has,
// they take these two, and the notes stay with them (buildDemoDataForModels).
const DEMO_MODELS = ["Anthropic", "DeepSeek", "OpenAI", "Gemini", "Mistral", "Grok"];

const DEMO_DATA = demoInPageLanguage({
  delays: { Anthropic: 1400, DeepSeek: 2500, OpenAI: 2900, Gemini: 3600, Mistral: 4300, Grok: 5000 },
  responses: {
    Anthropic:
`<div class="ai-block">
  <p>If the 12 years are firm, buying is likely the better deal, but not by much, and not for the reason most people think.</p>
  <h4>Why it can work</h4>
  <ul>
    <li>Every repayment is money you keep. Rent is gone, and it tends to rise.</li>
    <li>Buying from your landlord saves the agent’s fee and the move, and you already know the flat and the building.</li>
  </ul>
  <h4>Why it is closer than it looks</h4>
  <ul>
    <li>Tax, notary and land registry are gone the day you sign. The flat needs years just to earn them back.</li>
    <li>You carry the repairs. Ask for the owners’ association’s last three statements and the size of its repair reserve before you agree a price.</li>
  </ul>
  <p>Work out the year in which buying pulls ahead. If it is well before your 12, buy; if it is close, the money does not decide it.</p>
</div>`,

    DeepSeek:
`<div class="ai-block">
  <p>Renting and investing the difference is the more flexible choice, and over 12 years it is often just as good.</p>
  <h4>What speaks for renting</h4>
  <ul>
    <li>Plans change: a job, a child, a separation. Selling within a few years usually costs you the purchase costs and more.</li>
    <li>€70,000 in one flat is a bet on one building in one city. Invested broadly, the same money carries less risk.</li>
    <li>A tenant never pays for a new roof or a new heating system.</li>
  </ul>
  <h4>What it takes</h4>
  <ul>
    <li>Investing the difference every month, for 12 years. A loan makes you save; a savings plan does not.</li>
    <li>A rent that does not run away from you.</li>
  </ul>
  <p>If you are not sure you will really stay 12 years, I would keep renting.</p>
</div>`,

    OpenAI:
`<div class="ai-block">
  <p>The useful question is not whether to buy or rent, but from which year buying pulls ahead. Compare that year with your 12.</p>
  <h4>How to work it out</h4>
  <ul>
    <li>Let both households spend the same each month: the owners pay the loan and the upkeep, the tenants pay rent and invest the rest.</li>
    <li>Each year, compare what the owners own, the flat minus the loan, with what the tenants have saved.</li>
    <li>The owners start behind by the purchase costs; the repayments and the rising rent close the gap.</li>
  </ul>
  <h4>What moves the result most</h4>
  <ul>
    <li>How fast the flat gains in value, and what the savings earn.</li>
    <li>The rate once the fixed period ends.</li>
  </ul>
  <p>Run it with cautious numbers too. If buying only wins with optimistic ones, it does not really win.</p>
</div>`,

    Gemini:
`<div class="ai-block">
  <p>Look at the building and the price before you look at the calculation.</p>
  <ul>
    <li><b>The price</b>: €310,000 is about 28 years of your rent. Above 25 counts as expensive, and that favours renting.</li>
    <li><b>The building</b>: from 1994, it is reaching the age of a new roof, new windows or a new heating system. Ask whether the owners’ association has planned any of it.</li>
    <li><b>The reserve</b>: a small repair reserve today means a special levy later, on top of your monthly payment.</li>
    <li><b>The minutes</b>: read the last three years of owners’ meetings. Disputes and postponed repairs are in there.</li>
    <li><b>Your position</b>: as the sitting tenant you are the easiest buyer your landlord will find. That is worth a lower price.</li>
  </ul>
  <p>If the building is in good shape and the price comes down, buying is a reasonable bet for 12 years.</p>
</div>`,

    Mistral:
`<div class="ai-block">
  <p>Work through it in this order.</p>
  <ol>
    <li>Get the owners’ association’s statements, minutes and repair reserve. They decide what owning really costs.</li>
    <li>Negotiate: as the sitting tenant you save your landlord the agent and the search.</li>
    <li>Calculate year by year what each path leaves you with, including the purchase costs on the first day.</li>
    <li>Find the year in which buying pulls ahead, and compare it with how long you will really stay.</li>
    <li>Ask the bank how much will still be owed after the 15 years, and what a higher rate would cost you then.</li>
  </ol>
  <p>Only buy if it still works with cautious numbers.</p>
</div>`,

    Grok:
`<div class="ai-block">
  <p>Plain take: over 12 years the money is close to a coin toss, so decide on what the money does not show.</p>
  <ul>
    <li>Buying wins if you stay, the flat holds its value and the rate after 15 years is kind to you.</li>
    <li>Renting wins if you really invest the difference and might move sooner than you think.</li>
    <li>A landlord who sells is a signal. Find out why, and what the building needs soon.</li>
    <li>Do not stretch for it: the monthly payment should still feel easy in a bad year.</li>
  </ul>
  <p>If you both would rather own than invest, that is a fine reason to buy. Just know it is a preference, not a sure profit.</p>
</div>`
  },
  // The agent's own answer, written after it calculated in its workspace and
  // asked the AIs once. The first line is its verdict (bold in the chat,
  // demoAgentAnswer); the figure is the chart it shared, placed in the text
  // ("![…](picture:f1)", demoResponseMarkdown). Its purchase costs use
  // Saxony's old transfer tax: the reviewers' wrong note is about it.
  answer:
`<div class="ai-answer">
  <p>Buying pulls ahead in year 9, so over your 12 years it comes out about €9,200 in front.</p>
  <p>Until then, renting and investing the difference leads, because the purchase costs are gone on the first day. After that, the repayments and the rising rent tip it towards buying.</p>
  <figure data-picture="f1">Buying and renting over 30 years</figure>
  <h4>What the calculation assumes</h4>
  <ul>
    <li>Purchase costs: 3.5% property transfer tax and 2% for notary and land registry, €17,050 in total.</li>
    <li>As owners you pay €1,320 a month: €1,200 for the loan and €120 for management and the repair reserve.</li>
    <li>As tenants you pay €925 rent, rising 2.5% a year, and invest the other €395 at 5% a year.</li>
    <li>The flat gains 1.5% in value a year.</li>
    <li>The rate stays at 3.6% until the loan is repaid.</li>
  </ul>
  <h4>Decide for yourselves</h4>
  <ul>
    <li>The two answers I asked for split: one counts on the forced saving of paying off a loan, the other on the freedom to move without selling.</li>
    <li>At 12 years the two paths are less than 5% apart. If the 12 years are not certain, renting keeps you free to move.</li>
  </ul>
  <p>Every number is in the spreadsheet: change an assumption, and it works out again when buying pulls ahead.</p>
</div>`,

  // What the reviewers note on that answer, in the review's own shape
  // (agent_audit.place_marks): the sentence it concerns (anchor), the
  // quoted words in it (target), its kind and the reviewer's note. Daily's
  // two reviewers (Claude, DeepSeek) carry one note of each
  // kind between them; a reviewer the lineup does not have stays out. The
  // numbers are scripts/demo_assets.py's: with 5.5 % buying pulls ahead in
  // year 13, with 1 % value growth in year 20; after 15 years €157,116 is owed.
  notes: [
    {
      model: "Anthropic",
      kind: "wrong",
      anchor: "Purchase costs: 3.5% property transfer tax and 2% for notary and land registry, €17,050 in total.",
      target: "3.5% property transfer tax",
      note: "Saxony has charged 5.5% since January 2023. That makes the purchase costs €23,250, and buying only pulls ahead in year 13, after the 12 years you plan to stay."
    },
    {
      model: "DeepSeek",
      kind: "doubtful",
      anchor: "The flat gains 1.5% in value a year.",
      target: "1.5% in value a year",
      note: "That is a guess for 30 years, not a trend, and the result hangs on it: with 1% a year, buying only pulls ahead in year 20."
    },
    {
      model: "Anthropic",
      kind: "incomplete",
      anchor: "The rate stays at 3.6% until the loan is repaid.",
      target: "stays at 3.6% until the loan is repaid",
      note: "It is fixed for 15 years only. About €157,000 is still owed then, at a rate nobody can tell you today."
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
  order: ["Anthropic", "DeepSeek", "OpenAI", "Gemini", "Mistral", "Grok"],
  // Obergrenze fuer die getippte Frage (ohne die eingefuegten Eckdaten).
  typeChars: 140,
  typeSpeed: 30,
  gapBetweenModels: 540,
  pauseAfterTypingAll: 500
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
const DEMO_STREAM_STARTS = { Anthropic: 500, DeepSeek: 1150, OpenAI: 1800, Gemini: 2450, Mistral: 3100, Grok: 3750 };
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
    // A picture the agent shared, placed in its text (markdown-stream.js).
    if (tag === 'figure') return `\n\n![${text.trim()}](picture:${node.getAttribute('data-picture')})\n\n`;
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
   the real Agent surfaces, in the one mode every account has: one AI
   does the work, the AIs of the Daily lineup follow it
   and review its answer. What the agent does is what a real turn shows
   (agent-activity.js): its plan, checked off step by step (update_plan),
   a web search with its sources, its workspace (open_workspace, a script it
   writes and runs, the output of the run, the files it shares), the one
   time it asks the AIs (compare_models), then the streamed answer
   (markdown-stream.js) with its chart in the text and its spreadsheet under
   it (App.agentWorkspace.demo: the same figure, row and preview beside the
   chat as a real turn's files), and the review of exactly that text
   (agent-review.js, a review of mode "audit"): the reviewers' marks in the
   answer, Notes and the Answers of the AIs it asked under it. The
   reviewers and the AIs it asks stand beside the clock and in the panel
   (App.agentDelegation.demo, sessions of kind "audit" and "comparison").
   No score. The run is local and scripted from the same fixtures as the
   Compare demo: no request, no bookmark, no vote. agent-chat.js keeps the
   answer panel on screen while the demo owns it (App.agentChat.demoView),
   also for guests.
   ======================================================================= */
const DEMO_AGENT_ID = "demo";
const DEMO_AGENT_HASH = "demo-answer-v2";
// When each step happens, in ms after the question was sent. Something
// moves every second or so: the whole turn takes about 17 seconds.
const DEMO_AGENT_STEPS = {
  plan: 400,            // the plan and the first note; the reviewers start following
  search: 1000,         // web_search
  searched: 2400,
  workspace: 2700,      // open_workspace
  write: 3300,          // vm_write_file: the script
  run: 3900,            // vm_exec: its output arrives line by line
  ran: 5700,
  chart: 6000,          // vm_share_file: the chart
  sheet: 6500,          // vm_share_file: the spreadsheet
  compare: 7200,        // compare_models: the agent asks the AIs once
  modelSpread: 2800,    // the last answer lands this long after compare
  afterCompare: 700,    // progress note, then the answer starts streaming
  review: 2400          // the reviewers' final review of the fixed answer
};
const DEMO_AGENT_STREAM = { wordsPerTick: 3, tickMs: 40 };
const DEMO_AGENT_NOTES = demoInPageLanguage({
  plan: "Whether buying pays off depends on how long you stay. I’ll calculate both paths year by year in my workspace, then ask the other AIs how they weigh it.",
  computed: "In my calculation buying pulls ahead in year 9. I’ll put it all in a spreadsheet, so you can change any assumption.",
  compared: "They split on whether paying off a loan beats investing the difference, so the answer shows when the two paths cross instead of picking a side."
});
// The agent's plan in its own words (update_plan); the step it is on is
// "in_progress", the ones before it "completed".
const DEMO_AGENT_PLAN = demoInPageLanguage([
  "Look up rents and owner costs in Leipzig",
  "Calculate 30 years of buying and renting",
  "Ask the other AIs for their view",
  "Write the answer"
]);
// Real pages on what the search looked up; the answer does not cite them.
const DEMO_AGENT_SOURCES = [
  { url: "https://www.leipzig.de/mietspiegel", title: "Mietspiegel der Stadt Leipzig" },
  { url: "https://www.finanztip.de/eigentumswohnung/hausgeld/", title: "Hausgeld: Laufende Kosten einer Eigentumswohnung" },
  { url: "https://www.homeday.de/de/immobilienwissen/instandhaltungsruecklage/", title: "Instandhaltungsrücklage: Höhe & Berechnung" }
];
// The files of its workspace, named in the page's language; the files it
// shares are static (scripts/demo_assets.py writes them in both languages).
const DEMO_AGENT_FILES = demoInPageLanguage({
  script: "buy_vs_rent.py",
  chart: "chart.png",
  sheet: "buy-vs-rent.xlsx",
  task: "Calculate 30 years of buying and renting"
});
const DEMO_SHEET_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
function demoAgentShared(withSheet) {
  const lang = window.App?.lang === "de" ? "de" : "en";
  // Its size is the PNG's (scripts/demo_assets.py WIDTH, HEIGHT): the field
  // it shows until it arrives has its shape (agent_files.picture_size).
  const chart = { id: "dec0de00000000000000000000000001", name: DEMO_AGENT_FILES.chart, mime: "image/png",
    kind: "vm_file", status: "ready", size: 131072, width: 1600, height: 1000, origin: { ref: "f1" },
    demo: { file: `/static/demo/buy-vs-rent.${lang}.png` } };
  const sheet = { id: "dec0de00000000000000000000000002", name: DEMO_AGENT_FILES.sheet, mime: DEMO_SHEET_MIME,
    kind: "vm_file", status: "ready", size: 8192, preview: true,
    demo: { file: `/static/demo/buy-vs-rent.${lang}.xlsx`, preview: `/static/demo/buy-vs-rent.${lang}.pdf` } };
  return withSheet ? [chart, sheet] : [chart];
}
// What its script prints: a few of the 30 years (scripts/demo_assets.py),
// the year buying pulls ahead and the files it saved. Code output, so the
// numbers keep the program's format; its words are the page's.
const DEMO_AGENT_YEARS = [[0, 52950, 70000], [5, 104532, 112822], [9, 150924, 150123],
  [12, 189090, 179930], [20, 307364, 267223], [30, 484555, 379043]];
function demoRunOutput() {
  const t = window.App.t;
  const number = value => Math.round(value).toLocaleString("en-US");
  const cells = (...items) => items.map((item, index) => String(item).padStart(index ? 11 : 4)).join("");
  return [
    cells(t("year", null, "demo output"), t("buying", null, "demo output"), t("renting", null, "demo output"),
      t("lead", null, "demo output")),
    ...DEMO_AGENT_YEARS.map(([year, buying, renting]) => cells(year, number(buying), number(renting), number(buying - renting))),
    t("Buying pulls ahead in year {year}.", { year: 9 }),
    t("Saved {chart} and {sheet}", { chart: DEMO_AGENT_FILES.chart, sheet: DEMO_AGENT_FILES.sheet })
  ];
}
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
  window.App.agentWorkspace?.demo?.(null);
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
  // Once agent-chat.js has let go of the demo (a run, a saved chat or a new
  // chat took the panel), nothing more is written into it.
  let shown = false;
  const live = () => runId === demoRunId && (!shown || document.body.classList.contains("agent-demo-active"));
  const sendBtn = document.getElementById("sendButton");
  if (sendBtn) sendBtn.disabled = true;
  App.state.set("currentEvidenceSources", [], "evidence");

  const qi = document.getElementById("questionInput");
  if (DEMO_PHASES.preType && qi) {
    await typeIntoInput(qi, DEMO_TYPED_QUESTION.slice(0, DEMO_PHASES.typeChars), DEMO_PHASES.typeSpeed);
    await sleep(300);
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
  shown = Boolean(host);
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
  // A step that changes is a new event in its old place, as a real turn's
  // update arrives (agent-activity.js redraws an event only as a new object
  // or with a new status, stamp).
  const step = (id, changes) => {
    const index = events.findIndex(item => item.id === id);
    const item = { ...(index >= 0 ? events[index] : { version: 1, kind: "tool", id }), ...changes };
    if (index >= 0) events[index] = item; else events.push(item);
    return item;
  };
  // The plan as the agent updates it: `current` is the step it is on.
  let plans = 0;
  const plan = current => events.push({ version: 1, kind: "tool", id: `demo-plan-${++plans}`, name: "update_plan",
    status: "succeeded", items: DEMO_AGENT_PLAN.map((content, index) => ({ content,
      status: index < current ? "completed" : index === current ? "in_progress" : "pending" })) });
  paint();

  if (!await at(DEMO_AGENT_STEPS.plan)) return;
  plan(0);
  events.push({ version: 1, kind: "progress", id: "demo-note-plan", text: DEMO_AGENT_NOTES.plan });
  following = true;
  paint();

  // The search, with the pages it found.
  if (!await at(DEMO_AGENT_STEPS.search)) return;
  step("demo-search", { name: "web_search", status: "running" });
  paint();
  if (!await at(DEMO_AGENT_STEPS.searched)) return;
  step("demo-search", { status: "succeeded", count: 2, sources: DEMO_AGENT_SOURCES });
  round(DEMO_AGENT_STEPS.searched);
  paint();

  // Its workspace: the script, the run and its output, the files it shares.
  if (!await at(DEMO_AGENT_STEPS.workspace)) return;
  plan(1);
  step("demo-workspace", { name: "open_workspace", status: "running", task: DEMO_AGENT_FILES.task });
  paint();
  if (!await at(DEMO_AGENT_STEPS.write)) return;
  step("demo-workspace", { status: "succeeded" });
  step("demo-write", { name: "vm_write_file", status: "running", path: DEMO_AGENT_FILES.script });
  paint();
  if (!await at(DEMO_AGENT_STEPS.run)) return;
  step("demo-write", { status: "succeeded" });
  const command = `python ${DEMO_AGENT_FILES.script}`;
  step("demo-run", { name: "vm_exec", status: "running", command, started_at: iso(DEMO_AGENT_STEPS.run), output: "" });
  paint();
  const lines = demoRunOutput();
  const lineGap = (DEMO_AGENT_STEPS.ran - DEMO_AGENT_STEPS.run) / (lines.length + 1);
  for (let index = 0; index < lines.length; index++) {
    if (!await at(DEMO_AGENT_STEPS.run + lineGap * (index + 1))) return;
    step("demo-run", { output: lines.slice(0, index + 1).join("\n") });
    paint();
  }
  if (!await at(DEMO_AGENT_STEPS.ran)) return;
  step("demo-run", { status: "succeeded", exit_code: 0, duration_ms: DEMO_AGENT_STEPS.ran - DEMO_AGENT_STEPS.run });
  events.push({ version: 1, kind: "progress", id: "demo-note-computed", text: DEMO_AGENT_NOTES.computed });
  round(DEMO_AGENT_STEPS.ran);
  paint();
  for (const [id, path, ms] of [["demo-chart", DEMO_AGENT_FILES.chart, DEMO_AGENT_STEPS.chart],
    ["demo-sheet", DEMO_AGENT_FILES.sheet, DEMO_AGENT_STEPS.sheet]]) {
    if (!await at(ms)) return;
    step(id, { name: "vm_share_file", status: "running", path });
    paint();
    if (!await at(ms + 350)) return;
    step(id, { status: "succeeded" });
    paint();
  }

  // compare_models: the AIs answer independently, each on its own beat.
  if (!await at(DEMO_AGENT_STEPS.compare)) return;
  plan(2);
  step("demo-compare", { name: "compare_models", status: "running" });
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
  step("demo-compare", { status: "succeeded" });
  events.push({ version: 1, kind: "progress", id: "demo-note-compared", text: DEMO_AGENT_NOTES.compared });
  round(DEMO_AGENT_STEPS.compare + DEMO_AGENT_STEPS.modelSpread);
  paint();

  // The answer, written in its own step after the comparison, with the
  // chart in its place; the spreadsheet joins it once the text stands.
  if (!await at(DEMO_AGENT_STEPS.compare + DEMO_AGENT_STEPS.modelSpread + DEMO_AGENT_STEPS.afterCompare)) return;
  plan(3);
  events.push({ version: 1, kind: "status", id: "demo-status", status: "responding" });
  App.agentWorkspace?.demo?.(body, demoAgentShared(false), { writing: true });
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
  App.agentWorkspace?.demo?.(body, demoAgentShared(true));

  // The reviewers review exactly this text: the row under it stands with
  // Notes waiting, a quiet sheen passes over the answer (agent-chat.js
  // setAnswerChecking), the head says "Reviewing".
  const comparison = demoAgentComparison(models, answered);
  events.push({ version: 1, kind: "tool", id: "demo-plan-done", name: "update_plan", status: "succeeded",
    items: DEMO_AGENT_PLAN.map(content => ({ content, status: "completed" })) });
  step("demo-review", { name: "audit_answer", status: "running" });
  review = demoAgentReview({ models, comparison, status: "running", answer: answerText });
  body?.classList.add("is-answer-checking");
  App.agentReview?.render(body, review, { key: DEMO_AGENT_ID, question: DEMO_SCENARIO_PROMPT });
  paint();
  await sleep(DEMO_AGENT_STEPS.review);
  if (!live()) return;

  step("demo-review", { status: "succeeded" });
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
    // Die Eckdaten tippt niemand ab; sie werden eingefuegt. Deshalb erscheinen
    // sie in einem Zug, mit einer kurzen Pause davor, damit sichtbar bleibt,
    // dass Frage und Eckdaten zwei verschiedene Dinge sind.
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
  // danach wie eine echte Antwort gerendert (renderDemoModelResponse).
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
// good, and it fades out while Send fades in at the same end of the row.
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
  // Out of the row while it fades (components-misc.css .demo-chip.is-leaving), so
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
