// =====================================================================
// attachments.js
// Datei-Anhaenge (Pro-Feature): Attach-Menue, Upload-/Paste-/Drop-Validierung,
// Chips, Viewer-Vorschau, Bookmark-Vorschau-Chips. In eigene IIFE gekapselt.
// Extrahiert aus templates/index.html (initApp-Closure).
// Exporte: window.pendingAttachments, window.renderAttachmentChips,
// window.clearPendingAttachments, window.getAttachmentsPayload,
// window.showBookmarkAttachments.
// Call-time-Abhaengigkeiten: window.auth, window.trackUmamiEvent,
// DOM (#attachTrigger, #attachMenu, #attachFileInput, #attachmentBar, ...).
// =====================================================================

(function () {
  // Telemetrie-Wrapper (entspricht trackAppEvent aus initApp).
  function trackAppEvent(eventName, eventData = {}) {
    if (typeof window.trackUmamiEvent === "function") {
      window.trackUmamiEvent(eventName, eventData);
    }
  }

  // --- ATTACHMENTS (every signed-in account) ---
  const ATTACH_MAX_FILES = 2;
  const ATTACH_MAX_BYTES = 5 * 1024 * 1024;
  // Bilder werden vor dem Hochladen verkleinert, deshalb darf HIER mehr
  // reinkommen als rausgeht: ein Handyfoto hat 4-8 MB und soll nicht abgelehnt
  // werden, nur weil es aus der Kamera kommt. Was den Server erreicht, ist die
  // verkleinerte Fassung -- der Server erzwingt das noch einmal selbst.
  const IMAGE_MAX_INPUT_BYTES = 15 * 1024 * 1024;
  // Gleiche Werte wie in app/services/llm/attachments.py.
  const IMAGE_MAX_EDGE = 1568;
  const IMAGE_TARGET_BYTES = 900 * 1024;
  const IMAGE_JPEG_QUALITY = 0.82;
  const DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  // Die kanonischen Typen, die auch der Server kennt. Was der Browser sonst
  // noch meldet (text/markdown, text/csv, ...), fuehrt canonicalMime hierher
  // zurueck — der `accept`-Filter des Datei-Feldes ist weiterhin grosszuegiger.
  const ATTACH_ALLOWED_MIMES = ["application/pdf", DOCX_MIME, "text/plain", "image/png", "image/jpeg", "image/webp"];
  const ATTACH_TYPES_LABEL = "PDF, Word (.docx), TXT, MD, CSV, PNG, JPG, WebP";
  // Familien, deren aktuell effektives Modell keine Anhaenge lesen kann.
  function attachmentBlockedFamilies() {
    if (window.App?.agentChat?.isSelected?.()) return [];
    return (window.App?.modelPrefs || []).filter(pref => {
      const model = document.getElementById(pref.selectId)?.value;
      const accepts = typeof window.App?.modelAcceptsAttachments === "function"
        ? window.App.modelAcceptsAttachments(pref, model)
        : pref.handlesAttachments !== false;
      return !accepts;
    });
  }

  function attachmentBlockMessage(families) {
    const names = families.map(pref => pref.label);
    if (!names.length) return "";
    const listed = names.length === 1
      ? names[0]
      : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
    const verb = names.length === 1 ? "is" : "are";
    const pronoun = names.length === 1 ? "its" : "their";
    return `${listed} ${verb} paused for this question because ${pronoun} API cannot read `
      + `attachments. Remove the files to use ${listed} again.`;
  }
  window.pendingAttachments = [];

  (function initAttachments() {
    const trigger = document.getElementById("attachTrigger");
    const menu = document.getElementById("attachMenu");
    const uploadOption = document.getElementById("attachUploadOption");
    const fileInput = document.getElementById("attachFileInput");
    const bar = document.getElementById("attachmentBar");
    const inputContainer = document.querySelector(".chat-input-container");
    const questionInput = document.getElementById("questionInput");
    if (!trigger || !menu || !uploadOption || !fileInput || !bar) return;

    // One tray, two homes: the toolbar on the start screen, the composer in a chat.
    // Move the actual nodes so previews/removal keep their state and handlers.
    const composerHome = document.createComment("composer-attachments-home");
    bar.before(composerHome);
    function syncComposerPlacement() {
      const toolbar = document.getElementById("composerModeBar");
      // A docked toolbar (in a chat) carries only a status line; files then
      // belong above the question in the composer itself.
      const inToolbar = toolbar && !toolbar.hidden && toolbar.dataset.docked !== "true";
      const parent = inToolbar ? toolbar : composerHome.parentNode;
      if (!parent || bar.parentNode === parent) return;
      const focus = bar.contains(document.activeElement) ? document.activeElement : null;
      if (inToolbar) toolbar.prepend(bar);
      else composerHome.after(bar);
      focus?.focus({ preventScroll: true });
    }

    let pendingFileReads = 0;
    let dragDepth = 0;
    // Auswahlzustand je blockierter Familie vor dem Anhang.
    const selectionBeforeAttachment = new Map();
    // Waehrend des Abgebens beim Senden ist der Composer zwar leer, die Dateien
    // sind aber gerade RAUSGEGANGEN: der Lauf-Block bleibt dann bestehen.
    let detachingForSend = false;

    function hasSendableAttachments() {
      return (window.pendingAttachments || []).some(function (att) {
        return !att.previewOnly && !!att.data;
      });
    }

    function syncAttachmentCompatibility() {
      const families = attachmentBlockedFamilies();
      const blockedIds = new Set(families.map(family => family.checkId));
      const incompatible = hasSendableAttachments();
      const message = attachmentBlockMessage(families);

      (window.App?.modelPrefs || []).forEach(family => {
        const checkbox = document.getElementById(family.checkId);
        if (!checkbox) return;
        const label = document.querySelector(`label[for='${family.checkId}']`);
        const responseBox = document.getElementById(family.responseId);
        const excludeButton = responseBox?.querySelector(".exclude-btn");

        if (incompatible && blockedIds.has(family.checkId)) {
          if (!selectionBeforeAttachment.has(family.checkId)) {
            selectionBeforeAttachment.set(family.checkId, checkbox.checked);
          }
          if (checkbox.checked) {
            window.App?.setModelSelectionState?.(family.responseId, false, {
              persist: false,
              syncCheckbox: true,
              animate: true
            });
          }
          checkbox.disabled = true;
          checkbox.setAttribute("aria-describedby", "attachmentProviderNotice");
          if (label) {
            label.classList.add("is-attachment-incompatible");
            label.title = message;
          }
          if (excludeButton) {
            excludeButton.disabled = true;
            excludeButton.title = message;
            excludeButton.setAttribute("aria-label", message);
          }
          return;
        }

        if (checkbox.getAttribute("aria-describedby") === "attachmentProviderNotice") {
          checkbox.disabled = false;
          checkbox.removeAttribute("aria-describedby");
        }
        if (label) label.classList.remove("is-attachment-incompatible");
        if (excludeButton) excludeButton.disabled = false;

        // Der Composer ist leer, WEIL der Nutzer die Dateien entfernt hat: der
        // naechste Lauf geht ohne Anhaenge raus, also faellt auch der Lauf-Block.
        // Beim Senden (detachingForSend) ist der Composer ebenfalls leer, die
        // Dateien sind aber gerade mit der Frage rausgegangen — dort bleibt der
        // Block bis zum naechsten Senden stehen.
        if (!detachingForSend) {
          window.App?.setRunModelBlock?.(family.responseId, false);
        }

        if (selectionBeforeAttachment.has(family.checkId)) {
          const shouldRestore = selectionBeforeAttachment.get(family.checkId);
          selectionBeforeAttachment.delete(family.checkId);
          window.App?.setModelSelectionState?.(family.responseId, shouldRestore, {
            persist: false,
            syncCheckbox: true,
            animate: true
          });
        }
      });
    }

    function setMenuOpen(open) {
      menu.hidden = !open;
      trigger.setAttribute("aria-expanded", String(open));
      trigger.classList.toggle("is-open", open);
      if (inputContainer) inputContainer.classList.toggle("attach-menu-open", open);
      // Genau EIN Popup im Composer: der Modell-Picker stoppt auf seinem
      // Trigger die Propagation, also erreicht ihn unser document-Listener nie
      // — er muss hier ausdruecklich zugemacht werden.
      if (open) window.App?.collapseExpandedModelPicker?.();
    }

    // Andere Composer-Popups schliessen dieses Menue ueber window.App.
    window.App = window.App || {};
    window.App.closeAttachMenu = function () {
      if (!menu.hidden) setMenuOpen(false);
    };

    trigger.addEventListener("click", function (event) {
      event.stopPropagation();
      setMenuOpen(menu.hidden);
    });

    document.addEventListener("click", function (event) {
      if (!menu.hidden && !menu.contains(event.target) && event.target !== trigger) {
        setMenuOpen(false);
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") return;
      const viewer = document.getElementById("attachmentViewerModal");
      if (viewer && !viewer.hidden) {
        closeAttachmentViewer();
        return;
      }
      if (!menu.hidden) setMenuOpen(false);
    });

    // --- Viewer (einfache Vorschau beim Klick auf einen Chip) ---
    const viewerOverlay = document.getElementById("attachmentViewerModal");
    const viewerTitle = document.getElementById("attachmentViewerTitle");
    const viewerBody = document.getElementById("attachmentViewerBody");
    const viewerClose = document.getElementById("attachmentViewerClose");
    let viewerObjectUrl = null;
    // Stored Agent files load asynchronously; a newer open or a close makes
    // an older response stale so it can never paint into the wrong preview.
    let viewerToken = 0;

    function closeAttachmentViewer() {
      if (!viewerOverlay) return;
      viewerToken++;
      viewerOverlay.hidden = true;
      if (viewerBody) viewerBody.innerHTML = "";
      if (viewerObjectUrl) {
        URL.revokeObjectURL(viewerObjectUrl);
        viewerObjectUrl = null;
      }
    }

    function base64ToBlob(base64Data, mime) {
      const binary = atob(base64Data);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      return new Blob([bytes], { type: mime });
    }

    function viewerNotice(label, message) {
      const notice = document.createElement("div");
      notice.className = "attachment-viewer-notice";
      const icon = document.createElement("span");
      icon.className = "attachment-chip-icon";
      icon.textContent = label;
      const text = document.createElement("p");
      text.textContent = message;
      notice.appendChild(icon);
      notice.appendChild(text);
      return notice;
    }

    function readDataUrl(blob) {
      return new Promise(function (resolve, reject) {
        const reader = new FileReader();
        reader.onload = function () { resolve(String(reader.result || "")); };
        reader.onerror = function () { reject(new Error("Preview is not available in this browser.")); };
        reader.readAsDataURL(blob);
      });
    }

    // Download and removal for a stored Agent file. Removal asks once more
    // inline: it is permanent and the agent loses access to the file.
    function storedFileActions(att, blob) {
      const row = document.createElement("div");
      row.className = "attachment-viewer-actions";
      const download = document.createElement("button");
      download.type = "button";
      download.className = "attachment-viewer-action";
      download.textContent = "Download";
      download.addEventListener("click", function () {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = att.name;
        link.click();
        setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
      });
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "attachment-viewer-action is-quiet";
      remove.textContent = "Remove from chat";
      remove.addEventListener("click", function () {
        row.replaceChildren();
        const question = document.createElement("span");
        question.className = "attachment-viewer-confirm";
        question.textContent = "Remove " + att.name + "? The agent can no longer use it in this chat.";
        const confirm = document.createElement("button");
        confirm.type = "button";
        confirm.className = "attachment-viewer-action is-danger";
        confirm.textContent = "Remove";
        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.className = "attachment-viewer-action is-quiet";
        cancel.textContent = "Cancel";
        cancel.addEventListener("click", function () {
          row.replaceWith(storedFileActions(att, blob));
        });
        confirm.addEventListener("click", async function () {
          confirm.disabled = cancel.disabled = true;
          confirm.textContent = "Removing…";
          try {
            await window.App.agentWorkspace.removeFile(att.fileId);
            closeAttachmentViewer();
          } catch (failure) {
            window.App?.showPopup?.(failure.message);
            confirm.disabled = cancel.disabled = false;
            confirm.textContent = "Remove";
          }
        });
        row.append(question, confirm, cancel);
        cancel.focus();
      });
      row.append(download, remove);
      return row;
    }

    function showStoredAttachment(att) {
      const token = viewerToken;
      const loading = document.createElement("p");
      loading.className = "attachment-viewer-loading";
      loading.textContent = "Loading preview…";
      viewerBody.appendChild(loading);
      window.App.agentWorkspace.openFile(att.fileId).then(async function (file) {
        const mime = file.mime || att.mime;
        const image = mime.indexOf("image/") === 0 ? await readDataUrl(file.blob) : "";
        if (token !== viewerToken) return;
        viewerBody.innerHTML = "";
        if (image) {
          const img = document.createElement("img");
          img.className = "attachment-viewer-image";
          img.alt = att.name;
          img.src = image;
          viewerBody.appendChild(img);
        } else if (mime === "application/pdf" || mime.indexOf("text/") === 0) {
          viewerObjectUrl = URL.createObjectURL(mime.indexOf("text/") === 0
            ? new Blob([file.blob], { type: "text/plain;charset=utf-8" }) : file.blob);
          const frame = document.createElement("iframe");
          frame.className = "attachment-viewer-frame";
          frame.title = att.name;
          frame.src = viewerObjectUrl;
          viewerBody.appendChild(frame);
        } else {
          viewerBody.appendChild(viewerNotice(chipIconLabel(mime),
            "This file type cannot be previewed here. Download it to open it."));
        }
        viewerBody.appendChild(storedFileActions(att, file.blob));
      }).catch(function (failure) {
        if (token !== viewerToken) return;
        viewerBody.innerHTML = "";
        viewerBody.appendChild(viewerNotice(chipIconLabel(att.mime),
          (failure && failure.message) || "This file could not be loaded. Please retry."));
      });
    }

    function openAttachmentViewer(att) {
      if (!viewerOverlay || !viewerBody) return;
      closeAttachmentViewer();
      viewerTitle.textContent = att.name;
      viewerBody.innerHTML = "";

      if (att.fileId && window.App?.agentWorkspace?.openFile) {
        showStoredAttachment(att);
      } else if (att.previewOnly || !att.data) {
        const notice = document.createElement("div");
        notice.className = "attachment-viewer-notice";
        const icon = document.createElement("span");
        icon.className = "attachment-chip-icon";
        icon.textContent = chipIconLabel(att.mime);
        const text = document.createElement("p");
        text.textContent = "This file was attached to the saved chat. To keep storage light, only the file name is stored – not the file itself.";
        notice.appendChild(icon);
        notice.appendChild(text);
        viewerBody.appendChild(notice);
      } else if (att.mime === DOCX_MIME) {
        // Browser können DOCX nicht inline rendern – nur Hinweis zeigen.
        const notice = document.createElement("div");
        notice.className = "attachment-viewer-notice";
        const icon = document.createElement("span");
        icon.className = "attachment-chip-icon";
        icon.textContent = "DOC";
        const text = document.createElement("p");
        text.textContent = "Word documents cannot be previewed here. The extracted text is sent to the models with your question.";
        notice.appendChild(icon);
        notice.appendChild(text);
        viewerBody.appendChild(notice);
      } else if (att.mime.indexOf("image/") === 0) {
        const img = document.createElement("img");
        img.className = "attachment-viewer-image";
        img.alt = att.name;
        img.src = "data:" + att.mime + ";base64," + att.data;
        viewerBody.appendChild(img);
      } else {
        try {
          viewerObjectUrl = URL.createObjectURL(base64ToBlob(att.data, att.mime));
          const frame = document.createElement("iframe");
          frame.className = "attachment-viewer-frame";
          frame.title = att.name;
          frame.src = viewerObjectUrl;
          viewerBody.appendChild(frame);
        } catch (e) {
          const fallback = document.createElement("p");
          fallback.className = "attachment-viewer-notice";
          fallback.textContent = "Preview is not available in this browser.";
          viewerBody.appendChild(fallback);
        }
      }

      viewerOverlay.hidden = false;
      trackAppEvent("app_attachment_viewed", { mime: att.mime, preview_only: !!att.previewOnly, stored: !!att.fileId });
    }

    if (viewerClose) viewerClose.addEventListener("click", closeAttachmentViewer);
    if (viewerOverlay) {
      viewerOverlay.addEventListener("click", function (event) {
        if (event.target === viewerOverlay) closeAttachmentViewer();
      });
    }

    // Files are open to every account since 2026-10-02: they are paid from
    // the same token account as the question. They still need an account,
    // so a guest is asked to sign in instead of seeing a file picker.
    function canAttach() {
      return Boolean(window.auth?.currentUser);
    }
    function showAttachmentSignIn(source) {
      setMenuOpen(false);
      trackAppEvent("app_attachment_locked_click", { source: source });
      const modal = document.getElementById("loginModal");
      if (window.App?.openAuthModal) {
        window.App.openAuthModal("login", null, "attachments");
      } else if (modal) {
        modal.style.display = "block";
        trackAppEvent("auth_modal_open", { source: "attachments" });
        requestAnimationFrame(() => document.getElementById("loginEmail")?.focus());
      } else {
        window.App?.showPopup?.("Sign in to attach files. You can enter your question as text.");
      }
    }

    uploadOption.addEventListener("click", function () {
      if (!canAttach()) {
        showAttachmentSignIn("picker");
        return;
      }
      setMenuOpen(false);
      fileInput.click();
    });

    function isDriveFile(att) {
      return Boolean(att && att.origin && att.origin.source === "google_drive");
    }

    function formatFileSize(bytes) {
      if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
      return Math.max(1, Math.round(bytes / 1024)) + " KB";
    }

    // Bilder einer gesendeten Nachricht zeigen sich als kleine Kachel statt
    // als "IMG"-Plakette. Die Nachricht traegt nur Metadaten: direkt nach dem
    // Senden kommt das Bild aus dem Composer (sentImages, Schluessel aus Name,
    // Groesse und Typ), spaeter aus der gespeicherten Agent-Datei (einmal pro
    // Datei geladen, storedImages). Fehlt beides, bleibt die Plakette.
    const sentImages = new Map();
    const storedImages = new Map();
    function imageKey(att) {
      return [att.name, att.size || 0, att.mime].join("|");
    }
    function storedImage(fileId) {
      if (!storedImages.has(fileId)) {
        const load = window.App?.agentWorkspace?.openFile
          ? window.App.agentWorkspace.openFile(fileId).then(function (file) {
            if ((file.mime || file.blob.type || "").indexOf("image/") !== 0) throw new Error("Not an image");
            return URL.createObjectURL(file.blob);
          })
          : Promise.reject(new Error("Files are not available"));
        // A failed load (chat changed, file removed) may be retried later.
        load.catch(function () { storedImages.delete(fileId); });
        storedImages.set(fileId, load);
      }
      return storedImages.get(fileId);
    }
    function imageTile(chip, att, icon) {
      const img = document.createElement("img");
      img.className = "attachment-chip-thumb";
      img.alt = att.name;
      img.decoding = "async";
      chip.classList.add("is-image-tile");
      chip.title = att.name;
      const fallback = function () {
        chip.classList.remove("is-image-tile", "is-thumb-loading");
        img.replaceWith(icon);
      };
      const known = sentImages.get(imageKey(att));
      if (known) {
        img.src = known;
      } else {
        chip.classList.add("is-thumb-loading");
        storedImage(att.fileId).then(function (url) {
          img.addEventListener("load", function () { chip.classList.remove("is-thumb-loading"); }, { once: true });
          img.src = url;
        }, fallback);
      }
      img.addEventListener("error", fallback, { once: true });
      return img;
    }

    // Baut den Chip einer Datei. `readonly` macht ihn zum reinen
    // Anzeigeelement: kein Viewer, kein Entfernen — so haengt er an einer
    // bereits gesendeten Nachricht, deren Datei es nicht mehr gibt.
    function buildAttachmentChip(att, options) {
      const readonly = Boolean(options && options.readonly);
      const chip = document.createElement("div");
      chip.className = "attachment-chip";
      if (att.previewOnly) chip.classList.add("is-preview-only");

      if (!att.previewOnly && att.mime.indexOf("image/") === 0 && att.data) {
        const img = document.createElement("img");
        img.className = "attachment-chip-thumb";
        img.alt = "";
        img.src = "data:" + att.mime + ";base64," + att.data;
        chip.appendChild(img);
      } else {
        // Die Plakette traegt seit 2026-08-17 keine Typfarbe mehr (monochrome
        // App): der Dateityp steht als Text darin, nicht in einem Farbton.
        const icon = document.createElement("span");
        icon.className = "attachment-chip-icon";
        icon.textContent = chipIconLabel(att.mime);
        const tile = readonly && !att.previewOnly && att.mime.indexOf("image/") === 0
          && (att.fileId || sentImages.has(imageKey(att)));
        chip.appendChild(tile ? imageTile(chip, att, icon) : icon);
      }

      const meta = document.createElement("span");
      meta.className = "attachment-chip-meta";
      const nameEl = document.createElement("span");
      nameEl.className = "attachment-chip-name";
      nameEl.textContent = att.name;
      nameEl.title = att.name;
      const sizeEl = document.createElement("span");
      sizeEl.className = "attachment-chip-size";
      // A file from Google Drive is an ordinary file of the message; only its
      // origin is named, because Google data changes the chat's rules.
      const fromDrive = isDriveFile(att);
      if (fromDrive) chip.classList.add("is-drive");
      if (att.loading) {
        chip.classList.add("is-loading");
        sizeEl.textContent = "Loading from Google Drive…";
      } else if (att.error) {
        // Agent uploads keep a rejected file in the composer with the server's
        // reason, so the user can remove or replace it and send again.
        chip.classList.add("has-error");
        sizeEl.textContent = "Couldn't upload · " + att.error;
        sizeEl.title = att.error;
      } else if (readonly) {
        sizeEl.textContent = att.size ? formatFileSize(att.size) : "";
      } else {
        sizeEl.textContent = att.previewOnly
          ? (att.size ? formatFileSize(att.size) + " · saved chat" : "saved chat")
          : formatFileSize(att.size);
      }
      if (fromDrive && !att.loading && !att.error) {
        sizeEl.textContent = "Google Drive" + (sizeEl.textContent ? " · " + sizeEl.textContent : "");
      }
      meta.appendChild(nameEl);
      meta.appendChild(sizeEl);
      chip.appendChild(meta);

      // Older image uploads carry a capability note, not a reading limit.
      const warnings = Array.isArray(att.warnings)
        ? att.warnings.filter(w => w && !String(w).startsWith("Visual content is sent only to models")) : [];
      if (readonly && warnings.length) {
        // Agent files that were only partly readable (scans, limits) say so
        // on the message they were sent with, not only in the files list.
        chip.classList.add("has-warning");
        const badge = document.createElement("span");
        badge.className = "attachment-chip-warning";
        badge.textContent = "Partly read";
        badge.title = warnings.join(" ");
        meta.appendChild(badge);
        chip.setAttribute("aria-label", att.name + ", only partly readable: " + warnings.join(" "));
        chip.setAttribute("role", "group");
      }

      // A sent message's file can only be opened again when it was stored
      // (Agent chats); other sent chips are plain labels. A file still
      // loading from Drive has nothing to preview yet.
      if ((readonly && !att.fileId) || att.loading) return chip;
      if (readonly) chip.removeAttribute("role");

      // Preview and removal are sibling buttons, never nested controls.
      const preview = document.createElement("button");
      preview.type = "button";
      preview.className = "attachment-chip-preview";
      preview.title = "Preview " + att.name;
      preview.setAttribute("aria-label", chip.getAttribute("aria-label")
        ? "Preview " + chip.getAttribute("aria-label")
        : "Preview " + att.name + (att.size ? ", " + formatFileSize(att.size) : ""));
      chip.removeAttribute("aria-label");
      preview.append(...chip.childNodes);
      chip.appendChild(preview);
      preview.addEventListener("click", function () {
        openAttachmentViewer(att);
      });
      return chip;
    }

    // Anhaenge einer bereits gesendeten Frage. Sie stehen im Thread an ihrer
    // Nachricht und sind reine Metadaten — die Dateien selbst sind mit dem
    // Lauf rausgegangen und werden nicht aufbewahrt.
    function renderMessageAttachments(container, attachmentsMeta) {
      if (!container) return 0;
      container.innerHTML = "";
      const items = (Array.isArray(attachmentsMeta) ? attachmentsMeta : [])
        .filter(function (item) { return item && item.name; });
      items.forEach(function (item) {
        container.appendChild(buildAttachmentChip({
          name: String(item.name),
          mime: String(item.mime || ""),
          size: Number(item.size) || 0,
          warnings: Array.isArray(item.warnings) ? item.warnings.map(String).slice(0, 5) : [],
          // Agent uploads stay in their chat, so the chip can open them again.
          fileId: /^[a-f0-9]{32}$/.test(String(item.id || "")) ? String(item.id) : "",
          origin: item.source === "google_drive" || item.kind === "drive_file" || item.origin?.source === "google_drive"
            ? { source: "google_drive" } : null,
          data: null
        }, { readonly: true }));
      });
      container.hidden = items.length === 0;
      return items.length;
    }

    // Beim Senden gibt der Composer seine Anhaenge ab: die Chips wandern an
    // die Nachricht, das Feld startet leer in die naechste Frage. Ein Anhang,
    // der nach dem Senden ueber dem leeren Feld haengen bleibt, behauptet
    // sonst, er gehoere zur naechsten Frage — mitgeschickt wurde er aber mit
    // der letzten.
    // Was von den Anhaengen an der Nachricht haengen bleibt: reine Metadaten.
    // Die Blase der gerade abgeschickten Frage braucht sie schon, BEVOR der
    // Composer die Dateien abgibt — der Lauf kann noch scheitern, dann muessen
    // sie unveraendert am Feld stehen.
    function messageMeta() {
      return (window.pendingAttachments || [])
        .filter(function (att) { return !att.previewOnly && att.data; })
        .map(function (att) {
          const meta = { name: att.name, mime: att.mime, size: att.size || 0 };
          if (att.mime.indexOf("image/") === 0) sentImages.set(imageKey(meta), "data:" + att.mime + ";base64," + att.data);
          if (isDriveFile(att)) meta.origin = { source: "google_drive" };
          return meta;
        });
    }

    function detachForMessage() {
      invalidateImports();
      const meta = messageMeta();
      if (window.pendingAttachments.length) {
        window.pendingAttachments = [];
        detachingForSend = true;
        try {
          renderAttachmentChips();
        } finally {
          detachingForSend = false;
        }
      }
      return meta;
    }

    function renderAttachmentChips() {
      syncComposerPlacement();
      bar.innerHTML = "";
      const items = window.pendingAttachments;
      bar.hidden = items.length === 0;

      items.forEach(function (att, index) {
        const chip = buildAttachmentChip(att);

        const removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.className = "attachment-chip-remove";
        removeBtn.title = "Remove attachment";
        removeBtn.setAttribute("aria-label", "Remove " + att.name);
        removeBtn.innerHTML = "&#10005;";
        removeBtn.addEventListener("click", function (event) {
          event.stopPropagation();
          window.pendingAttachments.splice(index, 1);
          renderAttachmentChips();
          const next = bar.querySelectorAll(".attachment-chip-remove")[Math.min(index, window.pendingAttachments.length - 1)];
          const toolbar = document.getElementById("composerModeBar");
          (next || (!toolbar?.hidden && toolbar.dataset.docked !== "true" && document.getElementById("composerAttachButton")) || trigger).focus({ preventScroll: true });
        });
        chip.appendChild(removeBtn);

        bar.appendChild(chip);
      });

      const blockedFamilies = attachmentBlockedFamilies();
      if (hasSendableAttachments() && blockedFamilies.length) {
        const notice = document.createElement("p");
        notice.id = "attachmentProviderNotice";
        notice.className = "attachment-provider-notice";
        notice.setAttribute("role", "status");
        notice.setAttribute("aria-live", "polite");
        notice.textContent = blockedFamilies.map(family => family.label).join(", ")
          + " paused · No attachment support";
        notice.title = attachmentBlockMessage(blockedFamilies);
        bar.appendChild(notice);
      }

      syncAttachmentCompatibility();
      // Files arriving from the picker/paste must stay visible on mobile,
      // even if the composer collapsed while the file was being read.
      if (items.length) window.App?.composer?.expand?.();
      // A Drive file brings Google data (consent, agent-google.js).
      window.dispatchEvent(new CustomEvent("consensio:attachments-change"));
    }

    // Agent uploads report a per-file failure (or clear it with an empty
    // message). The payload copy is matched back to its pending attachment.
    function markError(file, message) {
      const target = (window.pendingAttachments || []).find(function (att) {
        return att.name === file?.name && (att.size || 0) === (file?.size || 0) && (!file?.data || att.data === file.data);
      });
      if (!target || (target.error || "") === (message || "")) return false;
      if (message) target.error = String(message).slice(0, 300);
      else delete target.error;
      renderAttachmentChips();
      return true;
    }

    window.renderAttachmentChips = renderAttachmentChips;
    window.App = window.App || {};
    window.App.attachments = {
      maxFiles: ATTACH_MAX_FILES,
      detachForMessage: detachForMessage,
      // True while a picked/pasted/dropped file of the CURRENT draft is still
      // being read. Send paths refuse to go out then, so a file can never
      // silently miss its question or land on the next one.
      isImporting: function () {
        return pendingFileReads > 0 || (window.pendingAttachments || []).some(function (att) { return att.loading; });
      },
      messageMeta: messageMeta,
      renderMessageAttachments: renderMessageAttachments,
      markError: markError,
      refreshCompatibility: syncAttachmentCompatibility,
      syncComposerPlacement: syncComposerPlacement
    };
    syncComposerPlacement();

    window.clearPendingAttachments = function () {
      invalidateImports();
      if (!window.pendingAttachments.length) return;
      window.pendingAttachments = [];
      renderAttachmentChips();
    };

    // Was der Browser als Typ meldet, ist je nach Betriebssystem verschieden:
    // dieselbe .md kommt als "text/markdown", "text/plain" oder ganz ohne Typ.
    // Der Server kennt nur die kanonischen Typen — ohne diese Tabelle fiel eine
    // .csv still aus dem gespeicherten Chat heraus, obwohl der Lauf mit ihr
    // funktioniert hat (dort entscheiden die Bytes, nicht die Client-Angabe).
    const ATTACH_MIME_ALIASES = {
      "text/markdown": "text/plain",
      "text/x-markdown": "text/plain",
      "text/csv": "text/plain",
      "application/csv": "text/plain",
      "image/jpg": "image/jpeg"
    };

    function canonicalMime(mime) {
      const normalized = String(mime || "").split(";")[0].trim().toLowerCase();
      return ATTACH_MIME_ALIASES[normalized] || normalized;
    }

    function inferMime(file) {
      const declared = canonicalMime(file.type);
      if (ATTACH_ALLOWED_MIMES.indexOf(declared) !== -1) return declared;
      const name = (file.name || "").toLowerCase();
      if (name.endsWith(".pdf")) return "application/pdf";
      if (name.endsWith(".docx")) return DOCX_MIME;
      if (name.endsWith(".txt") || name.endsWith(".md") || name.endsWith(".markdown") || name.endsWith(".csv")) return "text/plain";
      if (name.endsWith(".png")) return "image/png";
      if (name.endsWith(".jpg") || name.endsWith(".jpeg")) return "image/jpeg";
      if (name.endsWith(".webp")) return "image/webp";
      return null;
    }

    function chipIconLabel(mime) {
      if (mime.indexOf("image/") === 0) return "IMG";
      if (mime === DOCX_MIME) return "DOC";
      if (mime.indexOf("text/") === 0) return "TXT";
      return "PDF";
    }

    function imageExtension(mime) {
      if (mime === "image/jpeg") return "jpg";
      if (mime === "image/webp") return "webp";
      return "png";
    }

    function attachmentName(file, mime, source, index) {
      const originalName = String(file.name || "").trim();
      if (originalName) return originalName;
      if (source === "paste") {
        return "pasted-image-" + Date.now() + (index ? "-" + (index + 1) : "") + "." + imageExtension(mime);
      }
      return "image-" + Date.now() + (index ? "-" + (index + 1) : "") + "." + imageExtension(mime);
    }

    // Ein Bild auf Providergroesse bringen, BEVOR es base64-kodiert im Request
    // landet. Dieselbe Datei geht an bis zu sechs Familien gleichzeitig raus;
    // bei 1568 px laengster Kante sieht keine davon weniger als vorher, der
    // Upload ist aber ein Bruchteil. Kleine Bilder bleiben unangetastet (ein
    // Screenshot behaelt seine PNG-Schaerfe).
    // Loest immer auf: `null` heisst "unveraendert weiterverwenden".
    function shrinkImage(file, mime) {
      return new Promise(function (resolve) {
        if (mime.indexOf("image/") !== 0 || typeof document.createElement("canvas").toBlob !== "function") {
          resolve(null);
          return;
        }
        const url = URL.createObjectURL(file);
        const image = new Image();
        image.onload = function () {
          URL.revokeObjectURL(url);
          const longest = Math.max(image.naturalWidth, image.naturalHeight);
          if (!longest || (longest <= IMAGE_MAX_EDGE && file.size <= IMAGE_TARGET_BYTES)) {
            resolve(null);
            return;
          }
          const ratio = Math.min(1, IMAGE_MAX_EDGE / longest);
          const canvas = document.createElement("canvas");
          canvas.width = Math.max(1, Math.round(image.naturalWidth * ratio));
          canvas.height = Math.max(1, Math.round(image.naturalHeight * ratio));
          const ctx = canvas.getContext("2d");
          if (!ctx) {
            resolve(null);
            return;
          }
          // JPEG kennt kein Alpha: Transparenz kommt auf Weiss statt auf
          // Schwarz, sonst wird aus einem PNG-Logo eine dunkle Flaeche.
          ctx.fillStyle = "#ffffff";
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
          canvas.toBlob(function (blob) {
            resolve(blob && blob.size < file.size ? { blob: blob, mime: "image/jpeg" } : null);
          }, "image/jpeg", IMAGE_JPEG_QUALITY);
        };
        image.onerror = function () {
          URL.revokeObjectURL(url);
          resolve(null);
        };
        image.src = url;
      });
    }

    // Aus "urlaub.png" wird nach der Neukodierung "urlaub.jpg": der Name darf
    // nicht laenger einen Typ behaupten, den die Datei nicht mehr hat.
    function renameToJpeg(name) {
      return String(name || "image").replace(/\.[^.\/]+$/, "") + ".jpg";
    }

    function readAsBase64(blob) {
      return new Promise(function (resolve, reject) {
        const reader = new FileReader();
        reader.onload = function () {
          resolve(String(reader.result || "").split(",", 2)[1] || "");
        };
        reader.onerror = function () {
          reject(new Error("The file could not be read."));
        };
        reader.readAsDataURL(blob);
      });
    }

    // Bilder duerfen groesser reinkommen, weil sie verkleinert wieder
    // rausgehen. Alles andere laesst sich nicht schrumpfen und behaelt die
    // harte Grenze.
    function maxInputBytes(mime) {
      return mime.indexOf("image/") === 0 ? IMAGE_MAX_INPUT_BYTES : ATTACH_MAX_BYTES;
    }

    // Every import belongs to one draft generation. Clearing the draft (send,
    // opening a saved chat, Agent upload) or an account change starts a new
    // generation: late reads of the old one are discarded and no longer count
    // against the new draft's file limit.
    let readGeneration = 0;
    function invalidateImports() {
      readGeneration++;
      pendingFileReads = 0;
    }
    window.addEventListener("consensio:auth-state", invalidateImports);
    function addFiles(files, options) {
      const generation = readGeneration;
      const owner = window.auth?.currentUser?.uid;
      const source = options && options.source ? options.source : "picker";
      const imagesOnly = !!(options && options.imagesOnly);
      if (!files.length) return;

      if (!canAttach()) {
        showAttachmentSignIn(source);
        return;
      }

      let unsupportedShown = false;
      let limitShown = false;

      files.forEach(function (file, index) {
        const mime = inferMime(file);
        if (!mime || (imagesOnly && mime.indexOf("image/") !== 0)) {
          if (!unsupportedShown) {
            alert(imagesOnly
              ? "Only PNG, JPG, and WebP images can be pasted here."
              : "'" + (file.name || "This file") + "' is not supported. Allowed: " + ATTACH_TYPES_LABEL + ".");
            unsupportedShown = true;
          }
          return;
        }
        const sizeLimit = maxInputBytes(mime);
        if (file.size > sizeLimit) {
          alert("'" + attachmentName(file, mime, source, index) + "' is "
            + formatFileSize(file.size) + ". The limit is "
            + Math.round(sizeLimit / (1024 * 1024)) + " MB per file.");
          return;
        }
        if (window.pendingAttachments.length + pendingFileReads >= ATTACH_MAX_FILES) {
          if (!limitShown) {
            alert("You can attach up to " + ATTACH_MAX_FILES + " files per question.");
            limitShown = true;
          }
          return;
        }

        pendingFileReads += 1;
        const name = attachmentName(file, mime, source, index);
        shrinkImage(file, mime).then(function (shrunk) {
          const payload = shrunk ? shrunk.blob : file;
          return readAsBase64(payload).then(function (base64Data) {
            if (generation !== readGeneration) return;
            pendingFileReads = Math.max(0, pendingFileReads - 1);
            if (owner !== window.auth?.currentUser?.uid || !base64Data) return;
            if (window.pendingAttachments.length >= ATTACH_MAX_FILES) return;
            const attachment = {
              name: shrunk ? renameToJpeg(name) : name,
              mime: shrunk ? shrunk.mime : mime,
              size: payload.size,
              data: base64Data
            };
            if (options && options.origin) attachment.origin = options.origin;
            window.pendingAttachments.push(attachment);
            renderAttachmentChips();
            trackAppEvent("app_attachment_added", {
              mime: shrunk ? shrunk.mime : mime,
              source: source,
              shrunk: shrunk ? 1 : 0
            });
          });
        }).catch(function () {
          // A failed read of an abandoned draft is not the new draft's error.
          if (generation !== readGeneration) return;
          pendingFileReads = Math.max(0, pendingFileReads - 1);
          alert("The file could not be read. Please try again.");
        });
      });
    }

    // A file that first has to be fetched (Google Drive). It holds its slot as
    // a loading chip, so Send waits and the file limit counts it; the fetched
    // bytes then pass the same checks as a picked file. Removing the chip
    // while it loads drops the result.
    function addRemote(item, load) {
      const generation = readGeneration;
      const owner = window.auth?.currentUser?.uid;
      const source = item.source || "remote";
      if (!canAttach()) {
        showAttachmentSignIn(source);
        return false;
      }
      if (window.pendingAttachments.length + pendingFileReads >= ATTACH_MAX_FILES) {
        alert("You can attach up to " + ATTACH_MAX_FILES + " files per question.");
        return false;
      }
      const placeholder = { name: String(item.name || "File"), mime: item.mime || "", size: item.size || 0,
        origin: item.origin || null, loading: true };
      window.pendingAttachments.push(placeholder);
      renderAttachmentChips();
      function release() {
        const index = window.pendingAttachments.indexOf(placeholder);
        if (index === -1 || generation !== readGeneration) return false;
        window.pendingAttachments.splice(index, 1);
        renderAttachmentChips();
        return true;
      }
      Promise.resolve().then(load).then(function (file) {
        if (owner !== window.auth?.currentUser?.uid) return;
        if (release()) addFiles([file], { source: source, origin: item.origin });
      }).catch(function (failure) {
        if (release()) window.App?.showPopup?.(failure?.message || "The file could not be loaded. Please try again.");
      });
      return true;
    }
    window.App.attachments.addRemote = addRemote;
    window.App.attachments.hasDriveFiles = function () {
      return (window.pendingAttachments || []).some(isDriveFile);
    };
    window.App.attachments.removeDriveFiles = function () {
      const before = window.pendingAttachments.length;
      window.pendingAttachments = window.pendingAttachments.filter(function (att) { return !isDriveFile(att); });
      if (window.pendingAttachments.length !== before) renderAttachmentChips();
      return before - window.pendingAttachments.length;
    };

    function transferFiles(dataTransfer) {
      if (!dataTransfer) return [];
      const directFiles = Array.from(dataTransfer.files || []);
      if (directFiles.length) return directFiles;
      return Array.from(dataTransfer.items || [])
        .filter(function (item) { return item.kind === "file"; })
        .map(function (item) { return item.getAsFile(); })
        .filter(Boolean);
    }

    function isImageLike(file) {
      if (String(file.type || "").toLowerCase().indexOf("image/") === 0) return true;
      const name = String(file.name || "").toLowerCase();
      return /\.(png|jpe?g|webp)$/.test(name);
    }

    function isFileDrag(event) {
      return Array.from((event.dataTransfer && event.dataTransfer.types) || []).indexOf("Files") !== -1;
    }

    function clearDragState() {
      dragDepth = 0;
      if (inputContainer) inputContainer.classList.remove("is-image-dragover");
    }

    fileInput.addEventListener("change", function () {
      const files = Array.from(fileInput.files || []);
      fileInput.value = "";
      addFiles(files, { source: "picker", imagesOnly: false });
    });

    if (questionInput) {
      questionInput.addEventListener("paste", function (event) {
        const files = transferFiles(event.clipboardData).filter(isImageLike);
        if (!files.length) return;
        event.preventDefault();
        addFiles(files, { source: "paste", imagesOnly: true });
      });
    }

    if (inputContainer) {
      inputContainer.addEventListener("dragenter", function (event) {
        if (!isFileDrag(event)) return;
        event.preventDefault();
        dragDepth += 1;
        inputContainer.classList.add("is-image-dragover");
      });

      inputContainer.addEventListener("dragover", function (event) {
        if (!isFileDrag(event)) return;
        event.preventDefault();
        if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
        inputContainer.classList.add("is-image-dragover");
      });

      inputContainer.addEventListener("dragleave", function (event) {
        if (!isFileDrag(event)) return;
        dragDepth = Math.max(0, dragDepth - 1);
        if (dragDepth === 0) inputContainer.classList.remove("is-image-dragover");
      });

      inputContainer.addEventListener("drop", function (event) {
        if (!isFileDrag(event)) return;
        event.preventDefault();
        const files = transferFiles(event.dataTransfer);
        clearDragState();
        // Drag-and-drop supports the same whitelist as the file picker.
        // Only clipboard paste stays image-only so normal text paste keeps
        // behaving like text input.
        addFiles(files, { source: "drop", imagesOnly: false });
      });

      window.addEventListener("dragend", clearDragState);
      window.addEventListener("drop", clearDragState);
    }

    window.addEventListener("pageshow", function () {
      window.setTimeout(syncAttachmentCompatibility, 0);
    });
  })();

  window.getAttachmentsPayload = function () {
    return (window.pendingAttachments || [])
      .filter(function (att) { return !att.previewOnly && att.data; })
      .map(function (att) {
        const item = { name: att.name, mime: att.mime, size: att.size, data: att.data };
        // Only Agent chats take Drive files; the upload names their origin.
        if (att.origin && att.origin.source === "google_drive") item.origin = att.origin;
        return item;
      });
  };

  // Anhänge eines gespeicherten Bookmarks. Sie gehören zu der Frage, mit der
  // sie damals rausgegangen sind, und stehen deshalb an ihr im Thread — nicht
  // im Eingabefeld, das der naechsten Frage gehoert. Reine Metadaten: die
  // Dateien selbst sind nicht gespeichert.
  window.showBookmarkAttachments = function (attachmentsMeta) {
    window.clearPendingAttachments?.();
    window.App?.setThreadQuestionAttachments?.(attachmentsMeta);
  };
})();
