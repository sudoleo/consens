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
   mit den alten Heizkoerpern. Sie kostet fuenfstellig, die Fachleute sind
   sich wirklich uneins, und die Uneinigkeit ist die Nachricht, nicht der
   Fehler. Deshalb hat der Lauf drei strittige Stellen (ein kritischer
   Widerspruch zur Vorlauftemperatur, ein kleiner zum Gaskessel als Reserve,
   eine andere Gewichtung bei der Reihenfolge) statt einer Randnotiz, und
   der Score liegt im mittleren Bereich. Quellenlisten gibt es bewusst
   nicht: erfundene Belege waeren die schlechtere Demo.
   ================================================================= */
const DEMO_SCENARIO_PROMPT =
  "Our house is from 1978 and still has the original radiators. Can a heat pump heat it properly, or do we need new radiators first?\n\n" +
  "Detached, 140 m², walls insulated in 2015, original double glazing. The gas boiler currently runs at 70 °C.";

// Die Hausdaten werden nicht getippt, sondern eingefuegt, so wie man sie
// aus einer Notiz oder dem Energieausweis uebernimmt.
const DEMO_TYPED_QUESTION = DEMO_SCENARIO_PROMPT.split("\n")[0];

const DEMO_MODELS = ["OpenAI", "Mistral", "Anthropic", "Gemini", "DeepSeek", "Grok"];

const DEMO_DATA = {
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
  consensus:
`<div class="ai-consensus">
  <p>Consensus: probably yes, with a few radiators changed, not all of them</p>
  <p>All six models think a heat pump can heat this house. The walls were insulated in 2015, and that matters more than the year it was built. What none of them can tell you from here is which rooms fall short, and that is the whole question.</p>
  <h4>Do this first</h4>
  <ul>
    <li>Get a room-by-room heat-loss calculation before anyone quotes a heat pump size.</li>
    <li>Test it this winter: turn the boiler down to 50 °C for a cold week and note which rooms stay warm.</li>
    <li>Rooms that stay warm keep their radiators; only the rooms that fall short need larger or fan-assisted ones.</li>
    <li>Original 1970s radiators are often larger than the room needs today, because they were sized for an uninsulated house.</li>
    <li>Have the heat pump sized from the calculation, not from the old boiler’s output.</li>
  </ul>
  <h4>Decide for yourself</h4>
  <ul>
    <li>The models split on the target flow temperature: three would keep most radiators and run at 55 °C, three would replace more of them to run at 45 °C or below.</li>
    <li>They also disagree on what that costs you: estimates for the efficiency gap between 55 °C and 45 °C range from a few percent to about a quarter.</li>
    <li>Keeping the gas boiler as a backup for the coldest days divides them as well: a cheap safety net for some, two systems to maintain for others.</li>
    <li>Whether to start with the survey or with the winter test is a matter of order, not of substance.</li>
  </ul>
  <h4>What that looks like</h4>
  <blockquote>Heat-loss survey: 140 m² at roughly 8 kW. Test week at 50 °C: the living room and two bedrooms stay warm, the bathroom and the north bedroom do not. [Replace those two radiators, or more.] Heat pump sized at 8 to 9 kW. [Target flow temperature.]</blockquote>
  <p>Both bracketed parts are the ones the models could not settle for you, and both come down to the same trade: what you spend once on radiators against what you spend every winter on electricity.</p>
</div>`,

  // Strukturierte Auswertung, exakt das Schema, das eine echte Consensus-Query
  // liefert. Treibt Verdict-Header, Agreement-Badges und die Differences-Karten
  // (inkl. Contradiction) ueber window.renderConsensusInsights.
  //
  // Der Score ist nicht gegriffen, sondern die Rechnung aus
  // app/services/llm/consensus_scoring.py auf genau diese Daten:
  // Claim-Schnitt 15.8333/19 = 0.8333, minus 0.25 (major) - 0.10 (minor)
  // - 0.05 (emphasis) = 0.4333 -> 43, Deckel 0.64 greift nicht. Jeder
  // pruefbare Satz traegt einen Claim; dieselbe Uneinigkeit taucht deshalb
  // auch im Beispiel unten in den Klammern auf.
  differencesData: {
    models_compared: DEMO_MODELS,
    best_model: "Anthropic",
    judges: { differences: { provider: "Gemini" } },
    agreement: {
      score: 43,
      level: "partially",
      model_count: 6,
      major_contradictions: 1,
      minor_contradictions: 1,
      emphases: 1
    },
    claims: [
      {
        anchor: "Consensus: probably yes, with a few radiators changed",
        agree: DEMO_MODELS,
        dissent: [],
        coverage: "supported"
      },
      {
        anchor: "All six models think a heat pump can heat this house",
        agree: DEMO_MODELS,
        dissent: [],
        coverage: "supported"
      },
      {
        anchor: "The walls were insulated in 2015",
        agree: ["OpenAI", "Anthropic", "Gemini", "Grok"],
        dissent: [],
        coverage: "supported"
      },
      {
        anchor: "What none of them can tell you from here",
        agree: DEMO_MODELS,
        dissent: [],
        coverage: "supported"
      },
      {
        anchor: "Get a room-by-room heat-loss calculation",
        agree: DEMO_MODELS,
        dissent: [],
        coverage: "supported"
      },
      {
        anchor: "Test it this winter",
        agree: ["OpenAI", "Mistral", "Anthropic", "Gemini", "Grok"],
        dissent: [{
          model: "DeepSeek",
          quote: "Do not rely on a boiler test alone"
        }],
        coverage: "split"
      },
      {
        anchor: "Rooms that stay warm keep their radiators",
        agree: ["OpenAI", "Anthropic", "Gemini", "Grok"],
        dissent: [
          { model: "Mistral", quote: "Replace the radiators in every room you use daily" },
          { model: "DeepSeek", quote: "Replace the radiators in the rooms you heat most" }
        ],
        coverage: "split"
      },
      {
        anchor: "Original 1970s radiators are often larger than the room needs today",
        agree: ["OpenAI", "Anthropic", "Gemini", "Grok"],
        dissent: [],
        coverage: "supported"
      },
      {
        anchor: "Have the heat pump sized from the calculation",
        agree: DEMO_MODELS,
        dissent: [],
        coverage: "supported"
      },
      {
        anchor: "The models split on the target flow temperature",
        agree: ["OpenAI", "Gemini", "Grok"],
        dissent: [
          { model: "Mistral", quote: "That is what lets the heat pump run at 45 °C or below" },
          { model: "Anthropic", quote: "Plan for 45 °C rather than 55 °C" },
          { model: "DeepSeek", quote: "so the system can run at 45 °C or below" }
        ],
        coverage: "split"
      },
      {
        anchor: "They also disagree on what that costs you",
        agree: ["Mistral", "Anthropic", "DeepSeek"],
        dissent: [
          { model: "OpenAI", quote: "costs a few percent on the annual bill" },
          { model: "Gemini", quote: "The step down to 45 °C is worth a few percent" },
          { model: "Grok", quote: "saves less than the radiators cost" }
        ],
        coverage: "split"
      },
      {
        anchor: "Keeping the gas boiler as a backup for the coldest days divides them as well",
        agree: ["Mistral", "Gemini", "Grok"],
        dissent: [
          { model: "OpenAI", quote: "I would also take the gas boiler out completely" },
          { model: "Anthropic", quote: "Do not keep the gas boiler as a backup" },
          { model: "DeepSeek", quote: "You keep the standing charge and lose the reason you switched" }
        ],
        coverage: "split"
      },
      {
        anchor: "Whether to start with the survey or with the winter test",
        agree: DEMO_MODELS,
        dissent: [],
        coverage: "supported"
      },
      {
        anchor: "Heat-loss survey: 140 m² at roughly 8 kW.",
        agree: DEMO_MODELS,
        dissent: [],
        coverage: "supported"
      },
      {
        anchor: "Test week at 50 °C",
        agree: ["OpenAI", "Mistral", "Anthropic", "Gemini", "Grok"],
        dissent: [{
          model: "DeepSeek",
          quote: "A boiler at 50 °C on a mild day says little about a heat pump at minus ten"
        }],
        coverage: "split"
      },
      {
        anchor: "Replace those two radiators, or more.",
        agree: ["OpenAI", "Gemini", "Grok"],
        dissent: [
          { model: "Mistral", quote: "Replace the radiators in every room you use daily" },
          { model: "Anthropic", quote: "Plan for 45 °C rather than 55 °C" },
          { model: "DeepSeek", quote: "Replace the radiators in the rooms you heat most" }
        ],
        coverage: "split"
      },
      {
        anchor: "Heat pump sized at 8 to 9 kW.",
        agree: DEMO_MODELS,
        dissent: [],
        coverage: "supported"
      },
      {
        anchor: "Target flow temperature.",
        agree: ["OpenAI", "Gemini", "Grok"],
        dissent: [
          { model: "Mistral", quote: "That is what lets the heat pump run at 45 °C or below" },
          { model: "Anthropic", quote: "Plan for 45 °C rather than 55 °C" },
          { model: "DeepSeek", quote: "so the system can run at 45 °C or below" }
        ],
        coverage: "split"
      },
      {
        anchor: "Both bracketed parts are the ones the models could not settle for you",
        agree: DEMO_MODELS,
        dissent: [],
        coverage: "supported"
      }
    ],
    differences: [
      {
        claim: "Run at 55 °C with most radiators, or replace more of them for 45 °C?",
        // Stelle im Konsenstext, die inline markiert wird (Wellenlinie +
        // Marker). Muss woertlich im Antworttext oben vorkommen.
        consensus_anchor: "three would replace more of them to run at 45 °C or below",
        type: "contradiction",
        severity: "major",
        positions: [
          {
            stance: "55 °C. Keep every radiator that passes the test; the last ten degrees save little.",
            models: ["OpenAI", "Gemini", "Grok"],
            quote: "replacing every radiator to get there costs more than that difference will save in a decade."
          },
          {
            stance: "45 °C. Replace more radiators now; the efficiency is paid every winter.",
            models: ["Anthropic", "Mistral", "DeepSeek"],
            quote: "The efficiency difference is around a quarter, and you pay it every winter for twenty years."
          }
        ],
        verify: "Ask for the heat pump’s rated efficiency at 35 °C and at 55 °C from its datasheet, and get a price for the extra radiators. That turns the disagreement into arithmetic."
      },
      {
        claim: "Keep the gas boiler as a backup?",
        consensus_anchor: "two systems to maintain for others",
        type: "contradiction",
        severity: "minor",
        positions: [
          {
            stance: "Keep it for the first winter, then decide.",
            models: ["Mistral", "Gemini", "Grok"],
            quote: "Keep the gas boiler connected for the first winter as a backup."
          },
          {
            stance: "Take it out; a backup becomes the system that runs.",
            models: ["OpenAI", "Anthropic", "DeepSeek"],
            quote: "a backup tends to become the system that runs whenever it is cold."
          }
        ],
        verify: "Ask what the gas connection costs per year with no gas used. If it is small, one winter of backup is cheap insurance."
      },
      {
        claim: "Survey first, or winter test first?",
        consensus_anchor: "a matter of order, not of substance",
        type: "emphasis",
        severity: "minor",
        positions: [
          {
            stance: "Test first: it is free and shows which rooms matter.",
            models: ["OpenAI", "Gemini", "Grok"],
            quote: "Every room that stays warm is a room you do not need to touch."
          },
          {
            stance: "Survey first: without it every answer is a guess.",
            models: ["Anthropic", "Mistral", "DeepSeek"],
            quote: "Without it, every answer you get, including this one, is a guess."
          }
        ],
        verify: "Both camps want both. The test can start this week; the survey is what the quote should be built on."
      }
    ]
  },

  differences:
`The consensus answer is partially credible.

All six models agree that the house can work with a heat pump, that a room-by-room heat-loss calculation comes first, and that the heat pump must be sized from it. They contradict each other on the target flow temperature: three would keep most radiators and run at 55 °C, three would replace more of them for 45 °C, and they disagree on how much efficiency that difference is worth. They split again, more mildly, on keeping the gas boiler as a backup.

BestModel: Anthropic`
};

// Six authored viewpoints are instantiated for the configured Balanced families.
// Keep every claim/quote attached to the same viewpoint if an admin changes
// a preset family (for example Claude -> Kimi). These are local demo fixtures.
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

const DEMO_CONSENSUS_DELAY_MS = 4200;
const DEMO_CONSENSUS_JITTER_MS = 600;
// The structured contradiction check is synchronous in the local demo. Give
// its announced UI phase one deliberate beat so "Checking for contradictions"
// does not flash and disappear between two paints.
const DEMO_DIFFERENCES_REVIEW_MS = 1100;
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
const DEMO_CONSENSUS_STREAM = { wordsPerTick: 2, tickMs: 46 };

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

async function renderDemoConsensus(mainP, diffP) {
  const runId = demoRunId;
  // Der gefuehrte Lauf kennt bei einer echten Query drei Schritte: Antworten,
  // Konsens, Differences. Die Demo hat bisher nur Anfang und Ende gemeldet —
  // dadurch lief nach 6 s der Notausstieg (settleWithoutConsensus) und der
  // Lauf stand auf "Done", waehrend der Konsenstext noch geschrieben wurde.
  // Hier meldet die Demo dieselben Uebergaenge wie ein echter Lauf.
  window.App?.consensusPipeline?.onConsensusStart?.();

  // Konsens-Antwort als Streaming-Response aufbauen, danach sauber rendern,
  // damit Copy-Buttons und die Inline-Marker auf fertigem Markup sitzen.
  if (mainP) {
    await streamDemoInto(mainP, activeDemoData.consensus, runId, DEMO_CONSENSUS_STREAM);
    if (runId !== demoRunId) return;
    if (window.injectMarkdown) window.injectMarkdown(mainP, activeDemoData.consensus);
  }

  // Konsenstext steht: ab hier prueft die Auswertung auf Widersprueche.
  window.App?.consensusPipeline?.onDifferencesStart?.();
  await sleep(DEMO_DIFFERENCES_REVIEW_MS);
  if (runId !== demoRunId) return;

  // Differences exakt wie bei echten Queries: strukturierte Auswertung mit
  // Verdict-Header, Agreement-Badges und Contradiction-Karten. Nur wenn die
  // strukturierten Daten fehlen, greift der Legacy-Freitext.
  // Demo-Daten gehören zu keinem Bookmark: Resolve-Persistenz-Payload leeren,
  // damit eine Resolve-Runde hier nie ein altes Bookmark überschreibt.
  window.lastConsensusBookmarkPayload = null;
  const includedCount = (activeDemoData.differencesData?.models_compared || []).length || 6;
  const structuredRendered = window.renderConsensusInsights
    ? window.renderConsensusInsights(activeDemoData.differencesData, includedCount)
    : false;

  if (!structuredRendered && diffP) {
    window.App.differencesPanel?.expandForFallback?.();
    window.applyCredibilityFrame?.(diffP, activeDemoData.differences);
    const differences = window.colorizeCredibility?.(activeDemoData.differences)
      ?? activeDemoData.differences;
    if (window.injectMarkdown) {
      window.injectMarkdown(diffP, differences);
    } else {
      // This only happens while the app's deferred helpers are not available.
      // Keep the demo readable instead of depending on a CDN global directly.
      diffP.textContent = differences;
    }
  }

  // Demo-Ergebnisse sind reine lokale Produktvorschau. Sie dürfen weder das
  // Best-answer-Nutzungssignal noch die serverseitige Differences-Telemetrie
  // beeinflussen; deshalb gibt es hier bewusst keinen Persistenz-/Vote-Aufruf.
  window.App?.consensusPipeline?.onConsensusEnd?.();
  showPostDemoLoginPrompt();
}

/* === DEMO: Agent turn ===================================================
   Agent is where every question starts, so the demo plays an Agent turn on
   the real Agent surfaces: the activity line (agent-activity.js), the
   streamed answer (markdown-stream.js) and the answer check with its marks,
   agreement score and evidence links (agent-review.js). The run is local and
   scripted from the same fixtures as the Consensus demo: no request, no
   bookmark, no vote. agent-chat.js keeps the answer panel on screen while the
   demo owns it (App.agentChat.demoView), also for guests without Agent access.
   ======================================================================= */
const DEMO_AGENT_ID = "demo";
const DEMO_AGENT_HASH = "demo-answer-v1";
const DEMO_AGENT_BASIS = "demo-basis";
const DEMO_AGENT_STEPS = {
  plan: 900,            // first progress note
  compare: 1900,        // compare_models starts
  modelSpread: 5200,    // last comparison answer lands this long after compare
  afterCompare: 900,    // progress note, then the answer starts streaming
  check: 2300           // the judges hold the fixed answer against all six
};
const DEMO_AGENT_STREAM = { wordsPerTick: 3, tickMs: 42 };
const DEMO_AGENT_NOTES = {
  plan: "Whether this works depends on the heat loss of each room, not on the year the house was built. I will get six independent reads before I answer.",
  compared: "All six say it can work. They split on the flow temperature and on what it costs, so the answer has to say so instead of picking a side."
};

const capitalize = text => text.charAt(0).toUpperCase() + text.slice(1);
// The Agent writes its own answer: the Consensus fixture without its
// "Consensus:" label, opened by the verdict in bold.
function demoAgentAnswer() {
  return demoResponseMarkdown(activeDemoData.consensus || "")
    .replace(/^Consensus:\s*(.+)$/m, (_, verdict) => `**${capitalize(verdict.replace(/[.\s]*$/, ""))}.**`);
}
function demoAgentDifferences() {
  const data = JSON.parse(JSON.stringify(activeDemoData.differencesData || {}));
  for (const claim of data.claims || []) {
    if (typeof claim.anchor === "string" && /^Consensus:\s*/.test(claim.anchor)) {
      claim.anchor = capitalize(claim.anchor.replace(/^Consensus:\s*/, ""));
    }
  }
  return data;
}
function demoAgentModels() {
  return activeDemoModels.map(key => {
    const pref = window.App.modelPrefs.find(item => item.key === key);
    const select = pref && document.getElementById(pref.selectId);
    const option = select?.selectedOptions?.[0];
    return {
      key,
      label: (option?.textContent || "").trim() || pref?.label || key,
      model: select?.value || "",
      text: demoResponseMarkdown(activeDemoData.responses[key] || "")
    };
  });
}
// The review object a real turn carries (agent_review), reduced to one
// comparison: who has answered, the fixed answer version and its check.
function demoAgentReview({ answered, pending, status, answer, checked }) {
  const comparison = {
    id: "demo-comparison",
    basis_hash: DEMO_AGENT_BASIS,
    status: pending.length ? "running" : "completed",
    question: DEMO_TYPED_QUESTION,
    reason: "A five-figure decision where installers genuinely disagree: six models assess the house independently.",
    answers: answered.map(model => ({
      provider: model.key, provider_label: model.key,
      model: { label: model.label, model: model.model }, text: model.text, sources: []
    })),
    pending_models: pending.map(model => ({ label: model.label, model: model.model })),
    failed_models: []
  };
  const review = { status, comparisons: [comparison], versions: [], checks: [] };
  if (answer) {
    review.answer_version = "v1";
    review.answer_hash = DEMO_AGENT_HASH;
    review.versions = [{ id: "v1", text: answer, hash: DEMO_AGENT_HASH, status }];
  }
  if (checked) {
    review.checks = [{
      comparison_id: comparison.id, answer_hash: DEMO_AGENT_HASH, basis_hash: DEMO_AGENT_BASIS,
      status: "succeeded", issues: [], differences_data: checked
    }];
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
  body.parentElement?.querySelector(".agent-answer-actions")?.remove();
  window.App.agentDelegation?.demo?.(null);
}
// The calls behind the turn, as agent-delegation.js shows a real one: the
// model icons beside the clock, the activity panel and the light under it.
// Token counts are estimated from the fixture texts (about 4 characters per
// token), so the panel reads like a run without claiming a measured one.
const DEMO_AGENT_PROMPT_TOKENS = 1180;
function demoAgentUsage(text) {
  return { input_tokens: DEMO_AGENT_PROMPT_TOKENS, output_tokens: Math.round(text.length / 4), complete: true };
}
function demoAgentCalls({ models, answered, judges }) {
  const comparisons = models.map(model => {
    const done = answered.includes(model);
    return {
      id: `demo-${model.key}`, kind: "comparison", title: model.label,
      status: done ? "completed" : "working",
      model: { label: model.label, model: model.model, provider: model.key },
      text: done ? model.text : "", usage: done ? demoAgentUsage(model.text) : null
    };
  });
  const checks = judges.map(judge => ({
    id: `demo-${judge.id}`, kind: "judge", title: judge.title, status: judge.status,
    model: { label: "Answer check", model: "" },
    usage: judge.status === "completed" ? { input_tokens: 4200, output_tokens: 640, complete: true } : null
  }));
  const metered = [...comparisons, ...checks].filter(call => call.usage);
  const usage = metered.length ? {
    input_tokens: metered.reduce((n, call) => n + call.usage.input_tokens, 0),
    output_tokens: metered.reduce((n, call) => n + call.usage.output_tokens, 0),
    complete: true, measured_calls: metered.length, unmetered_calls: 0
  } : null;
  return { agents: [...comparisons, ...checks], usage };
}

async function runAgentDemoFlow() {
  const App = window.App;
  App.consensusPipeline?.dismiss?.();
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
  const answer = demoAgentAnswer();
  const checked = demoAgentDifferences();
  const started = Date.now();
  const events = [];
  let review = null;
  let answerText = "";
  let running = true;
  const answered = [];
  const judges = [];

  const paint = () => {
    if (!live() || !host) return;
    App.agentActivity?.render(host, {
      events, review, running, answerText,
      responding: Boolean(answerText),
      status: running ? "running" : "succeeded",
      elapsedMs: Date.now() - started
    });
    // The calls start with compare_models, as in a real turn.
    if (review && document.body.classList.contains("agent-demo-active")) App.agentDelegation?.demo?.({ turnId: `demo-${runId}`, running, ...demoAgentCalls({ models, answered, judges }) });
  };
  const at = async ms => {
    const wait = started + ms - Date.now();
    if (wait > 0) await sleep(wait);
    return live();
  };
  paint();

  if (!await at(DEMO_AGENT_STEPS.plan)) return;
  events.push({ version: 1, kind: "progress", id: "demo-plan", text: DEMO_AGENT_NOTES.plan });
  paint();

  // compare_models: six independent answers, each landing on its own beat.
  if (!await at(DEMO_AGENT_STEPS.compare)) return;
  const compareTool = { version: 1, kind: "tool", id: "demo-compare", name: "compare_models", status: "running" };
  events.push(compareTool);
  review = demoAgentReview({ answered, pending: models, status: "required" });
  paint();
  const order = DEMO_PHASES.order.filter(key => models.some(model => model.key === key))
    .concat(models.map(model => model.key).filter(key => !DEMO_PHASES.order.includes(key)));
  for (let i = 0; i < order.length; i++) {
    const landing = DEMO_AGENT_STEPS.compare + Math.round(DEMO_AGENT_STEPS.modelSpread * ((i + 1) / order.length) ** 1.15);
    if (!await at(landing)) return;
    answered.push(models.find(model => model.key === order[i]));
    review = demoAgentReview({ answered, pending: models.filter(model => !answered.includes(model)), status: "required" });
    paint();
  }
  compareTool.status = "succeeded";
  events.push({ version: 1, kind: "progress", id: "demo-compared", text: DEMO_AGENT_NOTES.compared });
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

  // The judges check that exact text; a quiet sheen says it is still going on.
  review = demoAgentReview({ answered, pending: [], status: "running", answer: answerText });
  judges.push({ id: "differences", title: "Differences judge", status: "working" },
    { id: "coverage", title: "Coverage judge", status: "working" });
  body?.classList.add("is-answer-checking");
  paint();
  await sleep(DEMO_AGENT_STEPS.check);
  if (!live()) return;

  review = demoAgentReview({ answered, pending: [], status: "succeeded", answer: answerText, checked });
  judges.forEach(judge => { judge.status = "completed"; });
  running = false;
  paint();
  if (body) {
    body.classList.remove("is-answer-checking");
    body.classList.add("is-answer-check-done");
    setTimeout(() => body.classList.remove("is-answer-check-done"), 450);
  }
  // Demo results are a local preview: no bookmark, no vote, no telemetry.
  App.agentReview?.render(body, review, { key: DEMO_AGENT_ID, question: DEMO_SCENARIO_PROMPT, reveal: true });
  App.agentAnswerActions?.render(body, { key: DEMO_AGENT_ID, text: answerText, running: false });
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

async function runDemoFlow() {
  // The demonstration always uses the complete Balanced lineup, not the
  // intersection of its fixture authors with a previous Daily/Custom choice.
  window.App.selectConsensusPreset?.('balanced');
  window.App.answerReader?.reset?.();
  const balanced = window.CONSENSUS_PRESETS?.find(preset => preset.id === 'balanced');
  activeDemoModels = window.App.modelPrefs.filter(pref => balanced?.models?.[pref.provider]).map(pref => pref.key);
  activeDemoData = buildDemoDataForModels(activeDemoModels);
  // Agent (the default, also for guests who come from the landing page)
  // plays an Agent turn; a chosen Compare or Consensus plays that mode.
  if (window.App?.runMode?.preference?.() === "agent" && window.App.agentChat?.demoView) {
    return runAgentDemoFlow();
  }
  const agentModeEnabled = window.App?.runMode?.pipeline?.() === true;
  // Auch die lokale Demo respektiert den Modus: Consensus baut den Thread
  // auf, Compare bleibt bei den sechs Antwortfenstern.
  if (agentModeEnabled) {
    window.exitHeroMode?.();
  } else {
    window.enterDirectComparisonView?.();
    window.App?.consensusPipeline?.dismiss?.();
  }
  const runId = ++demoRunId;
  const sendBtn = document.getElementById("sendButton");
  if (sendBtn) sendBtn.disabled = true;
  // Neue Demo-Runde: Konsens-Bereich zunächst ausblenden.
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

  window.setAgentModeStatus?.("complete");

  const consensusDiv = document.getElementById("consensusResponse");
  const mainP = window.App.consensusBodyEl(consensusDiv);
  const diffP = consensusDiv?.querySelector(".consensus-differences p");
  // Consensus/Differences gehoeren zum Consensus-Modus. In Compare endet die
  // Demo nach den sechs Modellantworten.
  const auto = window.App?.runMode?.pipeline?.() === true;

  if (auto) {
    window.resetConsensusInsights?.();
    window.resetCredibilityFrame?.(consensusDiv?.querySelector(".consensus-differences"));
    // Rahmenlosen Konsens-Bereich sanft einblenden, sobald alle Antworten fertig sind.
    window.revealConsensusOutput?.();
    if (mainP) mainP.innerHTML = window.spinnerHTML;
    if (diffP) diffP.innerHTML = window.spinnerHTML;
    setTimeout(
      () => renderDemoConsensus(mainP, diffP),
      DEMO_CONSENSUS_DELAY_MS + Math.floor(Math.random() * DEMO_CONSENSUS_JITTER_MS)
    );
  } else {
    showPostDemoLoginPrompt();
  }

  if (sendBtn) sendBtn.disabled = false;
}

function createStartDemoChip() {
  const storage = getDemoStorage();
  if (storage?.getItem("demoChipDismissed")) return;
  const container = document.querySelector(".chat-input-container");
  if (!container || container.querySelector(".demo-chip")) return;
  const questionInput = document.getElementById("questionInput");

  const btn = document.createElement("button");
  btn.className = "demo-chip demo-action send-glow";
  btn.type = "button";
  btn.setAttribute("aria-label", "Start interactive demo");
  // Zwei Beschriftungen, immer genau eine sichtbar. Auf einem 375er Schirm
  // teilen sich (+), Lauf-Schalter, dieser Knopf und Senden 315 px.
  // "Try the demo" passt dort nicht in eine Zeile mit dem Senden-Knopf.
  // Welche Beschriftung gilt, entscheidet
  // components-misc.css; der aria-Name bleibt in beiden Faellen derselbe.
  btn.innerHTML =
    '<span class="demo-action-icon" aria-hidden="true"><svg viewBox="0 0 16 16" fill="currentColor"><path d="M5 3.5v9l7-4.5z"></path></svg></span>' +
    '<span class="demo-chip-label demo-chip-label-full">Try the demo</span>' +
    '<span class="demo-chip-label demo-chip-label-short">Demo</span>';

  const inputActions = container.querySelector(".input-actions-container");
  if (inputActions) {
    inputActions.prepend(btn);
  } else {
    container.appendChild(btn);
  }

  const syncChipState = () => {
    const hasQuestionText = Boolean(questionInput?.value.length);
    container.classList.toggle("has-question-input", hasQuestionText);
    btn.hidden = hasQuestionText;
    btn.tabIndex = hasQuestionText ? -1 : 0;
  };

  window.syncDemoChipState = syncChipState;

  if (questionInput) {
    questionInput.addEventListener("input", event => {
      syncChipState();
      if (questionInput.value.length && event.isTrusted) {
        storage?.setItem("demoChipDismissed", "1");
        btn.remove();
      }
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
  if (!modal) return;

  modal.style.display = "block";
  window.trackAppEvent?.("auth_modal_open", { source: "post_demo" });
  requestAnimationFrame(() => document.getElementById("loginEmail")?.focus());
});

function toggleSettingsCollapse(contentId, arrowId) {
  const content = document.getElementById(contentId);
  const arrow = document.getElementById(arrowId);
  if (!content) return;

  // The initial closed state comes from a template CSS class. Inspect the
  // effective value so the first click opens it even before an inline value
  // has ever been written.
  if (window.getComputedStyle(content).display === "none") {
    content.style.display = "block";
    if (arrow) arrow.classList.add("rotated");
    if (arrow) arrow.innerHTML = "&#9650;";
  } else {
    content.style.display = "none";
    if (arrow) arrow.classList.remove("rotated");
    if (arrow) arrow.innerHTML = "&#9660;";
  }
}

window.toggleSettingsCollapse = toggleSettingsCollapse;
