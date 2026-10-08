import { describe, expect, it } from "vitest";
import { loadScripts } from "./helpers/appWindow.mjs";

const BODY = '<div id="appSidebar" class="sidebar"></div>';

function boot({ stored, width = 1440 } = {}) {
  return loadScripts(["static/js/sidebar-resize.js"], {
    body: BODY,
    before(window) {
      Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
      if (stored !== undefined) window.localStorage.setItem("sidebar_width", stored);
    },
  });
}

function pointer(window, type, props) {
  const event = new window.MouseEvent(type, { bubbles: true, cancelable: true, button: 0, ...props });
  Object.defineProperty(event, "pointerId", { value: props.pointerId ?? 1 });
  return event;
}

const width = window => window.document.documentElement.style.getPropertyValue("--sidebar-width");

describe("sidebar resize", () => {
  it("applies a stored width before the page renders and ignores invalid values", () => {
    const stored = boot({ stored: "340" });
    expect(width(stored.window)).toBe("340px");
    stored.dom.window.close();
    for (const value of ["abc", "-5", "0"]) {
      const invalid = boot({ stored: value });
      expect(width(invalid.window)).toBe(""); // the CSS default (260px)
      invalid.dom.window.close();
    }
    const tooWide = boot({ stored: "900" });
    expect(width(tooWide.window)).toBe("480px");
    tooWide.dom.window.close();
  });

  it("mounts an accessible separator next to the sidebar", () => {
    const { window, document, dom } = boot();
    document.dispatchEvent(new window.Event("DOMContentLoaded"));
    const handle = document.getElementById("sidebarResizer");
    expect(handle.previousElementSibling.id).toBe("appSidebar");
    expect(handle.getAttribute("role")).toBe("separator");
    expect(handle.getAttribute("aria-orientation")).toBe("vertical");
    expect(handle.getAttribute("aria-controls")).toBe("appSidebar");
    expect(handle.tabIndex).toBe(0);
    expect([handle.getAttribute("aria-valuemin"), handle.getAttribute("aria-valuenow"), handle.getAttribute("aria-valuemax")])
      .toEqual(["200", "260", "480"]);
    dom.window.close();
  });

  it("follows a pointer drag, persists only at the end and resets on double-click", () => {
    const { window, document, dom } = boot();
    document.dispatchEvent(new window.Event("DOMContentLoaded"));
    const handle = document.getElementById("sidebarResizer");
    handle.dispatchEvent(pointer(window, "pointerdown", { clientX: 260 }));
    expect(document.body.classList.contains("is-resizing-sidebar")).toBe(true);
    handle.dispatchEvent(pointer(window, "pointermove", { clientX: 300 }));
    handle.dispatchEvent(pointer(window, "pointermove", { clientX: 345 }));
    expect(width(window)).toBe("345px");
    expect(window.localStorage.getItem("sidebar_width")).toBe(null);
    // Another pointer cannot take over the drag.
    handle.dispatchEvent(pointer(window, "pointermove", { clientX: 600, pointerId: 2 }));
    expect(width(window)).toBe("345px");
    handle.dispatchEvent(pointer(window, "pointerup", { clientX: 345 }));
    expect(document.body.classList.contains("is-resizing-sidebar")).toBe(false);
    expect(window.localStorage.getItem("sidebar_width")).toBe("345");
    handle.dispatchEvent(pointer(window, "pointermove", { clientX: 400 }));
    expect(width(window)).toBe("345px"); // no drag without pointerdown
    handle.dispatchEvent(new window.MouseEvent("dblclick", { bubbles: true }));
    expect(width(window)).toBe("");
    expect(window.localStorage.getItem("sidebar_width")).toBe(null);
    expect(window.App.sidebarResize.get()).toBe(260);
    dom.window.close();
  });

  it("clamps drags and supports the keyboard", () => {
    const { window, document, dom } = boot();
    document.dispatchEvent(new window.Event("DOMContentLoaded"));
    const handle = document.getElementById("sidebarResizer");
    handle.dispatchEvent(pointer(window, "pointerdown", { clientX: 260 }));
    handle.dispatchEvent(pointer(window, "pointermove", { clientX: 2000 }));
    expect(width(window)).toBe("480px");
    handle.dispatchEvent(pointer(window, "pointermove", { clientX: -500 }));
    expect(width(window)).toBe("200px");
    handle.dispatchEvent(pointer(window, "pointercancel", {}));
    expect(window.localStorage.getItem("sidebar_width")).toBe("200");
    const key = (name, shiftKey = false) => handle.dispatchEvent(new window.KeyboardEvent("keydown", { key: name, shiftKey, bubbles: true, cancelable: true }));
    key("ArrowRight");
    expect(window.App.sidebarResize.get()).toBe(210);
    key("ArrowRight", true);
    expect(window.App.sidebarResize.get()).toBe(250);
    key("ArrowLeft");
    expect(window.App.sidebarResize.get()).toBe(240);
    key("End");
    expect(window.App.sidebarResize.get()).toBe(480);
    key("Home");
    expect(window.App.sidebarResize.get()).toBe(200);
    expect(handle.getAttribute("aria-valuenow")).toBe("200");
    key("Enter");
    expect(window.App.sidebarResize.get()).toBe(200);
    dom.window.close();
  });

  it("keeps the chosen width when the window narrows and brings it back when it widens", () => {
    const { window, document, dom } = boot({ stored: "460" });
    document.dispatchEvent(new window.Event("DOMContentLoaded"));
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1000 });
    window.dispatchEvent(new window.Event("resize"));
    expect(width(window)).toBe("400px");
    expect(window.localStorage.getItem("sidebar_width")).toBe("460");
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1600 });
    window.dispatchEvent(new window.Event("resize"));
    expect(width(window)).toBe("460px");
    dom.window.close();
  });
});
