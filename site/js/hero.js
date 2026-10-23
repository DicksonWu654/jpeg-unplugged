/* hero.js - the plug, and one dot per collection that goes dark when the plug is pulled. */
(function () {
  "use strict";
  var JU = window.JU;

  /* ---------------- plug animation ---------------- */
  var plugT = 0, plugRaf = 0;
  function drawPlug(t) {
    var body = JU.$("#plug-body"), cable = JU.$("#cable");
    if (!body || !cable) return;
    var dx = -128 * t;
    body.setAttribute("transform", "translate(" + dx.toFixed(1) + " 0)");
    var ex = 228 + dx;
    var sag = 70 * t;
    cable.setAttribute("d", "M-10 75 C 70 " + (75 + sag).toFixed(1) + " " + (ex - 80).toFixed(1) + " " + (75 - 38 * t).toFixed(1) + " " + ex.toFixed(1) + " 75");
  }
  function ease(x) { return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; }
  function animatePlug(to) {
    cancelAnimationFrame(plugRaf);
    if (JU.reduceMotion()) { plugT = to; drawPlug(to); return; }
    var from = plugT, t0 = performance.now(), dur = to > from ? 520 : 760;
    (function step(now) {
      var k = Math.min(1, (now - t0) / dur);
      plugT = from + (to - from) * ease(k);
      drawPlug(plugT);
      if (k < 1) plugRaf = requestAnimationFrame(step);
    })(t0);
    if (to > from) {
      var sp = JU.$("#sparks");
      if (sp) { sp.classList.remove("go"); void sp.getBoundingClientRect(); sp.classList.add("go"); }
    }
  }

  /* ---------------- numbers for the headline figure ---------------- */
  function numbers() {
    var c = JU.data.census, rows = JU.data.collections && JU.data.collections.collections;
    var n = {};
    if (c && c.totals && c.liveness && c.survival) {
      n.total = c.totals.collections; n.live = c.liveness; n.surv = c.survival;
    } else if (rows) {
      n.total = rows.length; n.live = {}; n.surv = {};
      rows.forEach(function (r) { n.live[r.liveness] = (n.live[r.liveness] || 0) + 1; n.surv[r.survives_unplugged] = (n.surv[r.survives_unplugged] || 0) + 1; });
    } else return null;
    return n;
  }

  var shown = null, countRaf = 0;
  function setFigure(val, ofText, subHtml) {
    var el = JU.$("#figure-n");
    JU.$("#figure-of").textContent = ofText;
    JU.$("#figure-sub").innerHTML = subHtml;
    cancelAnimationFrame(countRaf);
    if (shown === null || JU.reduceMotion()) { shown = val; el.textContent = JU.fmt(val); return; }
    var from = shown, t0 = performance.now(), dur = 900;
    (function step(now) {
      var k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      shown = Math.round(from + (val - from) * e);
      el.textContent = JU.fmt(shown);
      if (k < 1) countRaf = requestAnimationFrame(step);
    })(t0);
  }
  function updateFigure() {
    var n = numbers();
    if (!n) { JU.$("#figure-n").textContent = "-"; JU.$("#figure-of").textContent = "No census data loaded."; return; }
    var on = JU.state.power === "on", T = n.total, si = JU.sampleInfo();
    var headline = JU.data.headlines && JU.data.headlines.random.onchain.truly_onchain_census;
    var candidates = headline ? headline.k : n.surv.yes || 0;
    JU.$("#hero-answer").textContent = JU.pct(candidates, T, 1) + " fully on-chain candidates. Only the gallery is render-tested.";
    setFigure(candidates, "of " + JU.fmt(T) + " collections", on
      ? "have metadata and sampled media fully on-chain."
      : "candidate collections stay lit. What about the art? ↓");

  }

  /* ---------------- dot field ---------------- */
  var HERO_COLOR = { "data-uri": "#c5ff41", "onchain-renderer": "#67d9ee", arweave: "#ffcb47", ipfs: "#aa8aff", http: "#ff71ad", broken: "#868b95", unresolved: "#a89a78", other: "#59606a" };
  var OFF = [34, 40, 47];
  function hex(c) { return [parseInt(c.slice(1, 3), 16), parseInt(c.slice(3, 5), 16), parseInt(c.slice(5, 7), 16)]; }
  var canvas, ctx, dots = [], cols = 1, cell = 8, W = 0, H = 0, dpr = 1, running = false, lastT = 0;

  function paramsFor(row, power) {
    if (power === "on") {
      switch (row.liveness) {
        case "alive": return { fill: 1, ring: 0, size: 1, mix: 0, glow: 0 };
        case "degraded": return { fill: 0.5, ring: 1, size: 1, mix: 0, glow: 0 };
        case "dead": return { fill: 0, ring: 1, size: 0.92, mix: 0.1, glow: 0 };
        default: return { fill: 0.32, ring: 0, size: 0.9, mix: 0.3, glow: 0 };
      }
    }
    switch (row.survives_unplugged) {
      case "yes": return { fill: 1, ring: 0, size: 1.08, mix: 0, glow: 1 };
      case "partial": return { fill: 0.3, ring: 1, size: 1, mix: 0, glow: 0 };
      case "unknown": return { fill: 0.1, ring: 0.5, size: 0.7, mix: 0.7, glow: 0 };
      default: return { fill: 0.55, ring: 0, size: 0.5, mix: 0.97, glow: 0 };
    }
  }
  var ORDER = { yes: 0, partial: 1, unknown: 2, no: 3 };
  var LOCI = {}; JU.LOC.forEach(function (l, i) { LOCI[l.key] = i; });

  function layout() {
    var wrap = canvas.parentNode;
    W = Math.max(240, wrap.clientWidth);
    var N = dots.length || 1, target = window.innerWidth < 880 ? 128 : 292;
    var s = 14;
    for (; s > 3; s--) { var c = Math.floor(W / s); if (Math.ceil(N / c) * s <= target) break; }
    cell = s; cols = Math.max(1, Math.floor(W / s));
    var rows = Math.ceil(N / cols);
    H = rows * cell + 4;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    canvas.style.height = H + "px";
    var xOff = (W - cols * cell) / 2;
    dots.forEach(function (d, i) { d.x = xOff + (i % cols) * cell + cell / 2; d.y = Math.floor(i / cols) * cell + cell / 2 + 2; d.delay = (d.x / W) * 520 + Math.random() * 380; });
  }

  function draw() {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    var rad = cell * 0.5 - Math.max(0.6, cell * 0.1);
    for (var i = 0; i < dots.length; i++) {
      var d = dots[i], p = d.cur;
      var r = rad * p.size;
      var rgb = [0, 1, 2].map(function (k) { return Math.round(d.rgb[k] * (1 - p.mix) + OFF[k] * p.mix); });
      var col = "rgb(" + rgb[0] + "," + rgb[1] + "," + rgb[2] + ")";
      if (p.glow > 0.02) {
        ctx.fillStyle = "rgba(" + rgb[0] + "," + rgb[1] + "," + rgb[2] + "," + (0.22 * p.glow).toFixed(3) + ")";
        ctx.fillRect(d.x - r * 1.4, d.y - r * 1.4, r * 2.8, r * 2.8);
      }
      if (p.fill > 0.02) { ctx.globalAlpha = p.fill; ctx.fillStyle = col; ctx.fillRect(Math.round(d.x - r), Math.round(d.y - r), Math.round(r * 2), Math.round(r * 2)); ctx.globalAlpha = 1; }
      if (p.ring > 0.02) { ctx.globalAlpha = p.ring; ctx.strokeStyle = col; ctx.lineWidth = Math.max(1, cell * 0.12); ctx.strokeRect(Math.round(d.x - r) + 0.5, Math.round(d.y - r) + 0.5, Math.round(r * 2) - 1, Math.round(r * 2) - 1); ctx.globalAlpha = 1; }
    }
  }
  function step(now) {
    var dt = Math.min(48, now - lastT); lastT = now;
    var moving = false, k = 1 - Math.pow(0.0009, dt / 1000);
    for (var i = 0; i < dots.length; i++) {
      var d = dots[i];
      if (now < d.start) { moving = true; continue; }
      var c = d.cur, t = d.tgt, diff = 0;
      for (var key in t) { var dd = t[key] - c[key]; c[key] += dd * k; diff += Math.abs(dd); }
      if (diff > 0.004) moving = true; else for (var key2 in t) c[key2] = t[key2];
    }
    draw();
    if (moving) requestAnimationFrame(step); else running = false;
  }
  function kick() { if (!running) { running = true; lastT = performance.now(); requestAnimationFrame(step); } }

  function retarget(animate) {
    var now = performance.now();
    dots.forEach(function (d) {
      d.tgt = paramsFor(d.row, JU.state.power);
      if (!animate || JU.reduceMotion()) { d.cur = Object.assign({}, d.tgt); d.start = 0; }
      else d.start = now + d.delay;
    });
    draw(); kick();
  }

  function buildKey() {
    var ul = JU.$("#hero-key"); if (!ul) return;
    ul.innerHTML = "";
    var rows = JU.data.collections && JU.data.collections.collections; if (!rows) return;
    var counts = {}; rows.forEach(function (r) { counts[r.media_class] = (counts[r.media_class] || 0) + 1; });
    JU.LOC.forEach(function (l) {
      if (!counts[l.key]) return;
      var li = JU.h("li", { class: l.onchain ? "on" : "off" }, JU.h("i", { style: "background:" + HERO_COLOR[l.key] }), l.label);
      ul.appendChild(li);
    });
  }
  function caption() {
    var el = JU.$("#dots-caption"); if (!el) return;
    el.textContent = JU.state.power === "on"
      ? "One pixel per collection. Outlines do not fully load today."
      : "Most pixels go dark. Lit pixels are fully on-chain candidates; outlines are partial candidates.";
  }

  var tipOn = false;
  function onMove(e) {
    var rect = canvas.getBoundingClientRect();
    var x = e.clientX - rect.left, y = e.clientY - rect.top;
    var xOff = (W - cols * cell) / 2;
    var cx = Math.floor((x - xOff) / cell), cy = Math.floor((y - 2) / cell);
    var i = cy * cols + cx, tip = JU.$("#dot-tip");
    if (cx < 0 || cx >= cols || i < 0 || i >= dots.length) { tip.hidden = true; return; }
    var r = dots[i].row, loc = JU.LOCMAP[r.media_class], live = JU.LIVE.filter(function (l) { return l.key === r.liveness; })[0], sv = JU.SURV.filter(function (l) { return l.key === r.survives_unplugged; })[0];
    tip.innerHTML = "<b>" + JU.esc(r.name) + "</b>Image: " + JU.esc(loc ? loc.label : r.media_class) + "<br>Today: " + JU.esc(live ? live.label : r.liveness) + "<br>Unplugged: " + JU.esc(sv ? sv.label : r.survives_unplugged);
    tip.hidden = false;
    var wr = canvas.parentNode.getBoundingClientRect();
    var left = Math.min(Math.max(0, e.clientX - wr.left + 12), wr.width - 200);
    tip.style.left = left + "px"; tip.style.top = (e.clientY - wr.top + 16) + "px";
    tipOn = true;
  }

  function init() {
    canvas = JU.$("#dots"); if (!canvas) return;
    ctx = canvas.getContext("2d");
    var rows = JU.data.collections && JU.data.collections.collections;
    JU.$("#plug-btn").addEventListener("click", JU.togglePower);
    JU.$("#pill").addEventListener("click", JU.togglePower);
    JU.$(".plug-svg").addEventListener("click", JU.togglePower);
    if (rows && rows.length) {
      var sorted = rows.slice().sort(function (a, b) {
        return (ORDER[a.survives_unplugged] - ORDER[b.survives_unplugged]) || (LOCI[a.media_class] - LOCI[b.media_class]) ||
          ((a.liveness === "alive" ? 0 : 1) - (b.liveness === "alive" ? 0 : 1)) || (b.holders - a.holders);
      });
      dots = sorted.map(function (r) { return { row: r, rgb: hex(HERO_COLOR[r.media_class] || HERO_COLOR.other), cur: paramsFor(r, "on"), tgt: null, start: 0, delay: 0 }; });
      layout(); retarget(false);
      canvas.addEventListener("pointermove", onMove);
      canvas.addEventListener("pointerleave", function () { JU.$("#dot-tip").hidden = true; });
      JU.afterResize.push(function () { layout(); retarget(false); });
      buildKey();
      canvas.setAttribute("aria-label", "One pixel per census collection. " + rows.length + " collections. The table below lists each one.");
    } else {
      canvas.style.height = "0"; JU.$("#dots-caption").textContent = "Collection data not loaded.";
    }
    JU.onPower(function (s, changed, opts) {
      animatePlug(s.power === "off" ? 1 : 0);
      caption(); updateFigure();
      if (dots.length) retarget(true);
    });
    plugT = JU.state.power === "off" ? 1 : 0; drawPlug(plugT);
    caption(); updateFigure();
    if (dots.length) retarget(false);
  }
  JU.initHero = init;
})();
