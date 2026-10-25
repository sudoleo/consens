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
    expect(live.querySelector(".agent-vm-meta").textContent).toBe("Exit 1 · 12s");
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
    activity.renderTurn(host, { status: "completed", agent_activity: events, assistant_response: "Done." });
    const [write, failed] = host.querySelectorAll(".agent-activity-content .agent-vm");
    expect(write.querySelector(".agent-vm-verb").textContent).toBe("Wrote the file");
    expect(write.querySelector(".agent-vm-target").textContent).toBe("/home/sprite/stats.py");
    // Nothing to open without output.
    expect(write.classList.contains("has-output")).toBe(false);
    expect(failed.querySelector(".agent-vm-meta").textContent).toBe("VM not available");
    expect(failed.textContent).not.toMatch(/error|exception|HTTP/i);
  });

  it("adds the VM's run time to the admin's usage line", () => {
    const { host, activity } = setup();
    activity.renderTurn(host, { status: "completed", agent_activity: [], assistant_response: "Done.",
      agent_usage: { input_tokens: 1000, output_tokens: 200 }, agent_vm: { commands: 3, seconds: 75.4, checkpoint: "v2" } });
    expect(host.querySelector(".agent-usage").textContent).toBe("1,200 tokens · VM 1m 15s");
  });
});
