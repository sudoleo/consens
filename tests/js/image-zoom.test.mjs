import { describe, it, expect, vi } from 'vitest';
import { loadScripts } from './helpers/appWindow.mjs';

// A picture of 200 x 150 fitted in the middle of a frame of 400 x 300.
const BASE = { left: 100, top: 75, width: 200, height: 150 };
const FRAME = { left: 0, top: 0, width: 400, height: 300 };
const FITTED = { scale: 1, x: 0, y: 0 };

function boot({ reducedMotion = false, natural = 800 } = {}) {
  const ctx = loadScripts(['static/js/image-zoom.js'], { base: false,
    body: '<div id="frame"><img id="picture" alt="A chart"></div><input id="field">', before(window) {
      // jsdom has no matchMedia; the browser answers prefers-reduced-motion.
      window.matchMedia = query => ({ media: query, matches: reducedMotion && query.includes('reduce') });
    } });
  const { window, document } = ctx;
  const frame = document.getElementById('frame');
  const img = document.getElementById('picture');
  // jsdom lays nothing out: the boxes the browser would measure, the
  // picture's moved by its transform.
  frame.getBoundingClientRect = () => ({ ...FRAME });
  Object.defineProperty(frame, 'clientWidth', { value: FRAME.width });
  Object.defineProperty(frame, 'clientHeight', { value: FRAME.height });
  img.getBoundingClientRect = () => {
    const now = transformOf(img);
    return { left: BASE.left + now.x, top: BASE.top + now.y, width: BASE.width * now.scale, height: BASE.height * now.scale };
  };
  Object.defineProperty(img, 'naturalWidth', { value: natural });
  return { ...ctx, frame, img };
}
const NUMBER = '(-?\\d+(?:\\.\\d+)?(?:e-?\\d+)?)';
function transformOf(img) {
  const match = new RegExp(`translate\\(${NUMBER}px, ${NUMBER}px\\) scale\\(${NUMBER}\\)`).exec(img.style.transform);
  return match ? { x: Number(match[1]), y: Number(match[2]), scale: Number(match[3]) } : { ...FITTED };
}
function expectState(img, expected) {
  const now = transformOf(img);
  expect(now.scale).toBeCloseTo(expected.scale, 6);
  expect(now.x).toBeCloseTo(expected.x, 6);
  expect(now.y).toBeCloseTo(expected.y, 6);
}
// jsdom has no PointerEvent: a mouse event with the pointer's fields.
function pointer(window, type, { id = 1, x = 0, y = 0, kind = 'touch', primary = true, button = 0 } = {}) {
  const event = new window.MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y, button });
  Object.defineProperties(event, { pointerId: { value: id }, pointerType: { value: kind }, isPrimary: { value: primary } });
  return event;
}
function wheel(window, init) {
  return new window.WheelEvent('wheel', { bubbles: true, cancelable: true, clientX: 200, clientY: 150, ...init });
}
// Safari's GestureEvent: a plain event with its scale and point.
function gesture(window, type, fields = {}) {
  const event = new window.Event(type, { bubbles: true, cancelable: true });
  Object.defineProperties(event, Object.fromEntries(Object.entries({ scale: 1, clientX: 200, clientY: 150, ...fields })
    .map(([name, value]) => [name, { value }])));
  return event;
}
const key = (window, name, init = {}) => new window.KeyboardEvent('keydown', { key: name, bubbles: true, cancelable: true, ...init });

describe('zooming into a picture (image-zoom.js)', () => {
  it('keeps the point under the cursor, stays centred while smaller than its frame and leaves no gap once larger', () => {
    const { window } = boot();
    const { clamp, zoomAt, pinch, maxScale, visibleCentre } = window.App.imageZoom;
    // The corner under the cursor stays under it ...
    expect(zoomAt(FITTED, 3, { x: 100, y: 75 }, BASE)).toEqual({ scale: 3, x: 0, y: 0 });
    expect(zoomAt(FITTED, 2, { x: 150, y: 100 }, BASE)).toEqual({ scale: 2, x: -50, y: -25 });
    // ... until the picture would leave a gap at the frame's edge: 600 x 450
    // covers the frame from its top left corner, not from the cursor.
    expect(clamp({ scale: 3, x: 0, y: 0 }, BASE, FRAME)).toEqual({ scale: 3, x: -100, y: -75 });
    expect(clamp({ scale: 3, x: -500, y: -400 }, BASE, FRAME)).toEqual({ scale: 3, x: -300, y: -225 });
    // Smaller than the frame it stays centred where the fitted picture is.
    expect(clamp({ scale: 1.5, x: 40, y: -60 }, BASE, FRAME)).toEqual({ scale: 1.5, x: -50, y: -37.5 });
    // Never smaller than fitted, never further than the limit.
    expect(clamp({ scale: 0.6, x: 30, y: 30 }, BASE, FRAME)).toEqual(FITTED);
    expect(zoomAt(FITTED, 0.2, { x: 150, y: 100 }, BASE).scale).toBe(1);
    expect(zoomAt(FITTED, 20, { x: 150, y: 100 }, BASE, 5).scale).toBe(5);
    // Two fingers twice as far apart, the point between them moved 20 px right.
    expect(pinch(FITTED, { x: 200, y: 150 }, { x: 220, y: 150 }, 2, BASE, 4)).toEqual({ scale: 2, x: -80, y: -75 });
    // At least 4x, to the picture's own pixels, at most 8x.
    expect([maxScale(800, 200), maxScale(1000, 200), maxScale(4000, 200), maxScale(0, 200)]).toEqual([4, 5, 8, 4]);
    expect(visibleCentre(FITTED, BASE, FRAME)).toEqual({ x: 200, y: 150 });
    expect(visibleCentre({ scale: 3, x: -100, y: -75 }, BASE, FRAME)).toEqual({ x: 200, y: 150 });
  });

  it('zooms with Ctrl + wheel (a trackpad pinch) instead of the page, and pans only an enlarged picture', () => {
    const { window, frame, img } = boot();
    window.App.imageZoom.attach(img, { frame });
    const plain = wheel(window, { deltaY: 30 });
    img.dispatchEvent(plain);
    // Fitted, the wheel scrolls as ever.
    expect(plain.defaultPrevented).toBe(false);
    const pinch = wheel(window, { ctrlKey: true, deltaY: -10, clientX: 150, clientY: 100 });
    img.dispatchEvent(pinch);
    expect(pinch.defaultPrevented).toBe(true);
    const { clamp, zoomAt } = window.App.imageZoom;
    let expected = clamp(zoomAt(FITTED, Math.exp(0.1), { x: 150, y: 100 }, BASE), BASE, FRAME);
    expectState(img, expected);
    expect(frame.classList.contains('is-zoomed')).toBe(true);
    // A mouse wheel's notch is one step of about 1.5x, not 2.7x.
    for (let notch = 0; notch < 3; notch++) {
      img.dispatchEvent(wheel(window, { ctrlKey: true, deltaY: -100 }));
      expected = clamp(zoomAt(expected, expected.scale * Math.exp(0.4), { x: 200, y: 150 }, BASE), BASE, FRAME);
      expectState(img, expected);
    }
    expect(expected.scale).toBeCloseTo(Math.exp(1.3), 6);
    // Enlarged, a two-finger scroll moves the picture, within its bounds.
    const pan = wheel(window, { deltaX: 10, deltaY: 1000 });
    img.dispatchEvent(pan);
    expect(pan.defaultPrevented).toBe(true);
    expectState(img, clamp({ ...expected, x: expected.x - 10, y: -1000 }, BASE, FRAME));
    expect(transformOf(img).y).toBeCloseTo(FRAME.height - BASE.top - BASE.height * expected.scale, 6);
    // Out again: fitted, nothing clipped.
    for (let step = 0; step < 6; step++) img.dispatchEvent(wheel(window, { ctrlKey: true, deltaY: 100 }));
    expect(img.style.transform).toBe('');
    expect(frame.classList.contains('is-zoomed')).toBe(false);
  });

  it('toggles fitted and enlarged with a double click, animated, and zooms with + / - / 0', async () => {
    const { window, document, frame, img } = boot();
    let open = true;
    const zoom = window.App.imageZoom.attach(img, { frame, active: () => open });
    img.dispatchEvent(new window.MouseEvent('dblclick', { bubbles: true, cancelable: true, clientX: 150, clientY: 100 }));
    const { clamp, zoomAt } = window.App.imageZoom;
    expectState(img, clamp(zoomAt(FITTED, 2.5, { x: 150, y: 100 }, BASE), BASE, FRAME));
    expect(img.classList.contains('is-settling')).toBe(true);
    expect(zoom.zoomed()).toBe(true);
    img.dispatchEvent(new window.MouseEvent('dblclick', { bubbles: true, cancelable: true, clientX: 150, clientY: 100 }));
    expect(img.style.transform).toBe('');
    expect(zoom.zoomed()).toBe(false);
    // The frame clips until the way back has ended.
    expect(frame.classList.contains('is-zoomed')).toBe(true);
    await vi.waitFor(() => expect(frame.classList.contains('is-zoomed')).toBe(false));
    expect(img.classList.contains('is-settling')).toBe(false);

    const plus = key(window, '+');
    document.body.dispatchEvent(plus);
    expect(plus.defaultPrevented).toBe(true);
    expectState(img, clamp({ scale: 1.6, x: 0, y: 0 }, BASE, FRAME));
    document.body.dispatchEvent(key(window, '='));
    expect(transformOf(img).scale).toBeCloseTo(2.56, 6);
    document.body.dispatchEvent(key(window, '-'));
    expect(transformOf(img).scale).toBeCloseTo(1.6, 6);
    document.body.dispatchEvent(key(window, '0'));
    expect(img.style.transform).toBe('');
    // Ctrl + plus is the browser's zoom; a field keeps its keys; a closed
    // preview has none.
    const browser = key(window, '+', { ctrlKey: true });
    document.body.dispatchEvent(browser);
    expect(browser.defaultPrevented).toBe(false);
    document.getElementById('field').dispatchEvent(key(window, '+'));
    open = false;
    document.body.dispatchEvent(key(window, '+'));
    expect(img.style.transform).toBe('');
  });

  it('pinches with two fingers, pans with one, toggles with a double tap and takes the touches from the page', () => {
    const { window, frame, img } = boot();
    const zoom = window.App.imageZoom.attach(img, { frame });
    expect(img.style.touchAction).toBe('none');
    expect(img.style.transformOrigin).toBe('0 0');
    expect(img.draggable).toBe(false);
    const { clamp, pinch } = window.App.imageZoom;
    // 100 px apart, then 300: three times, the middle moved from 200 to 300.
    img.dispatchEvent(pointer(window, 'pointerdown', { id: 1, x: 150, y: 150 }));
    img.dispatchEvent(pointer(window, 'pointerdown', { id: 2, x: 250, y: 150, primary: false }));
    const move = pointer(window, 'pointermove', { id: 2, x: 450, y: 150, primary: false });
    img.dispatchEvent(move);
    expect(move.defaultPrevented).toBe(true);
    const pinched = clamp(pinch(FITTED, { x: 200, y: 150 }, { x: 300, y: 150 }, 3, BASE, 4), BASE, FRAME);
    expectState(img, pinched);
    expect(pinched.scale).toBe(3);
    // One finger lifts; the other pans on from where it is, without a jump.
    img.dispatchEvent(pointer(window, 'pointerup', { id: 2, x: 450, y: 150, primary: false }));
    expectState(img, pinched);
    img.dispatchEvent(pointer(window, 'pointermove', { id: 1, x: 120, y: 110 }));
    expectState(img, clamp({ scale: 3, x: pinched.x - 30, y: pinched.y - 40 }, BASE, FRAME));
    expect(img.classList.contains('is-panning')).toBe(true);
    img.dispatchEvent(pointer(window, 'pointerup', { id: 1, x: 120, y: 110 }));
    expect(img.classList.contains('is-panning')).toBe(false);
    // A double tap back to fitted, and in again where it lands.
    for (let tap = 0; tap < 2; tap++) {
      img.dispatchEvent(pointer(window, 'pointerdown', { id: 3 + tap, x: 160, y: 120 }));
      img.dispatchEvent(pointer(window, 'pointerup', { id: 3 + tap, x: 162, y: 121 }));
    }
    expect(zoom.zoomed()).toBe(false);
    for (let tap = 0; tap < 2; tap++) {
      img.dispatchEvent(pointer(window, 'pointerdown', { id: 5 + tap, x: 150, y: 100 }));
      img.dispatchEvent(pointer(window, 'pointerup', { id: 5 + tap, x: 150, y: 100 }));
    }
    expect(transformOf(img).scale).toBe(2.5);
    // The browser's dblclick after the taps toggles nothing more.
    img.dispatchEvent(new window.MouseEvent('dblclick', { bubbles: true, cancelable: true, clientX: 150, clientY: 100 }));
    expect(transformOf(img).scale).toBe(2.5);
    // A mouse holds and drags an enlarged picture; a fitted one it leaves alone.
    const grab = pointer(window, 'pointerdown', { id: 20, kind: 'mouse', x: 200, y: 150 });
    img.dispatchEvent(grab);
    expect(grab.defaultPrevented).toBe(true);
    img.dispatchEvent(pointer(window, 'pointerup', { id: 20, kind: 'mouse', x: 200, y: 150 }));
    zoom.reset();
    const click = pointer(window, 'pointerdown', { id: 21, kind: 'mouse', x: 200, y: 150 });
    img.dispatchEvent(click);
    expect(click.defaultPrevented).toBe(false);
  });

  it("zooms with Safari's trackpad gestures and always keeps the page from zooming", () => {
    const { window, frame, img } = boot();
    window.App.imageZoom.attach(img, { frame });
    const start = gesture(window, 'gesturestart', { clientX: 150, clientY: 100 });
    img.dispatchEvent(start);
    expect(start.defaultPrevented).toBe(true);
    img.dispatchEvent(gesture(window, 'gesturechange', { scale: 2, clientX: 150, clientY: 100 }));
    const { clamp, zoomAt } = window.App.imageZoom;
    expectState(img, clamp(zoomAt(FITTED, 2, { x: 150, y: 100 }, BASE), BASE, FRAME));
    const end = gesture(window, 'gestureend', { scale: 2 });
    img.dispatchEvent(end);
    expect(end.defaultPrevented).toBe(true);
    // On a touch screen the fingers zoom it already: the gesture adds nothing.
    img.dispatchEvent(pointer(window, 'pointerdown', { id: 1, x: 200, y: 150 }));
    const touch = gesture(window, 'gesturestart');
    img.dispatchEvent(touch);
    img.dispatchEvent(gesture(window, 'gesturechange', { scale: 3 }));
    expect(touch.defaultPrevented).toBe(true);
    expect(transformOf(img).scale).toBe(2);
  });

  it('jumps without animating for reduced motion, fits again on resize and lets go when detached', () => {
    const { window, frame, img } = boot({ reducedMotion: true });
    const zoom = window.App.imageZoom.attach(img, { frame });
    img.dispatchEvent(new window.MouseEvent('dblclick', { bubbles: true, cancelable: true, clientX: 200, clientY: 150 }));
    expect(zoom.zoomed()).toBe(true);
    expect(img.classList.contains('is-settling')).toBe(false);
    img.dispatchEvent(new window.MouseEvent('dblclick', { bubbles: true, cancelable: true, clientX: 200, clientY: 150 }));
    // No way back to wait for: the frame lets go at once.
    expect(frame.classList.contains('is-zoomed')).toBe(false);
    img.dispatchEvent(new window.MouseEvent('dblclick', { bubbles: true, cancelable: true, clientX: 200, clientY: 150 }));
    window.dispatchEvent(new window.Event('resize'));
    expect(img.style.transform).toBe('');
    expect(frame.classList.contains('is-zoomed')).toBe(false);
    img.dispatchEvent(new window.MouseEvent('dblclick', { bubbles: true, cancelable: true, clientX: 200, clientY: 150 }));
    zoom.detach();
    expect(img.style.transform).toBe('');
    expect(frame.classList.contains('is-zoomed')).toBe(false);
    const after = wheel(window, { ctrlKey: true, deltaY: -40 });
    img.dispatchEvent(after);
    expect(after.defaultPrevented).toBe(false);
  });
});
