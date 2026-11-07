import { describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// The calm view every account starts with (a casual user sees far too much,
// and no console commands by default): under the head one line says in
// everyday words what the agent does now, or while it thinks what it is
// after, each held a while. The Display switch
// "Detailed progress" (account setting detailed_progress) brings back the
// lines in full; the history under the head keeps everything either way.
function setup() {
  const app = loadScripts(["static/js/user-settings.js", "static/js/agent-activity.js"], { body: '<div id="host"></div>' });
  const { window } = app;
  // The lines' own clock and timers: a test moves time on by hand.
  const clock = { now: 1000, timers: [] };
  Object.defineProperty(window.performance, "now", { configurable: true, value: () => clock.now });
  window.setTimeout = (fn, ms = 0) => { clock.timers.push({ fn, at: clock.now + ms }); return clock.timers.length; };
  window.clearTimeout = id => { if (clock.timers[id - 1]) clock.timers[id - 1].done = true; };
  const host = app.document.getElementById("host");
  const activity = window.App.agentActivity;
  const events = [];
  const render = (spec = {}) => activity.render(host, { running: true, status: "running", events, ...spec });
  const preview = () => host.querySelector(".agent-progress");
  const status = () => preview().querySelector(".agent-current-status")?.textContent;
  // The thought is the status line itself while no step runs.
  const thought = () => status();
  // Time passes, and the timers whose time came run.
  const wait = ms => {
    clock.now += ms;
    for (const timer of clock.timers) {
      if (!timer.done && timer.at <= clock.now) { timer.done = true; timer.fn(); }
    }
  };
  return { app, window, host, activity, events, render, preview, status, thought, wait, clock };
}

const tool = fields => ({ version: 1, kind: "tool", id: "completion:1:call_1/tool", ...fields });
const note = (id, text) => ({ version: 1, kind: "progress", id: `${id}/note`, step_id: id, text });

describe("the calm live view", () => {
  it("says what the agent does in words: no command, no output, no fold of earlier steps", () => {
    const { activity, events, render, preview, status, host, wait } = setup();
    activity.receive(events, note("completion:1", "I'll install the charting library first. Then I build the chart."));
    render();
    // Before the step, the agent's own note is the line.
    expect(status()).toBe("I'll install the charting library first.");
    activity.receive(events, tool({ name: "vm_exec", status: "running", command: "pip install pandas matplotlib",
      started_at: new Date().toISOString(), output: "Collecting pandas\nDownloading pandas-2.3.whl (12 MB)\n" }));
    render();
    // The note stands its seconds, then the running step takes the line.
    expect(status()).toBe("I'll install the charting library first.");
    wait(4100);
    expect(status()).toBe("Working in the workspace…");
    // Nothing of the console: no block, no code, no output, no command.
    expect(preview().querySelector(".agent-vm, code, pre, .agent-vm-fold")).toBeNull();
    expect(preview().textContent).not.toContain("pip");
    expect(preview().textContent).not.toContain("Collecting");
    // One line of what it does, nothing under it (no thin subtitle).
    expect([...preview().children].map(child => child.className)).toEqual([
      "agent-progress-step agent-current-status"]);
    expect(preview().querySelector(".agent-current-status").getAttribute("role")).toBe("status");
    // The history under the head keeps the command, a click away.
    expect(host.querySelector(".agent-activity-content .agent-vm-target").textContent).toBe("pip install pandas matplotlib");
    // Earlier steps fold nowhere: they are in the history.
    for (let index = 2; index <= 5; index += 1) {
      activity.receive(events, tool({ id: `completion:${index}:call/tool`, name: "vm_exec", status: "succeeded",
        command: `python3 step${index}.py`, exit_code: 0 }));
    }
    activity.receive(events, tool({ id: "completion:6:call/tool", name: "vm_write_file", status: "running",
      path: "/home/sprite/game/snake.js" }));
    render();
    expect(preview().querySelector(".agent-vm-fold")).toBeNull();
    expect(preview().textContent).not.toContain("step");
    activity.dispose(host);
  });

  it("names a file by its name and a page by its site, never a path or a place on the page", () => {
    const { activity, events, render, status, wait, host } = setup();
    const step = (id, fields) => { activity.receive(events, tool({ id: `completion:${id}:call/tool`, ...fields })); render(); wait(1300); };
    step(1, { name: "vm_write_file", status: "running", path: "/home/sprite/game/snake.js" });
    expect(status()).toBe("Writing “snake.js”…");
    step(2, { name: "vm_edit_file", status: "running", path: "C:\\work\\index.html" });
    expect(status()).toBe("Editing “index.html”…");
    step(3, { name: "browser", action: "open", status: "running", url: "https://www.bild.de/regional/ticker" });
    expect(status()).toBe("Opening bild.de…");
    step(4, { name: "browser", action: "click", status: "running", ref: "e12" });
    expect(status()).toBe("Using the browser…");
    step(5, { name: "browser", action: "find", status: "running", query: "Förderfähige Kosten" });
    expect(status()).toBe("Reading the page…");
    step(6, { name: "vm_install_packages", status: "running", packages: ["ffmpeg"] });
    expect(status()).toBe("Setting up the workspace…");
    // Steps outside the workspace keep their words.
    step(7, { name: "web_search", status: "running" });
    expect(status()).toBe("Searching the web…");
    step(8, { name: "read_source", status: "running", host: "arxiv.org" });
    expect(status()).toBe("Reading arxiv.org…");
    activity.dispose(host);
  });

  it("holds a line a while: a step that comes and goes at once never flashes", () => {
    const { activity, events, render, status, wait, host } = setup();
    render();
    expect(status()).toBe("Thinking…");
    // A quick read starts and ends before the line stood its time.
    wait(300);
    activity.receive(events, tool({ name: "vm_read_file", status: "running", path: "/home/sprite/notes.md" }));
    render();
    expect(status()).toBe("Thinking…");
    activity.receive(events, tool({ name: "vm_read_file", status: "succeeded", path: "/home/sprite/notes.md" }));
    activity.receive(events, tool({ id: "completion:2:call/tool", name: "web_search", status: "running" }));
    render();
    expect(status()).toBe("Thinking…");
    // When its time is up, the newest takes the line, without a new report.
    wait(1000);
    expect(status()).toBe("Searching the web…");
    // A line that stood its time gives way at once.
    wait(2000);
    activity.receive(events, tool({ id: "completion:2:call/tool", name: "web_search", status: "succeeded" }));
    render();
    expect(status()).toBe("Thinking…");
    activity.dispose(host);
  });

  it("shows one thought: a summary's newest heading, else its newest short sentence, held for seconds", () => {
    const { activity, events, render, thought, wait, host } = setup();
    const reasoning = (id, text, format = "summary") => activity.receive(events,
      { version: 1, step_id: "completion:1", kind: "reasoning", id, format, text, append: true });
    reasoning("r1", "**Assessing the question**\n\nI need to weigh the running costs of a heat pump.");
    render();
    expect(thought()).toBe("Assessing the question");
    // More words under the same heading change nothing.
    reasoning("r1", " The insulation matters most here.");
    render();
    expect(thought()).toBe("Assessing the question");
    // A new heading waits until the one shown stood its four seconds.
    wait(1000);
    reasoning("r1", "\n\n**Checking the numbers**\n\nTypical seasonal performance is lower.");
    render();
    expect(thought()).toBe("Assessing the question");
    wait(3100);
    expect(thought()).toBe("Checking the numbers");
    // Thinking without headings speaks with its newest complete sentence.
    wait(5000);
    reasoning("r2", "The user wants the 2026 rates. I should check the official site first. Then", "text");
    render();
    expect(thought()).toBe("I should check the official site first.");
    // A scrap of deliberation says nothing to the user: the line keeps its thought.
    wait(5000);
    reasoning("r2", " Also maybe share nothing.", "text");
    render();
    expect(thought()).toBe("I should check the official site first.");
    // A sentence too long for the line leaves the one before it standing: nothing is cut.
    wait(5000);
    reasoning("r2", ` maybe ${"compare ".repeat(20)}all of them.`, "text");
    render();
    expect(thought()).toBe("I should check the official site first.");
    expect(thought()).not.toContain("…");
    activity.dispose(host);
  });

  it("keeps what waits on the user and what the user wrote, and the plan above", () => {
    const { activity, events, render, preview, status, host } = setup();
    activity.receive(events, tool({ name: "update_plan", status: "succeeded",
      items: [{ content: "Find the rates", status: "completed" }, { content: "Compare them", status: "in_progress" }] }));
    activity.receive(events, tool({ id: "completion:2:call/tool", name: "web_search", status: "succeeded" }));
    activity.receive(events, { version: 1, kind: "progress", id: "steer:1", from_user: true, text: "Also look at Austria." });
    render();
    expect(preview().firstElementChild.classList.contains("agent-plan")).toBe(true);
    expect(preview().querySelector(".agent-plan summary").textContent).toBe("Plan · 1 of 2 done");
    expect(preview().querySelector(".agent-user-note .agent-user-note-text").textContent).toBe("Also look at Austria.");
    // A reviewer's pause: no line of work while the run waits, the pause says why.
    activity.receive(events, { version: 1, kind: "hold", id: "hold:1", state: "waiting", halt: "harm",
      reviewer: "Gemini", reason: "This deletes the folder." });
    render();
    expect(status()).toBeUndefined();
    expect(preview().querySelector(".agent-hold-step")).not.toBeNull();
    activity.dispose(host);
  });

  it("quotes the comparison models while they answer, and says why it waits for tokens", () => {
    const { activity, events, render, preview, thought, host } = setup();
    activity.receive(events, note("completion:1", "I'll ask other models."));
    activity.receive(events, tool({ name: "compare_models", status: "running" }));
    render({ highlights: [{ id: "a", order: 1, label: "Gemini", text: "Checking the 2026 figures." }] });
    const lines = [...preview().querySelectorAll("p")].map(p => p.textContent);
    expect(lines).toEqual(["Gemini: Checking the 2026 figures."]);
    // The status line stays the step's while the models answer, no thought on it.
    expect(preview().querySelector(".agent-current-status")?.textContent ?? "").not.toContain("I'll ask other models.");
    activity.receive(events, tool({ name: "compare_models", status: "succeeded" }));
    activity.receive(events, { version: 1, kind: "status", id: "wait", status: "waiting", text: "Waiting for the allowance." });
    render();
    expect(preview().textContent).toContain("Waiting for the allowance.");
    expect(preview().textContent).not.toContain("I'll ask other models.");
    activity.dispose(host);
  });

  it("brings back the lines in full with the Display switch, and the calm line without it", () => {
    const { window, activity, events, render, preview, status, host } = setup();
    activity.receive(events, tool({ name: "vm_exec", status: "running", command: "npm test", output: "PASS\n" }));
    render();
    expect(preview().querySelector(".agent-vm")).toBeNull();
    window.App.userSettings.set("detailed_progress", true);
    render();
    expect(preview().querySelector(".agent-vm .agent-vm-target").textContent).toBe("npm test");
    expect(preview().querySelector(".agent-current-status")).toBeNull();
    window.App.userSettings.set("detailed_progress", false);
    render();
    expect(preview().querySelector(".agent-vm")).toBeNull();
    expect(status()).toBe("Working in the workspace…");
    activity.dispose(host);
  });

  it("lets the answer take the lines' place as before", () => {
    const { activity, events, render, preview, host } = setup();
    activity.receive(events, note("completion:1", "I have what I need."));
    render();
    expect(preview().hidden).toBe(false);
    render({ answerText: "The answer." });
    expect(preview().hidden).toBe(true);
    render({ running: false, status: "succeeded", answerText: "The answer." });
    expect(preview().childElementCount).toBe(0);
    activity.dispose(host);
  });
});
