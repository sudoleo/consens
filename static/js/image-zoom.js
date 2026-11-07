// Zooming into a picture in its preview (Max: "dass man bei einer
// Bildervorschau auch ranzoomen kann", Apple-like and without a toolbar).
// Two fingers or a trackpad pinch (Ctrl + wheel; Safari's gesture events)
// zoom about the point under them or the cursor, a double tap or click
// toggles between fitted and enlarged, an enlarged picture pans by dragging
// or a two-finger scroll, and + / - / 0 zoom from the keyboard. It never gets
// smaller than fitted, and once larger than its frame it leaves no gap at an
// edge. The browser's own page zoom stays where it is: the picture takes its
// touches (touch-action: none), and Ctrl + wheel and Safari's gestures over
// the frame are cancelled.
//
// App.imageZoom.attach(img, { frame, active }) -> { zoomed(), reset(), detach() }.
// The picture keeps its layout box; a transform (origin top left) moves it
// inside ``frame``, an ancestor that clips it while zoomed. ``active()`` says
// whether the keys are its (an open dialog). Classes for the caller's CSS:
// is-zoomed on the frame, is-panning while a drag holds the picture and
// is-settling while a jump (double tap, a key) animates. The math is plain
// functions on App.imageZoom for tests (clamp, zoomAt, pinch, maxScale,
// visibleCentre).
(() => {
  'use strict';
  const App = window.App = window.App || {};
  // A double tap or click enlarges this far; + and - multiply by STEP.
  const DOUBLE = 2.5;
  const STEP = 1.6;
  // At least 4x, further to the picture's own pixels, at most 8x.
  const MAX_LEAST = 4;
  const MAX_MOST = 8;
  // A trackpad pinch comes as Ctrl + wheel in small steps; a mouse wheel's
  // notch (100 px) is held to WHEEL_STEP, about 1.5x.
  const WHEEL_RATE = 0.01;
  const WHEEL_STEP = 40;
  const LINE = 16;
  // A tap is a short press that hardly moves; two within TAP_GAP and
  // TAP_NEAR of each other are a double tap.
  const TAP_MS = 300;
  const TAP_SLOP = 10;
  const TAP_GAP = 350;
  const TAP_NEAR = 30;
  // The jump's transition in CSS (--dur-state) ends well before this.
  const SETTLE_MS = 400;
  const FITTED = Object.freeze({ scale: 1, x: 0, y: 0 });

  // ---- The math --------------------------------------------------------------
  // A state { scale, x, y } is the transform of the picture's layout box
  // ``base`` ({ left, top, width, height } in client pixels, untransformed)
  // inside ``frame`` (the same).

  // One axis: where the zoomed picture may lie. Smaller than the frame, it
  // stays centred where the fitted picture is (within the frame); larger, it
  // covers the frame from edge to edge.
  function clampAxis(offset, scale, start, size, frameStart, frameSize) {
    const zoomed = size * scale;
    const lead = zoomed <= frameSize
      ? Math.min(frameStart + frameSize - zoomed, Math.max(frameStart, start + (size - zoomed) / 2))
      : Math.min(frameStart, Math.max(frameStart + frameSize - zoomed, start + offset));
    return lead - start;
  }
  function clamp(state, base, frame) {
    if (!(state.scale > 1)) return { ...FITTED };
    return {
      scale: state.scale,
      x: clampAxis(state.x, state.scale, base.left, base.width, frame.left, frame.width),
      y: clampAxis(state.y, state.scale, base.top, base.height, frame.top, frame.height),
    };
  }
  // Zoomed to ``scale`` (between fitted and ``max``) with the point under
  // ``at`` staying where it is.
  function zoomAt(state, scale, at, base, max = MAX_LEAST) {
    const next = Math.min(max, Math.max(1, scale));
    const ratio = next / state.scale;
    return {
      scale: next,
      x: at.x - (at.x - base.left - state.x) * ratio - base.left,
      y: at.y - (at.y - base.top - state.y) * ratio - base.top,
    };
  }
  // Two fingers: ``ratio`` is how far apart they are against the start, and
  // the point between them carries the picture from ``from`` to ``to``.
  function pinch(start, from, to, ratio, base, max) {
    const zoomed = zoomAt(start, start.scale * ratio, from, base, max);
    return { scale: zoomed.scale, x: zoomed.x + to.x - from.x, y: zoomed.y + to.y - from.y };
  }
  function maxScale(natural, fitted) {
    if (!(natural > 0) || !(fitted > 0)) return MAX_LEAST;
    return Math.min(MAX_MOST, Math.max(MAX_LEAST, natural / fitted));
  }
  // The middle of what shows of the picture: a key zooms about it.
  function visibleCentre(state, base, frame) {
    const left = Math.max(frame.left, base.left + state.x);
    const right = Math.min(frame.left + frame.width, base.left + state.x + base.width * state.scale);
    const top = Math.max(frame.top, base.top + state.y);
    const bottom = Math.min(frame.top + frame.height, base.top + state.y + base.height * state.scale);
    return { x: (left + right) / 2, y: (top + bottom) / 2 };
  }

  const reduced = () => Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches);
  const spot = event => ({ x: event.clientX, y: event.clientY });
  const apart = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const middle = (a, b) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });

  // ---- A picture that zooms ----------------------------------------------------
  function attach(img, { frame = img?.parentElement, active } = {}) {
    if (!img || !frame) return null;
    let state = { ...FITTED };
    let settleTimer = 0;
    const pointers = new Map();
    let gesture = null;
    let press = null;
    let lastTap = null;
    let lastPointer = '';
    let safari = null;
    img.draggable = false;
    img.style.transformOrigin = '0 0';
    img.style.touchAction = 'none';

    // A running jump ends where it was going before anything is measured.
    function settle() {
      clearTimeout(settleTimer);
      img.classList.remove('is-settling');
      if (!(state.scale > 1)) frame.classList.remove('is-zoomed');
    }
    function measure() {
      settle();
      const box = img.getBoundingClientRect();
      const base = { left: box.left - state.x, top: box.top - state.y,
        width: box.width / state.scale, height: box.height / state.scale };
      const outer = frame.getBoundingClientRect();
      const room = { left: outer.left + frame.clientLeft, top: outer.top + frame.clientTop,
        width: frame.clientWidth || outer.width, height: frame.clientHeight || outer.height };
      return { base, frame: room, max: maxScale(img.naturalWidth, base.width) };
    }
    // The frame clips from the first zoomed frame on, and lets go only once
    // a jump back has ended (its scrollbars would flash in between).
    function apply(next, jump = false) {
      const animate = jump && !reduced();
      state = next;
      const zoomed = state.scale > 1;
      clearTimeout(settleTimer);
      if (zoomed) frame.classList.add('is-zoomed');
      else if (!animate) frame.classList.remove('is-zoomed');
      img.classList.toggle('is-settling', animate);
      img.style.transform = zoomed ? `translate(${state.x}px, ${state.y}px) scale(${state.scale})` : ''; // i18n-ignore
      if (animate) settleTimer = setTimeout(settle, SETTLE_MS);
    }
    function zoomTo(scale, at, jump) {
      const { base, frame: room, max } = measure();
      apply(clamp(zoomAt(state, scale, at || visibleCentre(state, base, room), base, max), base, room), jump);
    }
    function toggle(at) {
      if (state.scale > 1) { apply({ ...FITTED }, true); return; }
      const { max } = measure();
      zoomTo(Math.min(DOUBLE, max), at, true);
    }

    // Fingers, a pen, or the mouse holding a zoomed picture.
    function begin() {
      const held = [...pointers.values()];
      gesture = null;
      img.classList.remove('is-panning');
      if (held.length >= 2) {
        gesture = { kind: 'pinch', start: state, at: middle(held[0], held[1]), apart: apart(held[0], held[1]) || 1, ...measure() };
      } else if (held.length === 1 && state.scale > 1) {
        gesture = { kind: 'pan', start: state, at: held[0], ...measure() };
        img.classList.add('is-panning');
      }
    }
    function onDown(event) {
      if (event.pointerType === 'mouse' && (event.button !== 0 || !(state.scale > 1))) return;
      pointers.set(event.pointerId, spot(event));
      if (event.pointerType === 'mouse') event.preventDefault();
      try { img.setPointerCapture?.(event.pointerId); } catch (error) { /* a pointer already gone */ }
      press = pointers.size === 1 ? { id: event.pointerId, time: event.timeStamp, ...spot(event) } : null;
      begin();
    }
    function onMove(event) {
      if (!pointers.has(event.pointerId)) return;
      pointers.set(event.pointerId, spot(event));
      if (press?.id === event.pointerId && apart(press, spot(event)) > TAP_SLOP) press = null;
      if (!gesture) return;
      event.preventDefault();
      const held = [...pointers.values()];
      if (gesture.kind === 'pinch' && held.length >= 2) {
        const next = pinch(gesture.start, gesture.at, middle(held[0], held[1]),
          apart(held[0], held[1]) / gesture.apart, gesture.base, gesture.max);
        apply(clamp(next, gesture.base, gesture.frame));
      } else if (gesture.kind === 'pan') {
        const now = held[0];
        apply(clamp({ scale: gesture.start.scale, x: gesture.start.x + now.x - gesture.at.x,
          y: gesture.start.y + now.y - gesture.at.y }, gesture.base, gesture.frame));
      }
    }
    function onUp(event) {
      if (!pointers.has(event.pointerId)) return;
      pointers.delete(event.pointerId);
      // A double tap toggles where it lands; the mouse has dblclick.
      const tapped = event.type === 'pointerup' && event.pointerType !== 'mouse' && press?.id === event.pointerId
        && event.timeStamp - press.time < TAP_MS;
      press = null;
      if (tapped) {
        const here = spot(event);
        if (lastTap && event.timeStamp - lastTap.time < TAP_GAP && apart(lastTap, here) < TAP_NEAR) {
          lastTap = null;
          toggle(here);
        } else lastTap = { time: event.timeStamp, ...here };
      }
      // The finger left on the picture pans on from where it is.
      begin();
    }
    function onDoubleClick(event) {
      if (lastPointer && lastPointer !== 'mouse') return;
      event.preventDefault();
      toggle(spot(event));
    }
    function onPointerTyped(event) {
      lastPointer = event.pointerType;
    }

    function pixels(delta, event, page) {
      return delta * (event.deltaMode === 1 ? LINE : event.deltaMode === 2 ? page : 1);
    }
    function onWheel(event) {
      if (event.ctrlKey) {
        event.preventDefault();
        const { base, frame: room, max } = measure();
        const step = Math.max(-WHEEL_STEP, Math.min(WHEEL_STEP, pixels(event.deltaY, event, room.height)));
        apply(clamp(zoomAt(state, state.scale * Math.exp(-step * WHEEL_RATE), spot(event), base, max), base, room));
        return;
      }
      if (!(state.scale > 1)) return;
      event.preventDefault();
      const { base, frame: room } = measure();
      apply(clamp({ scale: state.scale, x: state.x - pixels(event.deltaX, event, room.width),
        y: state.y - pixels(event.deltaY, event, room.height) }, base, room));
    }
    // Safari's trackpad pinch. On a touch screen the same gesture also
    // comes as pointers, which zoom it already.
    function onGestureStart(event) {
      event.preventDefault();
      if (pointers.size) { safari = null; return; }
      const measured = measure();
      const at = Number.isFinite(event.clientX) ? spot(event) : visibleCentre(state, measured.base, measured.frame);
      safari = { start: state, at, ...measured };
    }
    function onGestureChange(event) {
      event.preventDefault();
      if (!safari || pointers.size) return;
      apply(clamp(zoomAt(safari.start, safari.start.scale * event.scale, safari.at, safari.base, safari.max),
        safari.base, safari.frame));
    }
    function onGestureEnd(event) {
      event.preventDefault();
      safari = null;
    }
    function onKey(event) {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
      if (!img.isConnected || (active && !active())) return;
      if (event.target?.closest?.('input, textarea, select, [contenteditable="true"]')) return; // i18n-ignore
      if (event.key === '+' || event.key === '=') zoomTo(state.scale * STEP, null, true);
      else if (event.key === '-') zoomTo(state.scale / STEP, null, true);
      else if (event.key === '0') apply({ ...FITTED }, state.scale > 1);
      else return;
      event.preventDefault();
    }
    // A new size of the window fits the picture again.
    function onResize() {
      if (state.scale > 1) apply({ ...FITTED });
    }

    const listeners = [
      [img, 'pointerdown', onDown], [img, 'pointermove', onMove], [img, 'pointerup', onUp],
      [img, 'pointercancel', onUp], [img, 'dblclick', onDoubleClick], [frame, 'pointerdown', onPointerTyped],
      [frame, 'wheel', onWheel, { passive: false }], [frame, 'gesturestart', onGestureStart, { passive: false }],
      [frame, 'gesturechange', onGestureChange, { passive: false }], [frame, 'gestureend', onGestureEnd, { passive: false }],
      [document, 'keydown', onKey], [window, 'resize', onResize],
    ];
    for (const [target, type, handler, options] of listeners) target.addEventListener(type, handler, options);
    return {
      zoomed: () => state.scale > 1,
      reset() { apply({ ...FITTED }); },
      detach() {
        for (const [target, type, handler, options] of listeners) target.removeEventListener(type, handler, options);
        clearTimeout(settleTimer);
        pointers.clear();
        frame.classList.remove('is-zoomed');
        img.classList.remove('is-panning', 'is-settling');
        img.style.transform = '';
      },
    };
  }

  App.imageZoom = { attach, clamp, zoomAt, pinch, maxScale, visibleCentre };
})();
