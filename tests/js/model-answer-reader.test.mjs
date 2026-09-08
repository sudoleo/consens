import { afterEach, describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const contexts = [];
function boot({ desktop = true } = {}) {
  let visible = null;
  const ctx = loadScripts(["static/js/model-answer-reader.js"], {
    body: `<button id="agentModeAnswersToggle"><span class="consensus-tab-label">Compare answers</span></button>
      <div id="threadHistory"></div><div class="response-section"><div class="response-box" id="openaiResponse"><div class="collapsible-content"></div></div></div>`,
    before(window) {
      window.matchMedia = query => ({ matches: query.includes("1400") ? desktop : desktop, addEventListener() {} });
      window.HTMLDialogElement.prototype.show = function () { this.open = true; };
      window.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
      window.HTMLDialogElement.prototype.close = function () { this.open = false; };
      window.HTMLElement.prototype.scrollIntoView = vi.fn();
      window.scrollTo = vi.fn();
      window.injectMarkdown = vi.fn((el, markdown) => {
        const p = window.document.createElement("p"); p.textContent = markdown; el.replaceChildren(p);
      });
      window.App = {
        modelPrefs: [{ key: "OpenAI", responseId: "openaiResponse", textId: "openaiLabel" }],
        runRegistry: { visible: () => visible },
      };
    }
  });
  contexts.push(ctx);
  return { ...ctx, reader: ctx.window.App.answerReader,
    project(context) { visible = context; ctx.window.App.answerReader.project(context); } };
}
function run(id = "r1", options = {}) {
  return {
    runId: id, question: `Question ${id}`, config: { agentMode: true, providers: [
      { provider: "OpenAI", modelLabel: "GPT" }, { provider: "Anthropic", modelLabel: "Claude" }
    ] }, consensus: {}, modelResults: {
      OpenAI: { text: `GPT answer ${id}`, status: "complete", sources: [{ title: "First source", url: "https://example.com/first" }] },
      Anthropic: { text: `Claude answer ${id}`, status: "streaming" }
    }, ...options
  };
}
function archive(ctx, id = "t1") {
  const turn = { turn_id: id, question: `Archived ${id}`, consensus: "Saved consensus",
    model_answers: { OpenAI: { answer: `Saved GPT ${id}`, model_label: "Old GPT", sources: [{title: "Saved source", url: "https://example.com/saved"}] },
      Anthropic: { answer: `Saved Claude ${id}`, model_label: "Old Claude" } } };
  const node = ctx.document.createElement("article"); node.className = "thread-history-turn";
  const tabs = ctx.document.createElement("div"); node.appendChild(tabs);
  ctx.reader.registerTurn(node, turn, tabs);
  ctx.document.getElementById("threadHistory").appendChild(node);
  return { node, turn, button: tabs.querySelector("button") };
}
afterEach(() => { contexts.splice(0).forEach(ctx => ctx.dom.window.close()); });

describe("model answer reader", () => {
  it("keeps saved model versions independent of current model choices", () => {
    const ctx = boot();
    ctx.project(run());
    ctx.reader.showDirectBookmark({ id: 'saved', query: 'Earlier question',
      responses: {OpenAI: 'Earlier answer'}, model_labels: {OpenAI: 'GPT saved version'} });
    expect(ctx.document.querySelector('.answer-reader-caption').textContent).toBe('GPT saved version');
  });

  it.each([undefined, 'OpenAI', 'Model not recorded'])("omits unknown legacy version %s without inventing one", label => {
    const ctx = boot();
    ctx.project(run());
    ctx.reader.showDirectBookmark({ id: 'legacy', query: 'Earlier question',
      responses: {OpenAI: 'Earlier answer'}, model_labels: {OpenAI: label} });
    expect(ctx.document.querySelector('.answer-reader-caption').hidden).toBe(true);
    expect(ctx.document.querySelector('.answer-reader-answer h3').textContent).toBe('ChatGPT');
    expect(ctx.document.querySelector('.answer-reader-body').textContent).toBe('Earlier answer');
  });

  it("uses the frozen model ID if a live run has no display label", () => {
    const ctx = boot(); const state = run(); state.config.agentMode = false;
    Object.assign(state.config.providers[0], {modelLabel: '', modelId: 'openai/gpt-saved'});
    ctx.project(state);
    expect(ctx.document.querySelector('.answer-reader-caption').textContent).toBe('openai/gpt-saved');
  });

  it("shows only the selected original and updates streaming text without changing selection or scroll", () => {
    const ctx = boot(); const state = run(); ctx.project(state);
    ctx.reader.openLive("Claude");
    expect(ctx.document.querySelector(".answer-reader-body").textContent).toBe("Claude answer r1");
    const scroll = ctx.document.getElementById("answerReaderScroll"); scroll.scrollTop = 123;
    state.modelResults.Anthropic.text += " continued"; ctx.project(state);
    expect(ctx.document.querySelectorAll(".answer-reader-answer")).toHaveLength(1);
    expect(ctx.document.querySelector(".answer-reader-body").textContent).toContain("continued");
    expect(scroll.scrollTop).toBe(123);
    ctx.document.querySelector('#answerReaderModels [data-provider="OpenAI"]').click();
    scroll.scrollTop = 47;
    ctx.document.querySelector('#answerReaderModels [data-provider="Anthropic"]').click();
    expect(scroll.scrollTop).toBe(123);
  });

  it("keeps an archived question and its own sources selected when a later turn streams", () => {
    const ctx = boot(); const saved = archive(ctx); const state = run(); ctx.project(state);
    saved.button.click();
    ctx.project(run("r2"));
    expect(ctx.document.querySelector(".answer-reader-dialog").open).toBe(true);
    expect(ctx.document.querySelector(".answer-reader-body").textContent).toBe("Saved GPT t1");
    expect(ctx.document.querySelector(".answer-reader-sources a").href).toBe("https://example.com/saved");
    expect(ctx.document.getElementById("answerReaderTurn").value).toBe("turn:t1");
  });

  it("keeps a completed live answer pinned when it moves into the conversation history", () => {
    const ctx = boot(); const state = run(); state.consensus.completedTurn = {turn_id: "t1"}; ctx.project(state);
    ctx.reader.openLive("OpenAI");
    const saved = archive(ctx); saved.turn.question = state.question;
    ctx.project(run("r2"));
    expect(ctx.document.querySelector(".answer-reader-dialog").open).toBe(true);
    expect(ctx.document.getElementById("answerReaderTurn").value).toBe("turn:t1");
    expect(ctx.document.querySelector(".answer-reader-body").textContent).toBe("Saved GPT t1");
  });

  it("closes when switching to an unrelated run and on logout/reset", () => {
    const ctx = boot(); ctx.project(run()); ctx.reader.openLive(); ctx.project(run("unrelated"));
    expect(ctx.document.querySelector(".answer-reader-dialog").open).toBe(false);
    ctx.reader.openLive(); ctx.reader.reset();
    expect(ctx.document.getElementById("modelAnswerReader").hidden).toBe(true);
    expect(ctx.document.body.classList.contains("answer-reader-docked")).toBe(false);
  });

  it("preserves an untouched direct answer while another model streams", () => {
    const ctx = boot(); const state = run(); state.config.agentMode = false; ctx.project(state);
    const first = ctx.document.querySelector('.answer-reader-answer');
    first.querySelector('details').open = true;
    state.modelResults.Anthropic.text += ' continued'; ctx.project(state);
    expect(ctx.document.querySelector('.answer-reader-answer')).toBe(first);
    expect(first.querySelector('details').open).toBe(true);
    expect(ctx.document.querySelector('.answer-reader-body[data-provider="Anthropic"]').textContent).toContain('continued');
  });

  it("shows every direct answer inline including failed models", () => {
    const ctx = boot(); const state = run(); state.config.agentMode = false;
    state.modelResults.Anthropic = {status: "error", error: "Model timed out"}; ctx.project(state);
    expect(ctx.document.querySelector(".response-section > #modelAnswerReader")).not.toBeNull();
    expect(ctx.document.querySelector(".answer-reader-dialog").open).toBe(false);
    expect(ctx.document.querySelectorAll('.answer-reader-answer')).toHaveLength(2);
    expect(ctx.document.querySelector('.answer-reader-body[data-provider="Anthropic"]').textContent).toBe("Model timed out");
    expect(ctx.document.getElementById("answerReaderStatus").textContent).toContain("1 unavailable");
  });

  it("compares two distinct models and switches between them on phones", () => {
    const ctx = boot({desktop: false}); ctx.project(run()); ctx.reader.openLive();
    ctx.document.getElementById("answerReaderCompare").click();
    expect(ctx.document.querySelector(".answer-reader-dialog").dataset.modal).toBe("true");
    expect(ctx.document.getElementById("answerReaderMobile").hidden).toBe(false);
    const a = ctx.document.getElementById("answerReaderA"); const b = ctx.document.getElementById("answerReaderB");
    b.value = a.value; b.dispatchEvent(new ctx.window.Event("change"));
    expect(a.value).not.toBe(b.value);
    ctx.document.getElementById("answerReaderSideB").click();
    expect(ctx.document.getElementById("answerReaderColumns").dataset.mobileSide).toBe("b");
    expect(ctx.document.querySelectorAll(".answer-reader-answer")).toHaveLength(2);
  });

  it("uses actual reader width for tablets with a sidebar", () => {
    const ctx = boot(); ctx.project(run());
    Object.defineProperty(ctx.document.getElementById("modelAnswerReader"), "clientWidth", {value: 620});
    ctx.reader.openLive(); ctx.document.getElementById("answerReaderCompare").click();
    expect(ctx.document.getElementById("answerReaderMobile").hidden).toBe(false);
    expect(ctx.document.getElementById("answerReaderColumns").classList.contains("is-narrow")).toBe(true);
  });

  it("uses one compact model picker on phones instead of a tall stack of model tabs", () => {
    const ctx = boot({desktop: false}); ctx.project(run()); ctx.reader.openLive();
    expect(ctx.document.getElementById("answerReaderModels").hidden).toBe(true);
    expect(ctx.document.getElementById("answerReaderSingle").hidden).toBe(false);
    const model = ctx.document.getElementById("answerReaderModel");
    model.value = "Anthropic"; model.dispatchEvent(new ctx.window.Event("change"));
    expect(ctx.document.querySelector(".answer-reader-body").textContent).toBe("Claude answer r1");
  });

  it("opens claim links in the correct archived model and restores focus on close", () => {
    const ctx = boot({desktop: false}); const saved = archive(ctx); ctx.project(run());
    expect(ctx.reader.canOpenStored(saved.node, "Claude")).toBe(true);
    ctx.reader.openStored(saved.node, "Claude", "Saved Claude");
    expect(ctx.document.querySelector(".answer-reader-body").textContent).toBe("Saved Claude t1");
    expect(ctx.document.querySelector(".quote-flash-block")).not.toBeNull();
    ctx.document.getElementById("answerReaderClose").click();
    expect(ctx.document.activeElement).toBe(saved.button);
  });

  it("renders model names as text and never creates unsafe source links", () => {
    const ctx = boot(); const state = run(); state.config.providers[0].modelLabel = '<img src=x onerror="alert(1)">';
    state.modelResults.OpenAI.sources = [{url: "javascript:alert(1)", title: "Bad link"}]; ctx.project(state); ctx.reader.openLive();
    expect(ctx.document.querySelector("#modelAnswerReader img")).toBeNull();
    expect(ctx.document.querySelector(".answer-reader-sources a")).toBeNull();
  });
});
