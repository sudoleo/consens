import { afterEach, describe, expect, it, vi } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const contexts = [];
const FILE = { name: "Research notes.txt", mime: "text/plain", size: 42, data: "bm90ZXM=" };
const BODY = `<div class="input-section">
  <div class="chat-input-container"><div id="attachmentBar" hidden></div>
    <textarea id="questionInput"></textarea><button id="attachTrigger"></button>
    <div id="attachMenu" hidden><button id="attachUploadOption"></button></div>
    <input id="attachFileInput" type="file">
  </div>
  <div id="composerModeBar" hidden><p id="composerModeDescription"></p>
    <span id="composerModelIcons"></span><p id="composerComparisonStatus"></p>
    <button id="composerAttachButton"></button></div>
  </div>
  <input id="deepSearchToggle" type="checkbox">
  <div id="threadAskAttachments"></div>
  <div id="attachmentViewerModal" hidden><span id="attachmentViewerTitle"></span>
    <div id="attachmentViewerBody"></div><button id="attachmentViewerClose"></button></div>`;

function boot() {
  const ctx = loadScripts(["static/js/run-mode.js", "static/js/attachments.js", "static/js/agent-mode.js"], {
    body: BODY,
    before(window) {
      window.document.body.classList.add("is-hero");
      window.localStorage.setItem("runMode", "consensus");
      window.App = { modelPrefs: [], deepThinkModelLabels: {},
        getModelOptionLabel: () => "", getSelectedModelCount: () => 0,
        initCustomModelPicker: vi.fn(), trackAppEvent: vi.fn(), composer: {expand: vi.fn()} };
      window.URL.createObjectURL = () => "blob:preview";
      window.URL.revokeObjectURL = vi.fn();
    }
  });
  contexts.push(ctx);
  ctx.window.App.renderComposerMode();
  ctx.window.pendingAttachments = [{ ...FILE }];
  ctx.window.renderAttachmentChips();
  return ctx;
}
afterEach(() => contexts.splice(0).forEach(ctx => ctx.window.close()));

describe("composer attachment tray", () => {
  it("moves the same tray and focused control between the start toolbar, a chat in any mode and a new comparison", async () => {
    const { window, document } = boot();
    const tray = document.getElementById("attachmentBar");
    const toolbar = document.getElementById("composerModeBar");
    const preview = tray.querySelector(".attachment-chip-preview");
    expect(tray.parentNode).toBe(toolbar);
    preview.focus();
    document.body.classList.remove("is-hero");
    await Promise.resolve();
    expect(toolbar.hidden).toBe(true);
    expect(tray.parentNode).toBe(document.querySelector(".chat-input-container"));
    expect(tray.hidden).toBe(false);
    expect(document.activeElement).toBe(preview);
    // In a chat the tray stays above the question in every mode.
    window.App.runMode.set('compare');
    expect(tray.parentNode).toBe(document.querySelector(".chat-input-container"));
    window.App.runMode.set('consensus');
    document.body.classList.add("is-hero");
    await Promise.resolve();
    expect(tray.parentNode).toBe(toolbar);
    expect(tray.querySelector(".attachment-chip-preview")).toBe(preview);
    expect(document.querySelectorAll("#attachmentBar")).toHaveLength(1);
    expect(window.getAttachmentsPayload()[0].data).toBe(FILE.data);
  });

  it("hands sent files to the message, clears the draft and restores failed drafts in the visible composer", async () => {
    const { window, document } = boot();
    const sent = window.App.attachments.detachForMessage();
    expect(sent).toEqual([{ name: FILE.name, mime: FILE.mime, size: FILE.size }]);
    window.App.attachments.renderMessageAttachments(document.getElementById("threadAskAttachments"), sent);
    document.body.classList.remove("is-hero");
    await Promise.resolve();
    expect(document.getElementById("composerModeBar").hidden).toBe(true);
    expect(document.getElementById("attachmentBar").hidden).toBe(true);
    expect(document.querySelector("#threadAskAttachments .attachment-chip-name").textContent).toBe(FILE.name);
    expect(document.querySelector("#threadAskAttachments button")).toBeNull();
    expect(window.getAttachmentsPayload()).toEqual([]);
    window.pendingAttachments = [{ ...FILE }];
    window.renderAttachmentChips();
    expect(document.querySelector(".chat-input-container #attachmentBar").hidden).toBe(false);
    expect(window.App.composer.expand).toHaveBeenCalled();
  });

  it("separates preview from removal and returns focus to the next available action", () => {
    const { window, document } = boot();
    window.pendingAttachments.push({ ...FILE, name: "Second.txt" });
    window.renderAttachmentChips();
    document.querySelector(".attachment-chip-preview").click();
    expect(document.getElementById("attachmentViewerModal").hidden).toBe(false);
    document.getElementById("attachmentViewerClose").click();
    const remove = document.querySelector(".attachment-chip-remove");
    expect(remove.closest(".attachment-chip-preview")).toBeNull();
    remove.dispatchEvent(new window.KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
    expect(document.getElementById("attachmentViewerModal").hidden).toBe(true);
    remove.click();
    expect(window.pendingAttachments.map(file => file.name)).toEqual(["Second.txt"]);
    expect(document.activeElement).toBe(document.querySelector(".attachment-chip-remove"));
    document.activeElement.click();
    expect(document.getElementById("attachmentBar").hidden).toBe(true);
    expect(document.activeElement).toBe(document.getElementById("composerAttachButton"));
  });

  it("shows an Agent upload failure on the pending chip and clears it again", () => {
    const { window, document } = boot();
    expect(window.App.attachments.markError({ ...FILE }, "Page limit: 80 pages.")).toBe(true);
    const chip = document.querySelector("#attachmentBar .attachment-chip");
    expect(chip.classList.contains("has-error")).toBe(true);
    expect(chip.querySelector(".attachment-chip-size").textContent).toBe("Couldn't upload · Page limit: 80 pages.");
    expect(window.getAttachmentsPayload()[0].data).toBe(FILE.data);
    window.App.attachments.markError({ ...FILE }, "");
    expect(document.querySelector("#attachmentBar .attachment-chip").classList.contains("has-error")).toBe(false);
  });

  it("marks sent Agent files that were only partly readable", () => {
    const { window, document } = boot();
    const row = document.getElementById("threadAskAttachments");
    window.App.attachments.renderMessageAttachments(row, [{ ...FILE, warnings: ["No extractable text on pages 4."] }, FILE]);
    const chips = row.querySelectorAll(".attachment-chip");
    expect(chips[0].querySelector(".attachment-chip-warning").textContent).toBe("Partly read");
    expect(chips[0].getAttribute("aria-label")).toContain("only partly readable: No extractable text on pages 4.");
    expect(chips[1].querySelector(".attachment-chip-warning")).toBeNull();
  });
});
