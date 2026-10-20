/**
 * Buchstabenwolken im leeren Startbildschirm (body.is-hero).
 *
 * Rund um Begrüßung und Composer ziehen langsam Wolken aus Zeichen vorbei;
 * ein Klick auf eine freie Stelle schickt eine unregelmäßige Welle durch.
 * Mit der ersten Frage, einem geöffneten Chat oder der Watch-Seite blendet
 * die Ebene aus und die Schleife hält ganz an: im Chat kostet sie nichts.
 *
 * Sparsam gebaut: unten ein Raster aus Zeichen in voller Gerätedichte (bis
 * 3x), das fast nie neu gemalt wird,
 * darüber ein winziger Nebel-Canvas in Seitenfarbe (ein Punkt je 10 px), den
 * der Browser weich hochskaliert. Pro Bild ändert sich nur der Nebel. Ruhig
 * 10 Bilder/s, zwischen denen der Tab schläft; nur während einer Welle im
 * vollen Bildtakt; ein verdeckter Tab rechnet gar nicht. Reduzierte Bewegung
 * zeigt ruhende Wolken ohne Welle.
 *
 * Öffentlich: window.App.letterClouds { state(), splash(x, y) }.
 */
(function () {
  "use strict";

  window.App = window.App || {};

  const CH = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHJKLMNPQRSTUVWXYZ";
  const NCH = CH.length;
  const GLYPH_A = 0.26;   // Deckkraft eines voll freigelegten Zeichens
  const PEAK = 0.62;      // dichteste Wolke legt so viel davon frei
  const FOG = 10;         // CSS-Pixel je Nebelpunkt
  // Die Wolken ziehen nur ein paar Pixel pro Sekunde: 10 Bilder/s sehen wie
  // fließend aus und kosten ein Drittel weniger als 15.
  const IDLE_MS = 1000 / 10;
  const FLICKER = 0.018;  // Anteil der Zeichen, die pro Sekunde wechseln
  const FADE_IN = 7;      // Sekunden, bis die Wolken ganz da sind
  const MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";
  // Klicks auf Bedienelemente und Flächen mit eigener Aufgabe lösen keine Welle aus.
  const SKIP = [
    "a", "button", "input", "textarea", "select", "label", "summary",
    "[role='button']", "[role='menu']", "[role='dialog']", "[contenteditable='true']",
    "dialog", ".modal", ".input-section", ".sidebar", ".app-nav-float",
    ".view-switch", ".app-mobile-header"
  ].join(",");

  const body = document.body;
  // Ohne matchMedia lässt sich „reduzierte Bewegung“ nicht respektieren:
  // dann lieber gar keine Animation (betrifft auch jsdom in den Tests).
  if (!body || !window.matchMedia) {
    window.App.letterClouds = {
      state: () => ({ supported: false, active: false, running: false, ripples: 0 }),
      splash: () => false
    };
    return;
  }

  const reduceQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");
  const reduced = () => !!reduceQuery.matches;
  const now = () => performance.now() / 1000;
  const ss = v => { v = v < 0 ? 0 : v > 1 ? 1 : v; return v * v * (3 - 2 * v); };
  const rnd = (a, b) => a + Math.random() * (b - a);

  const layer = document.createElement("div");
  layer.className = "letter-clouds is-off";
  layer.setAttribute("aria-hidden", "true");
  const gc = document.createElement("canvas");
  gc.className = "letter-clouds-glyphs";
  const fc = document.createElement("canvas");
  fc.className = "letter-clouds-fog";
  layer.append(gc, fc);
  body.prepend(layer);

  const g = gc.getContext("2d");
  const f = fc.getContext("2d");
  const supported = !!(g && f);

  let dpr = 1, cw = 7, rh = 13, W = 0, H = 0, cols = 0, rows = 0;
  let chars = null, fw = 0, fh = 0, img = null, cvis = null, atlas = null;
  let noise = null, theme = "", calm = null, calmAt = -1e9;
  let active = false, raf = 0, timer = 0, lastCloud = -1e9, born = now(), stale = false;
  const rip = [];

  // Kachelbares Wertrauschen, beim ersten Start einmal berechnet und auf
  // Mittelwert 0 / Streuung 1 gebracht, damit jeder Aufruf ähnlich viel bedeckt.
  const NS = 128;
  const OFF = NS * 64;    // hält Abtastkoordinaten positiv, siehe sample()
  function buildNoise() {
    noise = new Float32Array(NS * NS);
    for (const [p, w] of [[32, 0.5], [16, 0.3], [8, 0.2]]) {
      const n = NS / p, lat = new Float32Array(n * n);
      for (let i = 0; i < lat.length; i++) lat[i] = Math.random();
      for (let y = 0; y < NS; y++) for (let x = 0; x < NS; x++) {
        const gx = x / p, gy = y / p, x0 = Math.floor(gx), y0 = Math.floor(gy);
        const sx = ss(gx - x0), sy = ss(gy - y0), x1 = (x0 + 1) % n, y1 = (y0 + 1) % n;
        const a = lat[y0 * n + x0], b = lat[y0 * n + x1], c = lat[y1 * n + x0], d = lat[y1 * n + x1];
        const top = a + (b - a) * sx;
        noise[y * NS + x] += w * (top + ((c + (d - c) * sx) - top) * sy);
      }
    }
    let m = 0, v = 0;
    for (const x of noise) m += x;
    m /= noise.length;
    for (const x of noise) v += (x - m) * (x - m);
    const sd = Math.sqrt(v / noise.length) || 1;
    for (let i = 0; i < noise.length; i++) noise[i] = (noise[i] - m) / sd;
  }
  // u, v sind positiv (Aufrufer verschieben um OFF): dann kacheln Bitmasken,
  // statt pro Abtastung zweimal die langsame Gleitkomma-Division % zu rechnen.
  function sample(u, v) {
    const ui = u | 0, vi = v | 0, fx = u - ui, fy = v - vi;
    const x0 = ui & (NS - 1), x1 = (ui + 1) & (NS - 1);
    const y0 = (vi & (NS - 1)) * NS, y1 = ((vi + 1) & (NS - 1)) * NS;
    const a = noise[y0 + x0], b = noise[y0 + x1], c = noise[y1 + x0], d = noise[y1 + x1];
    const top = a + (b - a) * fx;
    return top + ((c + (d - c) * fx) - top) * fy;
  }

  // Seitenfarbe und Tinte so, wie sie gerade gerendert werden (hell, dunkel, System).
  function readTheme() {
    const cs = getComputedStyle(body);
    let bg = cs.backgroundColor;
    if (!bg || bg === "transparent" || /rgba\(.*,\s*0\)$/.test(bg)) bg = getComputedStyle(document.documentElement).backgroundColor;
    return { bg: bg || "rgb(250, 250, 250)", ink: cs.getPropertyValue("--ink").trim() || cs.color || "#222428" };
  }
  function rgbOf(color) {
    f.fillStyle = "#000";
    f.fillStyle = color;
    const v = String(f.fillStyle);
    if (v[0] === "#") return [1, 3, 5].map(i => parseInt(v.slice(i, i + 2), 16));
    const m = v.match(/[\d.]+/g) || [0, 0, 0];
    return [+m[0], +m[1], +m[2]];
  }

  function drawCell(k) {
    const i = k % cols, j = (k / cols) | 0;
    g.clearRect(i * cw, j * rh, cw, rh);
    g.drawImage(atlas, chars[k] * cw, 0, cw, rh, i * cw, j * rh, cw, rh);
  }
  function paintAll() {
    const tk = readTheme();
    theme = tk.bg + "|" + tk.ink;
    atlas = document.createElement("canvas");
    atlas.width = NCH * cw;
    atlas.height = rh;
    const a = atlas.getContext("2d");
    a.font = "500 " + Math.round(11 * dpr) + "px " + MONO;
    a.textBaseline = "middle";
    a.textAlign = "center";
    a.fillStyle = tk.ink;
    for (let i = 0; i < NCH; i++) a.fillText(CH[i], i * cw + cw / 2, rh / 2);
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.clearRect(0, 0, gc.width, gc.height);
    g.globalAlpha = GLYPH_A;
    for (let k = 0; k < chars.length; k++) drawCell(k);
    const [r, gr, b] = rgbOf(tk.bg);
    const d = img.data;
    for (let p = 0; p < d.length; p += 4) { d[p] = r; d[p + 1] = gr; d[p + 2] = b; d[p + 3] = 255; }
    f.putImageData(img, 0, 0);
  }
  // Ein neues Format behält die Zeichen, die schon dastehen: Öffnet sich die
  // Android-Tastatur oder dreht sich das Gerät, würfelten sonst alle Zeichen
  // auf einmal neu (Apple-Audit D11). Nur hinzugekommene Zellen sind neu.
  function resize() {
    stale = false;
    // Die Zeichen werden in voller Gerätedichte gemalt (bis 3x): auf dem
    // iPhone waren sie mit 2x um das 1,5-Fache hochskaliert und weicher als
    // der Text davor (Apple-Audit G16). Das Raster wird fast nie neu gemalt,
    // der Nebel bleibt grob (FOG, unabhängig von der Dichte).
    dpr = Math.min(window.devicePixelRatio || 1, 3);
    cw = Math.round(7.2 * dpr);
    rh = Math.round(13 * dpr);
    W = layer.clientWidth || window.innerWidth;
    H = layer.clientHeight || window.innerHeight;
    gc.width = Math.round(W * dpr);
    gc.height = Math.round(H * dpr);
    const kept = chars, keptCols = cols;
    cols = Math.ceil(gc.width / cw);
    rows = Math.ceil(gc.height / rh);
    chars = new Uint8Array(cols * rows);
    for (let k = 0; k < chars.length; k++) {
      const i = k % cols, old = ((k / cols) | 0) * keptCols + i;
      chars[k] = kept && i < keptCols && old < kept.length ? kept[old] : (Math.random() * NCH) | 0;
    }
    fw = Math.ceil(W / FOG) + 1;
    fh = Math.ceil(H / FOG) + 1;
    fc.width = fw;
    fc.height = fh;
    fc.style.width = fw * FOG + "px";
    fc.style.height = fh * FOG + "px";
    img = f.createImageData(fw, fh);
    cvis = new Float32Array(fw * fh);
    calmAt = -1e9;
    lastCloud = -1e9;
    paintAll();
  }

  // Begrüßung, Composer und Hinweiszeile bleiben lesbar: um den Eingabeblock
  // herum lichten sich die Wolken.
  function measureCalm(t) {
    if (t - calmAt < 1) return;
    calmAt = t;
    const el = document.querySelector(".input-section");
    const r = el && el.getBoundingClientRect();
    calm = r && r.width > 0 && r.height > 0
      ? { x0: r.left - 40, x1: r.right + 40, y0: r.top - 36, y1: r.bottom + 36 }
      : null;
  }

  function clouds(t) {
    const still = reduced();
    const tt = still ? born : t;
    const fade = still ? 1 : ss((t - born) / FADE_IN);
    const wrap = x => OFF + x % NS;
    const ax = wrap(tt * 0.55), ay = wrap(tt * 0.1), bx = wrap(37.3 - tt * 0.27), by = wrap(11.9 + tt * 0.32);
    // Gedrehte Abtastung, sonst zeichnet das Gitter des Rauschens gerade Kanten.
    const c1 = 0.866 / 12, s1 = 0.5 / 12, c2 = 0.643 / 8, s2 = -0.766 / 8;
    measureCalm(t);
    for (let j = 0, q = 0; j < fh; j++) {
      const py = (j + 0.5) * FOG;
      const cy = calm ? Math.max(calm.y0 - py, 0, py - calm.y1) : 0;
      for (let i = 0; i < fw; i++, q++) {
        const px = (i + 0.5) * FOG;
        const n = 0.62 * sample(px * c1 - py * s1 + ax, px * s1 + py * c1 + ay)
          + 0.38 * sample(px * c2 - py * s2 + bx, px * s2 + py * c2 + by);
        let vis = ss((n - 0.55) / 0.6) * PEAK * fade;
        if (calm && vis > 0) {
          const cx = Math.max(calm.x0 - px, 0, px - calm.x1);
          vis *= 0.12 + 0.88 * ss(Math.sqrt(cx * cx + cy * cy) / 70);
        }
        cvis[q] = vis;
      }
    }
    if (!still) {
      const n = Math.max(1, (chars.length * FLICKER * IDLE_MS / 1000) | 0);
      for (let s = 0; s < n; s++) {
        const k = (Math.random() * chars.length) | 0;
        chars[k] = (Math.random() * NCH) | 0;
        drawCell(k);
      }
    }
  }

  // Eine Welle ist nie ein sauberer Kreis: Radius und Breite schwanken je
  // Richtung, sie bremst ab, zerfällt in Flecken und zieht Nachläufer hinter sich her.
  function addRipple(x, y, t, a) {
    rip.push({
      x, y, t, a, speed: rnd(170, 250), life: rnd(1.8, 2.5), sf: Math.random(),
      p: [rnd(0, 6.28), rnd(0, 6.28), rnd(0, 6.28)],
      h: [2 + ((Math.random() * 3) | 0), 5 + ((Math.random() * 4) | 0)]
    });
  }
  function splash(x, y) {
    if (!active || !supported || reduced()) return false;
    const t = now();
    addRipple(x, y, t, 0.7);
    const echoes = 1 + ((Math.random() * 2) | 0);
    for (let e = 0; e < echoes; e++) {
      const an = rnd(0, 6.28), d = rnd(15, 60);
      addRipple(x + Math.cos(an) * d, y + Math.sin(an) * d, t + rnd(0.12, 0.5), rnd(0.25, 0.4));
    }
    while (rip.length > 6) rip.shift();
    wake();
    return true;
  }

  function frame(t, doClouds) {
    for (let k = rip.length - 1; k >= 0; k--) if (t - rip[k].t > rip[k].life) rip.splice(k, 1);
    if (doClouds) clouds(t);
    const act = [];
    for (const r of rip) {
      const age = t - r.t;
      if (age <= 0) continue;
      // Radius 0.76–1.24 R0, Breite höchstens 36, |z| <= 3: außerhalb dieses
      // Rings trägt kein Punkt bei, die engere Grenze spart nur Rechnung.
      const R0 = r.speed * Math.pow(age, 0.78);
      const lo = Math.max(0, R0 * 0.6 - 60, R0 * 0.76 - 109), hi = Math.min(R0 * 1.35 + 60, R0 * 1.24 + 109);
      const p1 = r.p[1] + age * 1.7, p2 = r.p[2] + age;
      act.push({
        x: r.x, y: r.y, R0, lo2: lo * lo, hi, hi2: hi * hi, fade: Math.pow(1 - age / r.life, 1.5) * r.a,
        h0: r.h[0], h1: r.h[1], sf: r.sf,
        c0: Math.cos(r.p[0]), s0: Math.sin(r.p[0]), c1: Math.cos(p1), s1: Math.sin(p1), c2: Math.cos(p2), s2: Math.sin(p2)
      });
    }
    const d = img.data, rowAct = [];
    for (let j = 0, p = 3, q = 0; j < fh; j++) {
      const py = (j + 0.5) * FOG;
      rowAct.length = 0;
      for (const r of act) if (Math.abs(py - r.y) < r.hi) rowAct.push(r);
      const nr = rowAct.length;
      if (!nr) {
        for (let i = 0; i < fw; i++, p += 4, q++) d[p] = 255 - ((cvis[q] * 255) | 0);
        continue;
      }
      const cj = ((py * dpr / rh) | 0) * cols;
      for (let i = 0; i < fw; i++, p += 4, q++) {
        const px = (i + 0.5) * FOG;
        let a = 0;
        for (let s = 0; s < nr; s++) {
          const r = rowAct[s], dx = px - r.x;
          if (dx > r.hi || dx < -r.hi) continue;
          const dy = py - r.y, d2 = dx * dx + dy * dy;
          if (d2 < r.lo2 || d2 > r.hi2) continue;
          // sin(k·θ + p) ohne atan2 und Math.sin: cos/sin von θ aus dx, dy,
          // Vielfache per Tschebyschow-Rekursion, die Phase per Additionstheorem.
          const dd = Math.sqrt(d2), c = dd > 0 ? dx / dd : 1, sn = dd > 0 ? dy / dd : 0;
          let ck = c * c - sn * sn, sk = 2 * c * sn, cp = c, sp = sn, ca = ck, sa = sk;
          const cos2 = ck, sin2 = sk;
          for (let k = 3; k <= r.h1; k++) {
            const cn = 2 * c * ck - cp, snk = 2 * c * sk - sp;
            cp = ck; sp = sk; ck = cn; sk = snk;
            if (k === r.h0) { ca = ck; sa = sk; }
          }
          const R = r.R0 * (1 + 0.16 * (sa * r.c0 + ca * r.s0) + 0.08 * (sk * r.c1 + ck * r.s1));
          const z = (dd - R) / (24 * (1 + 0.5 * (sin2 * r.c2 + cos2 * r.s2)));
          if (z > 3 || z < -3) continue;
          let gq = Math.exp(-z * z) * r.fade, h = q * 0.6180339 + r.sf;
          h -= Math.floor(h);
          if (h > gq * 1.6) gq *= 0.25;
          a += gq;
        }
        let vis = cvis[q];
        if (a > 0) {
          if (a > 1) a = 1;
          vis += a * (1 - vis);
          // Unter der Wellenfront springen einzelne Zeichen um.
          if (a > 0.5 && Math.random() < 0.05) {
            const ci = (px * dpr / cw) | 0, k = cj + ci;
            if (ci < cols && k < chars.length) { chars[k] = (Math.random() * NCH) | 0; drawCell(k); }
          }
        }
        d[p] = 255 - ((vis * 255) | 0);
      }
    }
    f.putImageData(img, 0, 0);
  }

  // Während einer Welle läuft jedes Bild. Ruhig weckt ein Timer erst das
  // nächste fällige Bild: der Tab schläft dazwischen, statt bei jedem
  // Bildschirmtakt aufzuwachen und gleich wieder aufzugeben. Fällig misst die
  // Uhr, nicht ts: ts ist der Beginn des Bildtakts und kann vor dem Timer liegen.
  function loop(ts) {
    raf = 0;
    if (!active || document.hidden) return;
    const at = performance.now(), due = at - lastCloud >= IDLE_MS - 12;
    if (rip.length || due) {
      if (due) lastCloud = at;
      frame(ts / 1000, due);
    }
    if (rip.length) raf = window.requestAnimationFrame(loop);
    else if (!reduced()) timer = setTimeout(wake, lastCloud + IDLE_MS - 8 - performance.now());
  }
  function wake() {
    if (timer) { clearTimeout(timer); timer = 0; }
    if (!raf && active && supported && !document.hidden) raf = window.requestAnimationFrame(loop);
  }

  function wanted() {
    if (!body.classList.contains("is-hero")) return false;
    return !document.querySelector(".watch-page:not([hidden])");
  }
  function themeCheck() {
    if (!active || !img) return;
    const tk = readTheme();
    if (tk.bg + "|" + tk.ink !== theme) { paintAll(); lastCloud = -1e9; wake(); }
  }
  function sync() {
    if (!supported) return;
    const want = wanted();
    if (want && !active) {
      active = true;
      born = now();
      if (!noise) buildNoise();
      if (!img || stale) resize(); else paintAll();
      lastCloud = -1e9;
      layer.classList.remove("is-off");
      wake();
    } else if (!want && active) {
      active = false;
      rip.length = 0;
      layer.classList.add("is-off");
      if (raf) { window.cancelAnimationFrame(raf); raf = 0; }
      if (timer) { clearTimeout(timer); timer = 0; }
    } else if (want) {
      themeCheck();
    }
  }

  // Hinter einem Chat bleibt die Ebene unsichtbar liegen. Sobald sie
  // ausgeblendet ist, gibt sie ihre Leinwände frei (bei DPR 2 rund 30 MB),
  // statt sie für den nächsten leeren Startbildschirm aufzuheben; der baut
  // ohnehin neu auf und blendet ein (Apple-Audit D11).
  function release() {
    if (active || !img) return;
    gc.width = gc.height = 0;
    fc.width = fc.height = 0;
    img = cvis = chars = atlas = null;
    cols = rows = 0;
  }

  if (supported) {
    new MutationObserver(sync).observe(body, { attributes: true, attributeFilter: ["class"] });
    layer.addEventListener("transitionend", event => {
      if (event.target === layer && event.propertyName === "opacity") release();
    });
    const watchPage = document.querySelector(".watch-page");
    if (watchPage) new MutationObserver(sync).observe(watchPage, { attributes: true, attributeFilter: ["hidden"] });
    darkQuery?.addEventListener?.("change", themeCheck);
    reduceQuery?.addEventListener?.("change", () => { lastCloud = -1e9; wake(); });
    document.addEventListener("visibilitychange", wake);
    let resizeTimer = 0;
    // Hinter einem Chat malt die Ebene bei einer Größenänderung nichts neu;
    // sie misst beim nächsten Start neu.
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      if (!active) { stale = true; return; }
      resizeTimer = setTimeout(() => {
        if (!img) return;
        if (active) { resize(); wake(); } else stale = true;
      }, 150);
    }, { passive: true });
    document.addEventListener("pointerdown", event => {
      if (!active || event.button !== 0) return;
      const target = event.target;
      if (target && target.closest && target.closest(SKIP)) return;
      splash(event.clientX, event.clientY);
    }, { passive: true });
    sync();
  } else {
    layer.remove();
  }

  window.App.letterClouds = {
    state: () => ({ supported, active, running: !!(raf || timer), ripples: rip.length }),
    splash
  };
})();
