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
  <div id="composerTools"><p id="composerModeDescription"></p></div>
  <span id="composerModelIcons"></span>
  <div id="composerModeBar" hidden><p id="composerComparisonStatus"></p></div>
  </div>
  <input id="reasoningToggle" type="checkbox">
  <div id="threadAskAttachments"></div>
  <dialog id="attachmentViewerModal" class="modal"><div class="modal-content"><span id="attachmentViewerTitle"></span>
    <span id="attachmentViewerCount" aria-live="polite" hidden></span>
    <div id="attachmentViewerBody"></div><button id="attachmentViewerClose"></button>
    <button id="attachmentViewerPrev" hidden></button><button id="attachmentViewerNext" hidden></button></div></dialog>`;

function boot() {
  const ctx = loadScripts(["static/js/motion.js", "static/js/modal-dialog.js", "static/js/user-settings.js", "static/js/run-mode.js", "static/js/image-zoom.js", "static/js/attachments.js", "static/js/agent-mode.js"], {
    body: BODY,
    before(window) {
      window.document.body.classList.add("is-hero");
      window.localStorage.setItem("runMode", "consensus");
      window.localStorage.setItem("consensio.settingsReset", "2026-10-12");
      window.App = { modelPrefs: [],
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
  it("keeps the same tray and focused control above the question on the start screen, in a chat and in any mode", async () => {
    const { window, document } = boot();
    const tray = document.getElementById("attachmentBar");
    const field = document.querySelector(".chat-input-container");
    const preview = tray.querySelector(".attachment-chip-preview");
    expect(tray.parentNode).toBe(field);
    preview.focus();
    document.body.classList.remove("is-hero");
    await Promise.resolve();
    expect(document.getElementById("composerModeBar").hidden).toBe(true);
    expect(tray.parentNode).toBe(field);
    expect(tray.hidden).toBe(false);
    expect(document.activeElement).toBe(preview);
    window.App.runMode.set('compare');
    expect(tray.parentNode).toBe(field);
    window.App.runMode.set('consensus');
    document.body.classList.add("is-hero");
    await Promise.resolve();
    expect(tray.parentNode).toBe(field);
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

  // An Agent message's files wait on the message itself until stored
  // (agent-workspace.js upload), a picture as its tile in the skeleton, per
  // run.
  it("holds a sent file's tile as uploading until its run says it is stored", () => {
    const { window, document } = boot();
    const PICTURE = { name: "image.png", mime: "image/png", size: 7, data: "iVBORw0K" };
    window.pendingAttachments = [{ ...FILE }, { ...PICTURE }];
    const files = window.getAttachmentsPayload();
    window.App.attachments.markUploading("run-1", files);
    const row = document.getElementById("threadAskAttachments");
    row.classList.add("message-attachments");
    window.App.attachments.renderMessageAttachments(row, window.App.attachments.detachForMessage());
    const [text, picture] = row.querySelectorAll(".attachment-chip");
    // Drawn as uploading from the first frame: no picture shown, then covered.
    expect(picture.classList.contains("is-image-tile")).toBe(true);
    expect([text, picture].map(chip => chip.classList.contains("is-uploading"))).toEqual([true, true]);
    expect(picture.getAttribute("aria-busy")).toBe("true");
    expect(text.querySelector(".attachment-chip-status").textContent).toBe("Uploading…");
    // Another run ending leaves them; theirs ends file by file.
    window.App.attachments.markUploading("run-2", []);
    expect(picture.classList.contains("is-uploading")).toBe(true);
    window.App.attachments.markUploading("run-1", [files[1]]);
    expect([text, picture].map(chip => chip.classList.contains("is-uploading"))).toEqual([false, true]);
    window.App.attachments.markUploading("run-1", []);
    expect(picture.classList.contains("is-uploading")).toBe(false);
    expect(picture.hasAttribute("aria-busy")).toBe(false);
    // A stored file (with its id) is never marked.
    window.App.attachments.markUploading("run-3", files);
    window.App.attachments.renderMessageAttachments(row, [{ ...FILE, id: "a".repeat(32) }]);
    expect(row.querySelector(".attachment-chip").classList.contains("is-uploading")).toBe(false);
  });

  // Excel, Word and LibreOffice put a picture of what was copied next to its
  // text; Chromium hands it over as image.png. Taking the picture dropped
  // the text.
  it("pastes cells from an office program as text, a screenshot as a picture", () => {
    const { window, document } = boot();
    const field = document.getElementById("questionInput");
    const picture = new window.File(["png"], "image.png", { type: "image/png" });
    const paste = data => {
      const event = new window.Event("paste", { bubbles: true, cancelable: true });
      event.clipboardData = { types: Object.keys(data).concat(["Files"]), files: [picture], items: [],
        getData: type => data[type] || "" };
      field.dispatchEvent(event);
      return event.defaultPrevented;
    };
    expect(paste({ "text/plain": "Gold\t2400\n", "text/html": '<html xmlns:o="urn:schemas-microsoft-com:office:office"><table></table></html>' })).toBe(false);
    expect(paste({ "text/plain": "A paragraph from Word", "text/rtf": "{\\rtf1 A paragraph}" })).toBe(false);
    expect(paste({ "text/plain": "Gold\t2400", "text/html": '<meta name="generator" content="LibreOffice"><table></table>' })).toBe(false);
    expect(window.pendingAttachments.map(file => file.name)).toEqual([FILE.name]);
    // A screenshot, or a picture copied in the browser, stays a picture.
    expect(paste({})).toBe(true);
    expect(paste({ "text/html": '<img src="https://example.com/a.png">' })).toBe(true);
  });

  it("ends the (+) menu above the bottom edge of a short phone, where it scrolls", () => {
    const { window, document } = boot();
    const menu = document.getElementById("attachMenu");
    const trigger = document.getElementById("attachTrigger");
    // 320x568: on the start screen the menu opens down from y=321, 341px tall
    // (8px under a composer that ends at 313). Its box on screen is still
    // mid-motion, 11px lower; the layout says where it comes to rest.
    let height = 568;
    Object.defineProperty(window, "visualViewport", { configurable: true, get: () => ({ offsetTop: 0, height }) });
    const composer = { getBoundingClientRect: () => ({ top: 174 }), clientTop: 1 };
    Object.defineProperty(menu, "offsetParent", { configurable: true, value: composer });
    Object.defineProperty(menu, "offsetTop", { configurable: true, value: 146 });
    Object.defineProperty(menu, "offsetHeight", { configurable: true, value: 341 });
    menu.getBoundingClientRect = () => ({ top: 332, bottom: 666, left: 27, right: 315, width: 282, height: 334 });
    trigger.click();
    expect(menu.hidden).toBe(false);
    expect(menu.style.maxHeight).toBe("235px");
    // With room below (390x844) the stylesheet's own limit is left alone.
    trigger.click();
    height = 844;
    trigger.click();
    expect(menu.hidden).toBe(false);
    expect(menu.style.maxHeight).toBe("");
  });

  it("separates preview from removal and returns focus to the next available action", () => {
    const { window, document } = boot();
    window.pendingAttachments.push({ ...FILE, name: "Second.txt" });
    window.renderAttachmentChips();
    document.querySelector(".attachment-chip-preview").click();
    expect(document.getElementById("attachmentViewerModal").open).toBe(true);
    document.getElementById("attachmentViewerClose").click();
    const remove = document.querySelector(".attachment-chip-remove");
    expect(remove.closest(".attachment-chip-preview")).toBeNull();
    remove.dispatchEvent(new window.KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
    expect(document.getElementById("attachmentViewerModal").open).toBe(false);
    remove.click();
    expect(window.pendingAttachments.map(file => file.name)).toEqual(["Second.txt"]);
    expect(document.activeElement).toBe(document.querySelector(".attachment-chip-remove"));
    document.activeElement.click();
    expect(document.getElementById("attachmentBar").hidden).toBe(true);
    expect(document.activeElement).toBe(document.getElementById("attachTrigger"));
  });

  it("shows an Agent upload failure on the pending chip and clears it again", () => {
    const { window, document } = boot();
    expect(window.App.attachments.markError({ ...FILE }, "Page limit: 80 pages.")).toBe(true);
    const chip = document.querySelector("#attachmentBar .attachment-chip");
    expect(chip.classList.contains("has-error")).toBe(true);
    expect(chip.querySelector(".attachment-chip-size").textContent).toBe("Couldn’t upload · Page limit: 80 pages.");
    expect(window.getAttachmentsPayload()[0].data).toBe(FILE.data);
    window.App.attachments.markError({ ...FILE }, "");
    expect(document.querySelector("#attachmentBar .attachment-chip").classList.contains("has-error")).toBe(false);
  });

  it("marks sent Agent files that were only partly readable", () => {
    const { window, document } = boot();
    const row = document.getElementById("threadAskAttachments");
    window.App.attachments.renderMessageAttachments(row, [{ ...FILE, warnings: ["Page 4 is a scanned image and was not read."] }, FILE]);
    const chips = row.querySelectorAll(".attachment-chip");
    expect(chips[0].querySelector(".attachment-chip-warning").textContent).toBe("Partly read");
    expect(chips[0].getAttribute("aria-label")).toContain("only partly readable: Page 4 is a scanned image and was not read.");
    expect(chips[1].querySelector(".attachment-chip-warning")).toBeNull();
  });

  it("opens a stored Agent file from its sent message with download and a confirmed removal", async () => {
    const { window, document } = boot();
    const id = "a".repeat(32);
    const blob = new window.Blob(["hello"], { type: "text/plain" });
    window.App.agentWorkspace = { openFile: vi.fn(async () => ({ blob, mime: "text/plain" })), removeFile: vi.fn(async () => {}) };
    const row = document.getElementById("threadAskAttachments");
    window.App.attachments.renderMessageAttachments(row, [
      { name: "notes.txt", mime: "text/plain", size: 5, id },
      { name: "old.txt", mime: "text/plain", size: 5 }
    ]);
    const chips = row.querySelectorAll(".attachment-chip");
    // Only the stored file can be opened again.
    expect(chips[1].querySelector(".attachment-chip-preview")).toBeNull();
    chips[0].querySelector(".attachment-chip-preview").click();
    expect(window.App.agentWorkspace.openFile).toHaveBeenCalledWith(id);
    const body = document.getElementById("attachmentViewerBody");
    expect(body.textContent).toContain("Loading preview");
    // A text file reads in the app's own colours, not in a frame whose white
    // page took the dark theme's light text.
    await vi.waitFor(() => expect(body.querySelector(".attachment-viewer-text")?.textContent).toBe("hello"));
    expect(body.querySelector("iframe")).toBeNull();
    const actions = body.querySelector(".attachment-viewer-actions");
    expect([...actions.querySelectorAll("button")].map(b => b.textContent)).toEqual(["Download", "Remove from chat"]);
    actions.querySelectorAll("button")[1].click();
    expect(window.App.agentWorkspace.removeFile).not.toHaveBeenCalled();
    expect(body.textContent).toContain("Remove notes.txt? The agent can no longer use it in this chat.");
    [...body.querySelectorAll(".attachment-viewer-actions button")].find(b => b.textContent === "Remove").click();
    await vi.waitFor(() => expect(document.getElementById("attachmentViewerModal").open).toBe(false));
    expect(window.App.agentWorkspace.removeFile).toHaveBeenCalledWith(id);
  });

  it("shows why a stored file could not be opened", async () => {
    const { window, document } = boot();
    window.App.agentWorkspace = { openFile: vi.fn(async () => { throw new Error("The file has expired or is no longer available."); }) };
    const row = document.getElementById("threadAskAttachments");
    window.App.attachments.renderMessageAttachments(row, [{ name: "scan.png", mime: "image/png", size: 5, id: "b".repeat(32) }]);
    row.querySelector(".attachment-chip-preview").click();
    const body = document.getElementById("attachmentViewerBody");
    await vi.waitFor(() => expect(body.textContent).toContain("The file has expired or is no longer available."));
    expect(body.querySelector(".attachment-viewer-actions")).toBeNull();
  });

  // The pictures of a collage page through like a gallery.
  it("pages through a gallery of pictures with the arrows and the keys", async () => {
    const { window, document } = boot();
    const picture = (id, host) => ({ fileId: id.repeat(32), name: `picture-${id}.webp`, mime: "image/webp", size: 9,
      title: `Picture ${id}`, page: `https://${host}/page`, host });
    const gallery = [picture("a", "rbb24.de"), picture("b", "fupa.net"), picture("c", "nextg.tv")];
    const seen = [];
    window.trackUmamiEvent = name => seen.push(name);
    const views = () => seen.filter(name => name === "app_attachment_viewed").length;
    window.App.agentWorkspace = { openFile: vi.fn(async () => ({ blob: new window.Blob(["RIFF"], { type: "image/webp" }), mime: "image/webp" })) };
    const title = document.getElementById("attachmentViewerTitle");
    const count = document.getElementById("attachmentViewerCount");
    const [prev, next] = ["attachmentViewerPrev", "attachmentViewerNext"].map(id => document.getElementById(id));
    const body = document.getElementById("attachmentViewerBody");
    window.App.attachments.openStored({ ...gallery[0], gallery, index: 0 });
    expect([title.textContent, count.textContent, count.hidden, prev.hidden, next.hidden]).toEqual(["Picture a", "1 / 3", false, false, false]);
    await vi.waitFor(() => expect(body.querySelector(".attachment-viewer-image")).not.toBeNull());
    const source = body.querySelector("a.attachment-viewer-source");
    expect([source.textContent, source.href, source.rel]).toEqual(["rbb24.de", "https://rbb24.de/page", "noopener noreferrer nofollow"]);
    next.click();
    expect([title.textContent, count.textContent]).toEqual(["Picture b", "2 / 3"]);
    expect(window.App.agentWorkspace.openFile).toHaveBeenCalledWith(gallery[1].fileId);
    const modal = document.getElementById("attachmentViewerModal");
    modal.dispatchEvent(new window.KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }));
    expect(count.textContent).toBe("1 / 3");
    // From the first back to the last.
    modal.dispatchEvent(new window.KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }));
    expect([title.textContent, count.textContent]).toEqual(["Picture c", "3 / 3"]);
    // Each picture loads once, its neighbours before they are asked for;
    // paging is one view, not a view per picture.
    await vi.waitFor(() => expect(window.App.agentWorkspace.openFile).toHaveBeenCalledTimes(3));
    expect(views()).toBe(1);
    // With the focus on Download, emptied by the step, the keys still page.
    await vi.waitFor(() => expect(body.querySelector(".attachment-viewer-action")).not.toBeNull());
    body.querySelector(".attachment-viewer-action").focus();
    document.body.dispatchEvent(new window.KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    expect(count.textContent).toBe("1 / 3");
    expect(body.textContent).not.toContain("Loading preview");
    expect(count.getAttribute("aria-live")).toBe("polite");
    // A file of its own has no arrows.
    window.App.attachments.openStored({ ...gallery[0], gallery: [gallery[0]], index: 0 });
    expect([count.hidden, prev.hidden, next.hidden, title.textContent]).toEqual([true, true, true, "Picture a"]);
    await vi.waitFor(() => expect(body.querySelector(".attachment-viewer-image")).not.toBeNull());
  });

  // A picture in the viewer zooms (image-zoom.js).
  it("zooms into a picture, starts each picture fitted and pages by swipe only when it is fitted", async () => {
    const { window, document } = boot();
    const picture = id => ({ fileId: id.repeat(32), name: `picture-${id}.webp`, mime: "image/webp", size: 9, title: `Picture ${id}` });
    const gallery = [picture("a"), picture("b")];
    window.App.agentWorkspace = { openFile: vi.fn(async () => ({ blob: new window.Blob(["RIFF"], { type: "image/webp" }), mime: "image/webp" })) };
    const body = document.getElementById("attachmentViewerBody");
    const count = document.getElementById("attachmentViewerCount");
    const image = () => body.querySelector(".attachment-viewer-image");
    const swipe = (fromX, toX, second) => {
      const touch = (type, x, id = 1, primary = true) => {
        const event = new window.MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: 100 });
        Object.defineProperties(event, { pointerId: { value: id }, pointerType: { value: "touch" }, isPrimary: { value: primary } });
        return event;
      };
      body.dispatchEvent(touch("pointerdown", fromX));
      if (second) body.dispatchEvent(touch("pointerdown", fromX + 40, 2, false));
      body.dispatchEvent(touch("pointerup", toX));
    };
    window.App.attachments.openStored({ ...gallery[0], gallery, index: 0 });
    await vi.waitFor(() => expect(image()).not.toBeNull());
    expect(image().style.touchAction).toBe("none");
    image().dispatchEvent(new window.MouseEvent("dblclick", { bubbles: true, cancelable: true }));
    expect(body.classList.contains("is-zoomed")).toBe(true);
    // Enlarged, a swipe moves the picture, not to the next one; a pinch never pages.
    swipe(300, 100);
    expect(count.textContent).toBe("1 / 2");
    document.body.dispatchEvent(new window.KeyboardEvent("keydown", { key: "0", bubbles: true }));
    expect(image().style.transform).toBe("");
    swipe(300, 100, true);
    expect(count.textContent).toBe("1 / 2");
    // Fitted, it pages; the next picture starts fitted.
    image().dispatchEvent(new window.MouseEvent("dblclick", { bubbles: true, cancelable: true }));
    document.getElementById("attachmentViewerNext").click();
    expect(count.textContent).toBe("2 / 2");
    expect(body.classList.contains("is-zoomed")).toBe(false);
    await vi.waitFor(() => expect(image()?.alt).toBe("picture-b.webp"));
    expect(image().style.transform).toBe("");
    swipe(300, 100);
    expect(count.textContent).toBe("1 / 2");
  });
});
