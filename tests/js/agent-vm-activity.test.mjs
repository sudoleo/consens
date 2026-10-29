import { describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

// The agent's own VM (agent_vm_tools.py): each call is one activity event,
// updated while it runs. The chat shows it compactly like a terminal: the
// command and how it ended on one line, its output below, open while it runs
// and folded once it is done.
function setup() {
  const app = loadScripts(["static/js/agent-activity.js"], { body: '<div id="host"></div>' });
  return { app, host: app.document.getElementById("host"), activity: app.window.App.agentActivity };
}

function vm(fields) {
  return { version: 1, kind: "tool", id: "completion:1:call_1/tool", name: "vm_exec", ...fields };
}

describe("VM calls in the activity", () => {
  it("shows a running command with its live output, then folds it with exit code and duration", () => {
    const { host, activity } = setup();
    const events = [];
    activity.receive(events, vm({ status: "running", command: "pip install pandas", cwd: "/home/sprite" }));
    activity.receive(events, vm({ status: "running", output: "Collecting pandas\nDownloading…\n", output_truncated: false }));
    activity.render(host, { running: true, status: "running", events, elapsedMs: 4000 });
    // Live, in the progress lines under the collapsed activity.
    const live = host.querySelector(".agent-progress .agent-vm");
    expect(live.dataset.status).toBe("running");
    expect(live.querySelector(".agent-vm-target").textContent).toBe("pip install pandas");
    expect(live.querySelector(".agent-vm-meta").textContent).toBe("Running…");
    expect(live.open).toBe(true);
    expect(live.querySelector(".agent-vm-output").textContent).toBe("Collecting pandas\nDownloading…\n");
    // Command and output are data: never translated.
    expect(live.querySelector(".agent-vm-target").tagName).toBe("CODE");
    expect(live.querySelector(".agent-vm-output").tagName).toBe("PRE");
    expect(live.querySelector(".agent-vm-head").hasAttribute("data-i18n-skip")).toBe(true);
    // The updates add up: the end keeps what earlier updates said.
    activity.receive(events, vm({ status: "running", output: "Successfully installed pandas\n", output_truncated: true,
      exit_code: 1, duration_ms: 12400, timed_out: false }));
    activity.receive(events, vm({ status: "succeeded", command: "pip install pandas", cwd: "/home/sprite" }));
    activity.render(host, { running: true, status: "running", events, elapsedMs: 16000 });
    expect(live.open).toBe(false);
    // A command that failed says so in words and in the dispute tone (UX audit F1).
    expect(live.querySelector(".agent-vm-meta").textContent).toBe("Failed · code 1 · 12s");
    expect(live.dataset.outcome).toBe("failed");
    // A cut output says so before its end.
    expect(live.querySelector(".agent-vm-output").textContent).toBe("…\nSuccessfully installed pandas\n");
    // The history holds the same block, folded.
    const saved = host.querySelector(".agent-activity-content .agent-vm");
    expect(saved.classList.contains("agent-activity-tool")).toBe(true);
    expect(saved.open).toBe(false);
    expect(saved.querySelector(".agent-vm-target").textContent).toBe("pip install pandas");
  });

  it("keeps the reader's choice to open a finished command", () => {
    const { host, activity } = setup();
    const events = [];
    activity.receive(events, vm({ status: "running", command: "ls", output: "a\nb\n" }));
    activity.render(host, { running: true, status: "running", events });
    const live = host.querySelector(".agent-progress .agent-vm");
    live.querySelector("summary").click();
    activity.receive(events, vm({ status: "succeeded", exit_code: 0, duration_ms: 300 }));
    activity.render(host, { running: true, status: "running", events });
    // The reader closed it while it ran; it stays as the reader left it.
    expect(live.open).toBe(false);
    // A quick, successful command needs no words after it.
    expect(live.querySelector(".agent-vm-meta").textContent).toBe("");
  });

  it("names the file of a read or write and a VM that was not available, calmly", () => {
    const { host, activity } = setup();
    const events = [];
    activity.receive(events, { version: 1, kind: "tool", id: "s:1/tool", name: "vm_write_file", status: "succeeded",
      path: "/home/sprite/stats.py", bytes: 9 });
    activity.receive(events, { version: 1, kind: "tool", id: "s:2/tool", name: "vm_exec", status: "failed",
      command: "ls", outcome: "unavailable" });
    activity.receive(events, { version: 1, kind: "tool", id: "s:3/tool", name: "vm_edit_file", status: "succeeded",
      path: "/home/sprite/calc.py" });
    activity.receive(events, { version: 1, kind: "tool", id: "s:4/tool", name: "github_import", status: "succeeded",
      path: "/home/sprite/repos/app", repo: "owner/app" });
    activity.renderTurn(host, { status: "completed", agent_activity: events, assistant_response: "Done." });
    const [write, failed, edit, imported] = host.querySelectorAll(".agent-activity-content .agent-vm");
    // A repository the backend brought into the VM (agent_github.py).
    expect(imported.querySelector(".agent-vm-verb").textContent).toBe("Imported the repository into");
    expect(imported.querySelector(".agent-vm-target").textContent).toBe("/home/sprite/repos/app");
    expect(write.querySelector(".agent-vm-verb").textContent).toBe("Wrote the file");
    expect(write.querySelector(".agent-vm-target").textContent).toBe("/home/sprite/stats.py");
    // An exact replacement (vm_edit_file, 2026-10-26) says so with its file.
    expect(edit.querySelector(".agent-vm-verb").textContent).toBe("Edited the file");
    expect(edit.querySelector(".agent-vm-target").textContent).toBe("/home/sprite/calc.py");
    // Nothing to open without output.
    expect(write.classList.contains("has-output")).toBe(false);
    expect(failed.querySelector(".agent-vm-meta").textContent).toBe("Workspace not available");
    expect(failed.textContent).not.toMatch(/error|exception|HTTP/i);
  });

  // Like Claude Code: the earlier steps fold into one line, the latest note
  // and command stay in view (2026-10-26; before, a screen of commands).
  it("folds the earlier steps of a VM run into one line while it works", () => {
    const { host, activity } = setup();
    const events = [];
    const note = (n, text) => activity.receive(events, { version: 1, kind: "progress", id: `p${n}`, text });
    const command = (n, fields) => activity.receive(events, vm({ id: `c:${n}/tool`, ...fields }));
    note(1, "Let me look around."); command(1, { status: "succeeded", command: "ls -la", exit_code: 0 });
    note(2, "Let me check the file."); command(2, { status: "succeeded", command: "file chart.png", exit_code: 0 });
    activity.render(host, { running: true, status: "running", events });
    const preview = host.querySelector(".agent-progress");
    // One earlier command is no list worth folding.
    expect(preview.querySelector(".agent-vm-fold")).toBeNull();
    note(3, "Let me rebuild the chart."); command(3, { status: "running", command: "python3 chart.py" });
    activity.render(host, { running: true, status: "running", events });
    const fold = preview.querySelector(".agent-vm-fold");
    expect(fold.querySelector("summary").textContent).toBe("Ran 2 commands");
    expect(fold.open).toBe(false);
    expect([...fold.querySelectorAll(".agent-vm-target")].map(el => el.textContent)).toEqual(["ls -la", "file chart.png"]);
    expect(fold.textContent).toContain("Let me check the file.");
    // In view: the fold, the note leading into the command at work, the command.
    expect([...preview.children].map(el => el.className.split(" ")[0])).toEqual(["agent-vm-fold", "", "agent-vm"]);
    expect(preview.children[1].textContent).toBe("Let me rebuild the chart.");
    expect(preview.children[2].querySelector(".agent-vm-target").textContent).toBe("python3 chart.py");
    // A read among them makes them steps; the reader's open fold stays open.
    fold.open = true;
    activity.receive(events, { version: 1, kind: "tool", id: "c:4/tool", name: "vm_read_file", status: "succeeded",
      path: "/home/sprite/chart.py" });
    command(5, { status: "running", command: "ls /tmp" });
    activity.render(host, { running: true, status: "running", events });
    expect(fold.querySelector("summary").textContent).toBe("4 earlier steps");
    expect(fold.open).toBe(true);
    expect(preview.children[1].querySelector(".agent-vm-target").textContent).toBe("ls /tmp");
    // The history keeps every step as it was.
    expect(host.querySelectorAll(".agent-activity-content .agent-vm")).toHaveLength(5);
  });

  // update_plan (2026-10-26), like Claude Code's todo list.
  it("pins the latest plan above the live progress and keeps it once in the timeline", () => {
    const { host, activity } = setup();
    const events = [];
    const plan = (n, statuses, fields = {}) => activity.receive(events, { version: 1, kind: "tool", id: `p:${n}/tool`,
      name: "update_plan", status: "succeeded", ...fields,
      items: ["Read the data", "Fit the model", "Plot the result"].map((content, i) => ({ content, status: statuses[i] })) });
    plan(1, ["in_progress", "pending", "pending"]);
    activity.receive(events, vm({ id: "c:1/tool", status: "succeeded", command: "head data.csv", exit_code: 0 }));
    plan(2, ["completed", "in_progress", "pending"]);
    activity.receive(events, vm({ id: "c:2/tool", status: "running", command: "python fit.py" }));
    activity.render(host, { running: true, status: "running", events });
    const preview = host.querySelector(".agent-progress");
    // One plan, the latest, first and open; the commands follow in their order.
    const pinned = preview.querySelectorAll(".agent-plan");
    expect(pinned).toHaveLength(1);
    expect(preview.firstElementChild).toBe(pinned[0]);
    expect(pinned[0].open).toBe(true);
    expect(pinned[0].querySelector("summary").textContent).toBe("Plan · 1 of 3 done");
    const steps = [...pinned[0].querySelectorAll("li")];
    expect(steps.map(li => li.dataset.status)).toEqual(["completed", "in_progress", "pending"]);
    expect(steps[1].getAttribute("aria-label")).toBe("In progress: Fit the model");
    // The steps are the model's words: data, never translated.
    expect(pinned[0].querySelector(".agent-plan-list").hasAttribute("data-i18n-skip")).toBe(true);
    expect(preview.querySelectorAll(".agent-vm:not(.agent-vm-fold)")).toHaveLength(2);
    // A rejected update never replaces the plan in view.
    plan(3, ["completed", "completed", "completed"], { status: "failed" });
    activity.render(host, { running: true, status: "running", events });
    expect(preview.querySelector(".agent-plan summary").textContent).toBe("Plan · 1 of 3 done");
    // The timeline keeps the plan once, folded, where it was first made, with
    // its latest state (UX audit A5); a failed update keeps its own line.
    const saved = host.querySelectorAll(".agent-activity-content .agent-plan");
    expect(saved).toHaveLength(2);
    expect([...saved].map(node => node.open)).toEqual([false, false]);
    expect(host.querySelector(".agent-activity-content").firstElementChild).toBe(saved[0]);
    expect(saved[0].querySelector("summary").textContent).toBe("Plan · 1 of 3 done");
    expect(saved[1].querySelector("summary").textContent).toBe("Plan not updated");
  });

  // vm_start_process & co. (2026-10-26): a dev server or a long test run.
  it("shows a background process with its command, then by its id", () => {
    const { host, activity } = setup();
    const events = [];
    activity.receive(events, { version: 1, kind: "tool", id: "b:1/tool", name: "vm_start_process", status: "succeeded",
      command: "npm run dev", output: "Listening on :3000\n", process: "abcd1234", process_status: "running" });
    activity.receive(events, { version: 1, kind: "tool", id: "b:2/tool", name: "vm_stop_process", status: "succeeded",
      process: "abcd1234", exit_code: 143 });
    activity.renderTurn(host, { status: "completed", agent_activity: events, assistant_response: "Done." });
    const [started, stopped] = host.querySelectorAll(".agent-activity-content .agent-vm");
    expect(started.querySelector(".agent-vm-verb").textContent).toBe("Started in the background");
    expect(started.querySelector(".agent-vm-target").textContent).toBe("npm run dev");
    expect(started.querySelector(".agent-vm-meta").textContent).toBe("Running in the background");
    expect(started.classList.contains("has-output")).toBe(true);
    expect(stopped.querySelector(".agent-vm-verb").textContent).toBe("Stopped process");
    expect(stopped.querySelector(".agent-vm-target").textContent).toBe("abcd1234");
    expect(stopped.querySelector(".agent-vm-meta").textContent).toBe("Exit 143");
  });

  // A message the user sent into the running response (2026-10-26).
  it("shows the user's message in their own words, live and in the timeline", () => {
    const { host, activity } = setup();
    const events = [];
    activity.receive(events, vm({ id: "c:1/tool", status: "succeeded", command: "make", exit_code: 0 }));
    activity.receive(events, { version: 1, kind: "progress", id: "completion:1/note-n1", text: "Done", from_user: true });
    activity.receive(events, vm({ id: "c:2/tool", status: "running", command: "make test" }));
    activity.render(host, { running: true, status: "running", events });
    const live = host.querySelector(".agent-progress .agent-user-note");
    expect(live.querySelector(".agent-user-note-who").textContent).toBe("You");
    // The words stay the user's: never translated, even when they match a label.
    const words = live.querySelector(".agent-user-note-text");
    expect(words.textContent).toBe("Done");
    expect(words.hasAttribute("data-i18n-skip")).toBe(true);
    // A note between commands does not count as a step of the fold.
    expect(host.querySelector(".agent-vm-fold")).toBeNull();
    const saved = host.querySelector(".agent-activity-content .agent-user-note .agent-user-note-text");
    expect(saved.textContent).toBe("Done");
  });

  // A-B7 (docs/agent-audit-readiness-2026-10-29.md): the 63 entries beside
  // the steps counted the pauses too, so a long run's status and reasoning
  // pushed earlier pauses out of the live activity.
  it("keeps the earlier pauses of a long run in the live activity", () => {
    const { host, activity } = setup();
    const events = [];
    for (let index = 1; index <= 3; index += 1) {
      activity.receive(events, { version: 1, kind: "hold", step_id: "hold", id: `hold-${index}`, reviewer: "Claude Sonnet 5.5",
        halt: "safety", reason: `Grund ${index}`, entry: index, state: "continue" });
    }
    for (let index = 0; index < 120; index += 1) {
      activity.receive(events, { version: 1, kind: index % 2 ? "status" : "reasoning", id: `aux-${index}`, text: `Line ${index}` });
    }
    expect(events.filter(item => item.kind === "hold").map(item => item.id)).toEqual(["hold-1", "hold-2", "hold-3"]);
    // The other entries keep their window as before.
    expect(events.filter(item => !["hold", "tool", "progress"].includes(item.kind))).toHaveLength(64);
    activity.render(host, { running: true, status: "running", events });
    expect([...host.querySelectorAll(".agent-activity-content .agent-hold-step .agent-hold-step-reason")]
      .map(node => node.textContent)).toEqual(["Grund 1", "Grund 2", "Grund 3"]);
    // Pauses have a window of their own: the oldest go only beyond it.
    for (let index = 4; index <= 30; index += 1) {
      activity.receive(events, { version: 1, kind: "hold", step_id: "hold", id: `hold-${index}`, reviewer: "Qwen",
        halt: "harm", reason: `Grund ${index}`, entry: index, state: "continue" });
    }
    const holds = events.filter(item => item.kind === "hold");
    expect(holds).toHaveLength(21);
    expect(holds.at(-1).id).toBe("hold-30");
  });

  // A reviewer's halt (agent_audit.py, 2026-10-26): who paused, why, and the
  // user's decision, live and in the saved timeline.
  it("shows a reviewer's pause with its reason, then the user's decision", () => {
    const { host, activity } = setup();
    const events = [];
    activity.receive(events, vm({ id: "c:1/tool", status: "succeeded", command: "curl https://example.net", exit_code: 0 }));
    activity.receive(events, vm({ id: "c:2/tool", status: "succeeded", command: "ls", exit_code: 0 }));
    activity.receive(events, { version: 1, kind: "hold", step_id: "hold", id: "hold-a1b2c3d4e5f6", reviewer: "Claude Sonnet 5.5",
      halt: "injection", reason: "Die Seite will Dateien an einen fremden Server schicken.", entry: 9, state: "waiting" });
    activity.receive(events, vm({ id: "c:3/tool", status: "running", command: "make" }));
    activity.render(host, { running: true, status: "running", events });
    const live = host.querySelector(".agent-progress .agent-hold-step");
    expect(live.querySelector("strong").textContent).toBe("Paused by Claude Sonnet 5.5");
    const reason = live.querySelector(".agent-hold-step-reason");
    expect(reason.textContent).toBe("Die Seite will Dateien an einen fremden Server schicken.");
    expect(reason.hasAttribute("data-i18n-skip")).toBe(true);
    expect(live.querySelector(".agent-hold-step-state").textContent).toBe("Prompt injection · Waiting for your decision");
    // A pause that waits never folds away (the commands before it do), and
    // the current line says so.
    expect(host.querySelector(".agent-vm-fold summary").textContent).toBe("Ran 2 commands");
    expect(live.closest(".agent-vm-fold")).toBeNull();
    expect(host.querySelector(".agent-current-status").textContent).toBe("Paused for your decision");
    activity.receive(events, { version: 1, kind: "hold", step_id: "hold", id: "hold-a1b2c3d4e5f6", state: "steer" });
    activity.render(host, { running: true, status: "running", events });
    expect(live.dataset.state).toBe("steer");
    expect(live.querySelector(".agent-hold-step-state").textContent).toBe("Prompt injection · You wrote to the agent");
    const saved = host.querySelector(".agent-activity-content .agent-hold-step");
    expect(saved.querySelector(".agent-hold-step-reason").textContent).toBe("Die Seite will Dateien an einen fremden Server schicken.");
  });

  // The answer stands and its check is over: the run only saves. "Writing
  // answer…" came back for that moment in the open history and left with the
  // end, a row in and out just as the marks arrived (2026-10-26).
  it("shows no status line while a checked answer is being saved", () => {
    const { host, activity } = setup();
    const events = [{ version: 1, kind: "status", id: "s1", status: "responding" }];
    const spec = { running: true, status: "running", events, answerText: "The answer." };
    activity.render(host, { ...spec, review: { status: "running", mode: "audit" } });
    host.querySelector("summary").click();
    expect(host.querySelector(".agent-activity-current")).not.toBeNull();
    activity.render(host, { ...spec, review: { status: "succeeded", mode: "audit" } });
    expect(host.querySelector(".agent-activity-current")).toBeNull();
    expect(host.querySelector(".agent-current-status")).toBeNull();
    // A reconnect still says so.
    activity.render(host, { ...spec, review: { status: "succeeded", mode: "audit" }, reconnecting: true });
    expect(host.querySelector(".agent-activity-current").textContent).toBe("Reconnecting…");
  });

  it("offers the admin to restore the VM to before a finished message", () => {
    const { host, activity } = setup();
    const turn = { status: "completed", agent_activity: [], assistant_response: "Done.",
      agent_vm: { commands: 2, seconds: 3, checkpoint: "v2" } };
    let restored = 0;
    activity.renderTurn(host, turn, { vmRestore: () => { restored += 1; } });
    const button = host.querySelector(".agent-vm-restore");
    expect(button.hidden).toBe(false);
    // Audit with its VM is Pro and admins (style.css .audit-only).
    expect(button.classList.contains("audit-only")).toBe(true);
    expect(button.textContent).toBe("Restore the VM to before this message");
    button.click();
    expect(restored).toBe(1);
    // No action without a checkpoint or a handler.
    activity.renderTurn(host, { ...turn, agent_vm: { commands: 0 } }, { vmRestore: () => {} });
    expect(button.hidden).toBe(true);
    activity.renderTurn(host, turn);
    expect(button.hidden).toBe(true);
  });

  it("adds the VM's run time to the admin's usage line", () => {
    const { host, activity } = setup();
    activity.renderTurn(host, { status: "completed", agent_activity: [], assistant_response: "Done.",
      agent_usage: { input_tokens: 1000, output_tokens: 200 }, agent_vm: { commands: 3, seconds: 75.4, checkpoint: "v2" } });
    expect(host.querySelector(".agent-usage").textContent).toBe("1,200 tokens · VM 1m 15s");
  });
});

describe("a step in the workspace's browser", () => {
  // Since 2026-10-27 the browser tool (agent_browser.py) with typed actions,
  // no longer a browser command in the shell.
  const step = fields => vm({ name: "browser", ...fields });
  it("shows the action and what it was on, and offers to watch it live", () => {
    const { app, host, activity } = setup();
    const opened = [];
    app.window.App.workspaceView = { open: () => opened.push(true) };
    app.document.body.classList.add("viewer-has-workspace");
    const events = [];
    activity.receive(events, step({ status: "running", action: "open", url: "https://github.com" }));
    activity.receive(events, vm({ id: "completion:1:call_2/tool", status: "succeeded", command: "pip install x",
      exit_code: 0, output: "ok\n" }));
    activity.render(host, { running: true, status: "running", events });
    const [browserStep, otherStep] = host.querySelectorAll(".agent-activity-content .agent-vm");
    expect(browserStep.querySelector(".agent-vm-verb").textContent).toBe("Opening");
    // A page by its name in the text's type, its address on hover (UX audit A9).
    expect(browserStep.querySelector(".agent-vm-target").textContent).toBe("github.com");
    expect(browserStep.querySelector(".agent-vm-target").title).toBe("https://github.com");
    expect(browserStep.dataset.target).toBe("text");
    const watch = browserStep.querySelector(".agent-vm-watch");
    expect(watch.hidden).toBe(false);
    expect(watch.textContent).toBe("Watch live");
    expect(otherStep.querySelector(".agent-vm-watch").hidden).toBe(true);
    // Opens the view without folding the step open or shut.
    const wasOpen = browserStep.open;
    watch.click();
    expect(opened).toEqual([true]);
    expect(browserStep.open).toBe(wasOpen);
    // A step that only reads, with the page as its output; a click by its ref.
    activity.receive(events, step({ id: "completion:1:call_3/tool", status: "succeeded", action: "read",
      title: "Example", page: 'Page: "Example"\n[e1] link "More"' }));
    activity.receive(events, step({ id: "completion:1:call_4/tool", status: "succeeded", action: "click", ref: "e1" }));
    activity.render(host, { running: true, status: "running", events });
    const [, , read, click] = host.querySelectorAll(".agent-activity-content .agent-vm");
    expect(read.querySelector(".agent-vm-verb").textContent).toBe("Read the page");
    expect(read.querySelector(".agent-vm-target").textContent).toBe("Example");
    expect(read.querySelector(".agent-vm-output").textContent).toContain("[e1] link");
    expect(read.querySelector(".agent-vm-watch").hidden).toBe(false);
    expect(click.querySelector(".agent-vm-verb").textContent).toBe("Clicked");
    expect(click.querySelector(".agent-vm-target").textContent).toBe("e1");
    // A search on the page by what it looked for, its places as the output.
    activity.receive(events, step({ id: "completion:1:call_6/tool", status: "succeeded", action: "find",
      query: "price", title: "Shop", page: 'Page: "Shop"\n1 match for "price":\n[e4] "Sort by price"' }));
    activity.render(host, { running: true, status: "running", events });
    const find = host.querySelectorAll(".agent-activity-content .agent-vm")[4];
    expect(find.querySelector(".agent-vm-verb").textContent).toBe("Searched the page for");
    // A search term is a quote in the text's type (agent-chat.css adds the marks, A8).
    expect(find.querySelector(".agent-vm-target").textContent).toBe("price");
    expect(find.dataset.target).toBe("quote");
    // Opened, the page says its title, its host after it at the edge.
    activity.receive(events, step({ id: "completion:1:call_7/tool", status: "succeeded", action: "open",
      url: "https://www.kfw.de/inlandsfoerderung/", title: "Heizungsförderung für Privatpersonen | KfW" }));
    activity.render(host, { running: true, status: "running", events });
    const page = host.querySelectorAll(".agent-activity-content .agent-vm")[5];
    expect(page.querySelector(".agent-vm-verb").textContent).toBe("Opened");
    expect(page.querySelector(".agent-vm-target").textContent).toBe("Heizungsförderung für Privatpersonen | KfW");
    expect(page.querySelector(".agent-vm-meta").textContent).toBe("kfw.de");
    expect(find.querySelector(".agent-vm-output").textContent).toContain('[e4] "Sort by price"');
  });

  it("offers nothing without a workspace on the account, and never for a shell command", () => {
    const { app, host, activity } = setup();
    const events = [];
    activity.receive(events, step({ status: "running", action: "open", url: "https://github.com" }));
    activity.render(host, { running: true, status: "running", events });
    expect(host.querySelector(".agent-vm .agent-vm-watch").hidden).toBe(true);
    app.window.App.workspaceView = { open() {} };
    app.document.body.classList.add("viewer-has-workspace");
    activity.receive(events, vm({ id: "completion:1:call_5/tool", status: "running", command: "browser open x" }));
    activity.render(host, { running: true, status: "running", events });
    expect(host.querySelectorAll(".agent-activity-content .agent-vm")[1].querySelector(".agent-vm-watch").hidden)
      .toBe(true);
  });
});

describe("installing and asking for a domain", () => {
  it("shows the packages and the domain like a command", () => {
    const { host, activity } = setup();
    const events = [];
    activity.receive(events, vm({ name: "vm_install_packages", status: "succeeded", packages: ["ffmpeg", "jq"],
      exit_code: 0, duration_ms: 4200, output: "Setting up jq\n" }));
    activity.receive(events, vm({ id: "completion:1:call_2/tool", name: "request_domain", status: "succeeded",
      domain: "api.example.com", domain_status: "allowed" }));
    activity.render(host, { running: false, status: "completed", events });
    const [install, domain] = host.querySelectorAll(".agent-activity-content .agent-vm");
    expect(install.querySelector(".agent-vm-verb").textContent).toBe("Installed");
    expect(install.querySelector(".agent-vm-target").textContent).toBe("ffmpeg jq");
    expect(install.querySelector(".agent-vm-output").textContent).toBe("Setting up jq\n");
    expect(domain.querySelector(".agent-vm-verb").textContent).toBe("Access to");
    expect(domain.querySelector(".agent-vm-target").textContent).toBe("api.example.com");
  });

  it("keeps the user's decision on a domain in the history", () => {
    const { host, activity } = setup();
    const events = [];
    activity.receive(events, { version: 1, kind: "hold", id: "hold-abc", step_id: "hold", halt: "domain",
      domain: "api.example.com", reviewer: "", reason: "", entry: 4, gate: true, state: "waiting" });
    activity.receive(events, { version: 1, kind: "hold", id: "hold-abc", step_id: "hold", state: "deny" });
    activity.render(host, { running: false, status: "completed", events });
    const step = host.querySelector(".agent-activity-content .agent-hold-step");
    expect(step.querySelector("strong").textContent).toBe("The agent asked to reach api.example.com");
    expect(step.querySelector(".agent-hold-step-state").textContent).toBe("Network access · You did not allow it");
    // Undecided, it stays closed and the work goes on: never "Stopped" (UX audit 2026-10-29 C8).
    activity.receive(events, { version: 1, kind: "hold", id: "hold-def", step_id: "hold", halt: "domain",
      domain: "api.example.org", reviewer: "", reason: "", entry: 6, gate: true, state: "timeout" });
    activity.render(host, { running: false, status: "completed", events });
    expect(host.querySelectorAll(".agent-activity-content .agent-hold-step")[1].querySelector(".agent-hold-step-state").textContent)
      .toBe("Network access · Not allowed after 30 minutes without a decision");
  });

  // A step that acts outside the workspace that not every reviewer could
  // check (agent_audit.gate_hold, GATE_UNCHECKED): no reviewer, no reason,
  // yet the run waits for the user like on any pause (2026-10-28: it was
  // filtered out, the heading said "Thinking…" and the history lost it).
  it("shows a pause before an unchecked step and keeps the decision", () => {
    const { host, activity } = setup();
    const events = [];
    activity.receive(events, { version: 1, kind: "hold", id: "hold-0123456789ab", step_id: "hold", halt: "unchecked",
      reviewer: "", provider: "", reason: "", entry: 7, gate: true, state: "waiting" });
    activity.render(host, { running: true, status: "running", events });
    const live = host.querySelector(".agent-progress .agent-hold-step");
    expect(live.querySelector("strong").textContent).toBe("Paused before a step ran");
    expect(live.querySelector(".agent-hold-step-state").textContent).toBe("Not checked · Waiting for your decision");
    expect(host.querySelector(".agent-current-status").textContent).toBe("Paused for your decision");
    activity.receive(events, { version: 1, kind: "hold", id: "hold-0123456789ab", step_id: "hold", state: "continue" });
    activity.render(host, { running: false, status: "completed", events });
    const saved = host.querySelector(".agent-activity-content .agent-hold-step");
    expect(saved.querySelector(".agent-hold-step-state").textContent).toBe("Not checked · You let the work go on");
  });

  // The agent's own question (ask_user, 2026-10-29): it waits for the user,
  // not for a decision on a pause, and the history keeps what it asked.
  it("waits for the user on the agent's question and keeps how it ended", () => {
    const { host, activity } = setup();
    const events = [];
    activity.receive(events, { version: 1, kind: "hold", id: "hold-a1b2c3d4e5f6", step_id: "hold", halt: "ask",
      ask: "browser", request: "Bitte melde dich bei der Post an.", reviewer: "", provider: "", reason: "",
      entry: null, state: "waiting" });
    activity.render(host, { running: true, status: "running", events });
    const live = host.querySelector(".agent-progress .agent-hold-step");
    // In the present while it waits (UX audit 2026-10-29 C14), in the past once over.
    expect(live.querySelector("strong").textContent).toBe("The agent asks you to take over the browser");
    expect(live.querySelector(".agent-hold-step-state").textContent).toBe("Waiting for you");
    expect(host.querySelector(".agent-current-status").textContent).toBe("Waiting for you");
    activity.receive(events, { version: 1, kind: "hold", id: "hold-a1b2c3d4e5f6", step_id: "hold", state: "handed_back" });
    activity.render(host, { running: false, status: "completed", events });
    const saved = host.querySelector(".agent-activity-content .agent-hold-step");
    expect(saved.querySelector("strong").textContent).toBe("The agent asked you to take over the browser");
    expect(saved.querySelector(".agent-hold-step-reason").textContent).toBe("Bitte melde dich bei der Post an.");
    expect(saved.querySelector(".agent-hold-step-state").textContent).toBe("You handed the browser back");
  });
});

// Since 2026-10-28 the agent's text beside a tool call stands whole in the
// timeline (agent_answer_mode.NOTE_CHARS), its lines kept.
describe("The agent's note beside a tool call", () => {
  it("keeps the whole text and its lines in the live progress", () => {
    const { host, activity } = setup();
    const events = [];
    const text = "I'll first look at the folder. ".repeat(20) + "\n- Then the notes.";
    activity.receive(events, { version: 1, kind: "progress", id: "completion:0/note", text });
    activity.render(host, { running: true, status: "running", events, elapsedMs: 3000 });
    const note = [...host.querySelectorAll(".agent-progress p")].find(p => p.textContent.startsWith("I'll first"));
    expect(note.textContent).toBe(text);
    expect(note.textContent.length).toBeGreaterThan(400);
  });
});

// 2026-10-28 (Max): a long run without a VM step grew its live lines down
// the screen. Every run folds its earlier steps; the step at work and the
// note leading into it stay, a long note three lines tall.
describe("Live lines of a long run", () => {
  it("fold every earlier step, not only commands", () => {
    const { host, activity } = setup();
    const events = [];
    const search = (n, status = "succeeded") => activity.receive(events, { version: 1, kind: "tool",
      id: `s${n}/tool`, name: "web_search", status, count: 1 });
    search(1); search(2);
    activity.receive(events, { version: 1, kind: "progress", id: "completion:3/note", text: "Checking the docs. ".repeat(40) });
    search(3, "running");
    activity.render(host, { running: true, status: "running", events });
    const preview = host.querySelector(".agent-progress");
    const fold = preview.querySelector(".agent-vm-fold");
    expect(fold.querySelector("summary").textContent).toBe("2 earlier steps");
    const note = preview.querySelector(".agent-progress-note");
    expect(note.closest(".agent-vm-fold")).toBeNull();
    expect(note.textContent.length).toBeGreaterThan(400);
  });
});

// The thinking stays visible (UX audit 2026-10-29, package A).
describe("the agent's thinking in the activity", () => {
  it("keeps the reasoning beside a note, live and in the history (A1)", () => {
    const { host, activity } = setup();
    const events = [];
    const thought = (step, text) => activity.receive(events, { version: 1, kind: "reasoning", step_id: step,
      id: `${step}/reasoning-summary`, format: "summary", summary_source: "provider_summary", text });
    thought("completion:0", "Clarifying the question");
    thought("completion:1", "Checking the numbers");
    activity.receive(events, { version: 1, kind: "progress", step_id: "completion:1", id: "completion:1/note",
      text: "The calculation is done: gas costs more than the heat pump." });
    activity.render(host, { running: false, status: "completed", events });
    // Before, one note hid every thought of the run.
    expect([...host.querySelectorAll(".agent-activity-reasoning")].map(node => node.textContent))
      .toEqual(["Clarifying the question", "Checking the numbers"]);
    // A step's thought its own note repeats word for word stands back.
    thought("completion:2", "The calculation is done: gas costs more than the heat pump.");
    activity.receive(events, { version: 1, kind: "progress", step_id: "completion:2", id: "completion:2/note",
      text: "The calculation is done: gas costs more than the heat pump.\nNext the subsidy." });
    activity.render(host, { running: false, status: "completed", events });
    expect(host.querySelectorAll(".agent-activity-reasoning")).toHaveLength(2);
  });

  it("opens a step's thinking as its headings over their paragraphs, never translated (A2)", () => {
    const { host, activity } = setup();
    const events = [];
    activity.receive(events, { version: 1, kind: "progress", step_id: "completion:1", id: "completion:1/thinking",
      text: "Checking the numbers – The search found 11.8 ct/kWh.", summary_source: "provider_summary" });
    activity.render(host, { running: true, status: "running", events });
    // Still thinking: its line, live and in the history.
    expect(host.querySelector(".agent-progress p").textContent).toBe("Checking the numbers – The search found 11.8 ct/kWh.");
    const entry = host.querySelector(".agent-activity-content .agent-activity-thought");
    expect(entry.textContent).toBe("Checking the numbers – The search found 11.8 ct/kWh.");
    // Its step is over: the sections arrive with the last line.
    activity.receive(events, { version: 1, kind: "progress", step_id: "completion:1", id: "completion:1/thinking",
      text: "Choosing the efficiency – A SCOP of 3.4 is cautious.", summary_source: "provider_summary",
      sections: [{ title: "Checking the numbers", text: "The search found 11.8 ct/kWh. I will compute the costs." },
                 { title: "Choosing the efficiency", text: "A SCOP of 3.4 is cautious.\n\nI will also run 3.0 and 3.8." }] });
    activity.render(host, { running: false, status: "completed", events });
    const saved = host.querySelector(".agent-activity-content .agent-activity-thought");
    expect(saved).toBe(entry);
    expect([...saved.children].map(p => [p.className, p.textContent])).toEqual([
      ["agent-thought-title", "Checking the numbers"], ["", "The search found 11.8 ct/kWh. I will compute the costs."],
      ["agent-thought-title", "Choosing the efficiency"], ["", "A SCOP of 3.4 is cautious."], ["", "I will also run 3.0 and 3.8."]]);
    expect([...saved.children].every(p => p.hasAttribute("data-i18n-skip"))).toBe(true);
    expect(saved.getAttribute("aria-label")).toBe("Reasoning summary");
  });
});
