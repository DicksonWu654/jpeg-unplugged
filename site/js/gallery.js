/* gallery.js - live, sandboxed renders. Plugged = the document as the chain returned it. Unplugged = same bytes under a
   strict CSP meta tag, so the browser itself refuses every request. Unplugged + archive = the archived-dependency variant. */
(function () {
  "use strict";
  var JU = window.JU, h = JU.h;

  // Featured order is defined only here; names and verdicts always come from gallery.json.
  var FEATURED = ["cryptopunks-data", "ab-0", "ab-78", "ab-13", "autoglyphs", "loot", "nouns", "checks", "terraforms", "ab-1"];

  var CSP = "default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval' data: blob:; connect-src data: blob:; style-src 'unsafe-inline' data:; img-src data: blob:; font-src data:; media-src data: blob:; form-action 'none'; base-uri 'none'";
  var KNOWN_CDNS = ["cdnjs.cloudflare.com", "unpkg.com", "cdn.aframe.io"]; /* plain library hosts; anything else asks first */
  /* A sandboxed frame without allow-same-origin has no storage and throws on localStorage/cookie access. Many libraries touch
     them at start-up, so give the frame in-memory stand-ins (the harness page had real ones). */
  var SHIM = "try{var mk=function(){var d={};return{getItem:function(k){return Object.prototype.hasOwnProperty.call(d,k)?d[k]:null},setItem:function(k,v){d[k]=String(v)},removeItem:function(k){delete d[k]},clear:function(){d={}},key:function(i){return Object.keys(d)[i]||null},get length(){return Object.keys(d).length}}};" +
    "['localStorage','sessionStorage'].forEach(function(n){var st=mk();Object.defineProperty(window,n,{configurable:true,get:function(){return st}})});" +
    "Object.defineProperty(document,'cookie',{configurable:true,get:function(){return ''},set:function(){}})}catch(e){}";
  var REPORTER = SHIM + "(function(){var id='__ID__';function s(t,d){try{parent.postMessage({ju:1,id:id,t:t,d:d},'*')}catch(e){}}" +
    "document.addEventListener('securitypolicyviolation',function(e){s('blocked',{u:String(e.blockedURI||''),dir:String(e.effectiveDirective||'')})});" +
    "addEventListener('error',function(e){var t=e.target;if(t&&t!==window&&(t.src||t.href)){s('loaderr',{u:String(t.src||t.href)})}else{s('err',{m:String(e.message||'')})}},true);" +
    "addEventListener('unhandledrejection',function(e){var r=e.reason;s('err',{m:String(r&&r.message||r)})});" +
    "try{new PerformanceObserver(function(l){l.getEntries().forEach(function(x){s('fetched',{u:String(x.name)})})}).observe({type:'resource',buffered:true})}catch(e){}})();";

  var G = { items: [], bySlug: {}, tiles: {}, docs: {}, consent: {}, filter: "all", paused: false, owners: {}, manual: {}, io: null, vis: {}, seq: 0 };

  function mode() { return JU.state.power === "on" ? "plugged" : JU.state.archive ? "archive" : "unplugged"; }
  function heavy(it) { return /three|regl|a-frame|aframe|webgl/i.test(it.medium); }
  function hostOf(u) { try { return new URL(u).host; } catch (e) { return String(u).slice(0, 40); } }
  function liveBlocked() {
    return (window.matchMedia && window.matchMedia("(max-width: 700px)").matches) || JU.reduceMotion() ||
      (navigator.connection && navigator.connection.saveData) || location.protocol === "file:";
  }
  function cap() { return liveBlocked() ? 3 : 8; }
  function riskyHosts(it) { return it.ext_hosts_A.filter(function (x) { return KNOWN_CDNS.indexOf(x) < 0; }); }
  function fileFor(it, m) { return m === "archive" && it.archive ? it.archive : it.file; }

  /* ---------- verdict badge for the current mode ---------- */
  function badge(it, m) {
    var v, cls, ic, txt;
    if (m === "plugged") { cls = "good"; ic = "✓"; txt = it.ext_requests_A ? "Loads (fetches " + it.ext_requests_A + ")" : "Loads"; }
    else {
      v = m === "unplugged" ? it.verdict_B : it.verdict_C;
      if (v === "identical") { cls = "good"; ic = "✓"; txt = m === "archive" && it.verdict_B !== "identical" ? "Restored" : "Unchanged"; if (txt === "Restored") ic = "↺"; }
      else if (v === "a-blank") { cls = "mute"; ic = "-"; txt = "Faint by design"; }
      else if (v === "degraded") { cls = "warn"; ic = "!"; txt = "Degraded"; }
      else { cls = "crit"; ic = "×"; txt = "Broken"; }
    }
    return h("span", { class: "vbadge " + cls }, h("span", { class: "ic", "aria-hidden": "true", text: ic }), txt);
  }
  function thumbFor(it, m) { var k = m === "plugged" ? "A" : m === "unplugged" ? "B" : "C"; return "gallery-assets/" + (it.thumbs[k] || it.thumbs.A); }

  /* ---------- building the sandboxed document ---------- */
  function loadDoc(file) {
    if (!G.docs[file]) G.docs[file] = fetch("gallery-assets/" + file).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.text(); });
    return G.docs[file];
  }
  function buildDoc(it, m, id, text) {
    var inj = (m === "plugged" ? "" : '<meta http-equiv="Content-Security-Policy" content="' + CSP + '">') + "<script>" + REPORTER.replace("__ID__", id) + "<\/script>";
    if (it.file_type === "svg") {
      return "<!doctype html><html><head><meta charset=\"utf-8\">" + inj + "<style>html,body{margin:0;height:100%;background:#fff}img{display:block;width:100%;height:100%;object-fit:contain}</style></head><body><img alt=\"\" src=\"data:image/svg+xml;charset=utf-8," + encodeURIComponent(text) + "\"></body></html>";
    }
    // Put the policy first in the real head, before any artwork script or resource.
    var head = /<head\b[^>]*>/i.exec(text);
    if (head) {
      var at = head.index + head[0].length;
      return text.slice(0, at) + inj + text.slice(at);
    }
    var opening = /^\s*(?:<!doctype[^>]*>\s*)?(?:<html\b[^>]*>)?/i.exec(text);
    var end = opening ? opening[0].length : 0;
    return text.slice(0, end) + "<head>" + inj + "</head>" + text.slice(end);
  }
  function makeFrame(it, m, id, text) {
    var f = h("iframe", { title: it.name + " (" + m + ")", sandbox: "allow-scripts", referrerpolicy: "no-referrer", allow: "", tabindex: "-1", "aria-hidden": "true" });
    if (m !== "plugged") f.setAttribute("csp", CSP);
    f.srcdoc = buildDoc(it, m, id, text);
    return f;
  }

  /* ---------- reports coming back from the frames ---------- */
  window.addEventListener("message", function (e) {
    var d = e.data; if (!d || d.ju !== 1 || typeof d.id !== "string") return;
    var o = G.owners[d.id]; if (!o || !o.frame || e.source !== o.frame.contentWindow) return;
    var ev = o.events;
    if (ev.length > 60) return;
    var u = d.d && typeof d.d.u === "string" ? d.d.u.slice(0, 300) : "", msg = d.d && typeof d.d.m === "string" ? d.d.m.slice(0, 200) : "";
    if (d.t === "fetched" && (!/^https?:/.test(u) || o.mode !== "plugged")) return; /* when unplugged the browser still lists the refused request; it was not fetched */
    if (d.t === "loaderr" && o.mode !== "plugged" && o.seen["blocked|" + u]) return;
    if (d.t === "blocked" && (u === "inline" || u === "eval" || !u || /^(data|blob):/.test(u))) return;
    var key = d.t + "|" + (u || msg);
    if (o.seen[key]) return; o.seen[key] = 1;
    ev.push({ t: d.t, u: u, m: msg });
    if (o.onEvent) o.onEvent();
  });
  function newOwner(frame, onEvent, m) {
    var id = "o" + (++G.seq);
    G.owners[id] = { id: id, frame: frame, events: [], seen: {}, onEvent: onEvent, mode: m };
    return id;
  }
  function eventLines(o, limit) {
    var out = [];
    o.events.forEach(function (e) {
      if (e.t === "blocked") out.push({ bad: true, txt: "blocked " + hostOf(e.u) + (e.u.length > 0 ? " " + e.u.replace(/^https?:\/\/[^/]+/, "").slice(0, 38) : "") });
      else if (e.t === "fetched") out.push({ bad: false, txt: "requested " + hostOf(e.u) });
      else if (e.t === "loaderr") out.push({ bad: true, txt: "failed to load " + hostOf(e.u) });
      else if (e.t === "err") out.push({ bad: true, txt: e.m });
    });
    return limit ? out.slice(0, limit) : out;
  }

  /* ---------- tiles ---------- */
  function sortItems(items) {
    return items.slice().sort(function (a, b) {
      var ai = FEATURED.indexOf(a.slug), bi = FEATURED.indexOf(b.slug);
      if (ai >= 0 || bi >= 0) return (ai < 0 ? Infinity : ai) - (bi < 0 ? Infinity : bi);
      return a.name.localeCompare(b.name, "en", { numeric: true });
    });
  }

  function staticLine(it) {
    return it.ext_hosts_A.length ? "Asks for " + it.ext_hosts_A.join(", ") : "Asks for nothing outside the chain";
  }
  function buildTile(it) {
    var img = h("img", { class: "thumb", src: thumbFor(it, mode()), alt: "", loading: "lazy", decoding: "async" });
    var stage = h("div", { class: "tile-stage" }, img);
    var tag = h("div", { class: "tile-tag" });
    var open = h("button", { type: "button", class: "tile-open", "aria-label": "Open " + it.name + " larger", onclick: function () { openViewer(it); } });
    var live = h("p", { class: "tile-live", "aria-live": "off" });
    var cap_ = h("div", { class: "tile-cap" },
      h("h4", { class: "tile-name", text: it.name.replace(/^Art Blocks #\d+ /, "").replace(/ \(.+\)$/, "") }),
      h("p", { class: "tile-sub", text: "#" + (it.token.length > 12 ? it.token.slice(0, 10) + "…" : it.token) + " · " + it.medium }),
      h("p", { class: "tile-sub tile-dependency", text: it.ext_hosts_A.length ? "External dependency" : "Chain bytes only" }), live);
    var el = h("article", { class: "tile", "data-slug": it.slug }, stage, cap_);
    stage.appendChild(tag); stage.appendChild(open);
    var t = { it: it, el: el, stage: stage, img: img, tag: tag, liveEl: live, frame: null, ownerId: null, running: false, runBtn: null, consent: null };
    G.tiles[it.slug] = t;
    paintTile(t);
    return el;
  }
  function paintTile(t) {
    var m = mode(), verdict = m === "unplugged" ? t.it.verdict_B : t.it.verdict_C;
    t.el.classList.toggle("is-broken", m !== "plugged" && verdict !== "identical" && verdict !== "a-blank");
    t.el.classList.toggle("is-survivor", m !== "plugged" && verdict === "identical");
    t.tag.innerHTML = ""; t.tag.appendChild(badge(t.it, m));
    if (!t.running) t.img.src = thumbFor(t.it, m);
    t.img.alt = t.it.name + ", " + (m === "plugged" ? "with the network" : m === "unplugged" ? "unplugged" : "unplugged with archive") + " (screenshot)";
    t.el.classList.remove("flash");
    // static hint for non-running tiles in thumbnail-only environments
    if (!t.running) {
      if (liveBlocked()) {
        if (!t.runBtn) { t.runBtn = h("button", { type: "button", class: "tile-run", text: "Run live ↗", onclick: function () { G.manual[t.it.slug] = true; schedule(true); } }); JU.$(".tile-cap", t.el).appendChild(t.runBtn); }
      } else if (t.runBtn) { t.runBtn.remove(); t.runBtn = null; }
    }
  }
  function needsConsent(t) { return mode() === "plugged" && riskyHosts(t.it).length && !G.consent[t.it.slug]; }
  function showConsent(t) {
    if (t.consent) return;
    var rh = riskyHosts(t.it).join(", ");
    t.consent = h("div", { class: "tile-consent" }, h("span", { text: "Plugged in, this piece asks " + rh + " for something that depends on who you are (your IP address)." }),
      h("button", { type: "button", text: "Run it anyway", onclick: function (e) { e.stopPropagation(); G.consent[t.it.slug] = true; hideConsent(t); schedule(true); } }));
    t.stage.appendChild(t.consent);
  }
  function hideConsent(t) { if (t.consent) { t.consent.remove(); t.consent = null; } }

  function startTile(t) {
    if (t.running) return;
    if (needsConsent(t)) { showConsent(t); return; }
    hideConsent(t);
    t.running = true; t.starting = ++G.seq;
    var token = t.starting, m = mode(), it = t.it;
    if (t.runBtn) { t.runBtn.remove(); t.runBtn = null; }
    loadDoc(fileFor(it, m)).then(function (text) {
      if (!t.running || t.starting !== token) return;
      var frame = h("iframe");
      var oid = newOwner(frame, function () { renderTileLive(t); }, m);
      frame = makeFrame(it, m, oid, text);
      G.owners[oid].frame = frame;
      t.frame = frame; t.ownerId = oid;
      frame.addEventListener("load", function () { t.el.classList.add("is-live"); });
      t.stage.insertBefore(frame, t.tag);
      t.liveEl.textContent = "";
      active++; updateLiveNote();
    }, function (err) { t.running = false; t.liveEl.textContent = "Could not load " + fileFor(it, m) + ": " + err.message; });
  }
  function stopTile(t) {
    if (!t.running) return;
    t.running = false; t.starting = 0;
    if (t.frame) { t.frame.remove(); t.frame = null; active = Math.max(0, active - 1); }
    if (t.ownerId) { delete G.owners[t.ownerId]; t.ownerId = null; }
    t.el.classList.remove("is-live"); t.liveEl.textContent = "";
    paintTile(t); updateLiveNote();
  }
  function renderTileLive(t) {
    var o = G.owners[t.ownerId]; if (!o) return;
    var hosts = {}, nh = 0, err = "", n = 0;
    o.events.forEach(function (e) {
      if (e.t === "blocked" || e.t === "loaderr" || e.t === "fetched") { var k = (e.t === "fetched" ? "r " : "b ") + hostOf(e.u); if (!hosts[k]) { hosts[k] = 1; nh++; } n++; }
      else if (e.t === "err" && !err) err = e.m.replace(/^Uncaught\s*/, "");
    });
    t.liveEl.innerHTML = "";
    Object.keys(hosts).forEach(function (k, i) {
      t.liveEl.appendChild(h("span", { class: k[0] === "b" ? "bad" : "ok", text: (i ? " " : "") + (k[0] === "b" ? "blocked " : "requested ") + k.slice(2) }));
    });
    if (err) t.liveEl.appendChild(h("span", { class: "bad", text: (nh ? " | " : "") + (err.length > 70 ? err.slice(0, 68) + "\u2026" : err) }));
  }
  var active = 0;
  function updateLiveNote() {
    var el = JU.$("#g-live"); if (!el) return;
    el.textContent = liveBlocked()
      ? "Reference screenshots. Tap “Run live” to test."
      : active + " live renders · other tiles show reference screenshots until you scroll.";
  }

  /* ---------- deciding which tiles run live ---------- */
  var schT;
  function schedule(now) { clearTimeout(schT); schT = setTimeout(reconcile, now ? 0 : 140); }
  function reconcile() {
    if (G.paused) return;
    var vh = window.innerHeight, mid = vh / 2, C = cap(), used = 0;
    var vis = Object.keys(G.vis).filter(function (s) { return G.vis[s]; }).map(function (s) { return G.tiles[s]; }).filter(Boolean);
    vis.forEach(function (t) { var r = t.stage.getBoundingClientRect(); t._d = Math.abs(r.top + r.height / 2 - mid); });
    vis.sort(function (a, b) { return a._d - b._d; });
    var want = {};
    var blocked = liveBlocked();
    // manual first, then (when allowed) automatic by distance to the viewport centre, keeping running tiles sticky
    vis.forEach(function (t) {
      var w = heavy(t.it) ? 2 : 1;
      if (G.manual[t.it.slug] && used + w <= C) { want[t.it.slug] = 1; used += w; }
    });
    if (!blocked) {
      vis.filter(function (t) { return t.running && !want[t.it.slug]; }).forEach(function (t) { var w = heavy(t.it) ? 2 : 1; if (used + w <= C) { want[t.it.slug] = 1; used += w; } });
      vis.forEach(function (t) { if (want[t.it.slug]) return; var w = heavy(t.it) ? 2 : 1; if (used + w <= C) { want[t.it.slug] = 1; used += w; } });
    }
    Object.keys(G.tiles).forEach(function (s) {
      var t = G.tiles[s];
      if (want[s]) startTile(t); else { if (t.running) stopTile(t); hideConsent(t); }
    });
    updateLiveNote();
  }
  function initObserver() {
    if (!("IntersectionObserver" in window)) { Object.keys(G.tiles).forEach(function (s) { G.vis[s] = true; }); return; }
    G.io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { G.vis[en.target.getAttribute("data-slug")] = en.isIntersecting; });
      schedule();
    }, { rootMargin: "120px 0px" });
    Object.keys(G.tiles).forEach(function (s) { G.io.observe(G.tiles[s].el); });
    window.addEventListener("scroll", function () { schedule(); }, { passive: true });
  }

  /* ---------- reacting to the plug ---------- */
  function onPower() {
    updateModeButtons(); modeNote();
    Object.keys(G.tiles).forEach(function (s) {
      var t = G.tiles[s], was = t.running;
      if (was) stopTile(t);
      hideConsent(t);
      t.liveEl.textContent = "";
      paintTile(t);
      if (was) t.el.classList.add("flash");
    });
    schedule(true);
    if (viewerItem) fillViewerLive();
  }
  function updateModeButtons() {
    var m = mode();
    JU.$$(".seg3").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-mode") === (m === "plugged" ? "on" : m === "unplugged" ? "off" : "archive"))); });
  }
  function modeNote() {
    var el = JU.$("#g-mode-note"); if (!el || !G.items.length) return;
    var C = JU.data.gallery.counts, n = G.items.length, m = mode();
    var hosts = {}; G.items.forEach(function (i) { i.ext_hosts_A.forEach(function (x) { hosts[x] = 1; }); });
    var hostList = Object.keys(hosts).sort();
    var risky = G.items.filter(function (i) { return riskyHosts(i).length; }).length;
    var brokenB = G.items.filter(function (i) { return i.verdict_B !== "identical" && i.verdict_B !== "a-blank"; }).length;
    var saved = G.items.filter(function (i) { return i.verdict_B !== "identical" && i.verdict_B !== "a-blank" && i.verdict_C === "identical"; }).length;
    var still = G.items.filter(function (i) { return i.verdict_C !== "identical" && i.verdict_C !== "a-blank"; }).length;
    if (m === "plugged") el.textContent = "Network connected. " + C.made_request_in_A + " of " + n + " pieces reach outside the chain. Try unplugging.";
    else if (m === "unplugged") el.textContent = "Network blocked by the browser. " + brokenB + " of " + n + " pieces go blank or break. Survivors stay lit.";
    else el.textContent = "Network still blocked. Local archived libraries restore " + saved + " of " + brokenB + " broken pieces; " + still + " still fails.";

  }

  /* ---------- filters ---------- */
  function applyFilter() {
    var f = G.filter;
    Object.keys(G.tiles).forEach(function (s) {
      var it = G.tiles[s].it, ok = true;
      var brk = it.verdict_B !== "identical" && it.verdict_B !== "a-blank";
      if (f === "breaks") ok = brk;
      else if (f === "saved") ok = brk && it.verdict_C === "identical";
      else if (f === "ab") ok = it.family === "art-blocks";
      else if (f === "other") ok = it.family !== "art-blocks";
      if (FEATURED.indexOf(s) >= 0) ok = true;
      G.tiles[s].el.hidden = !ok;
      if (!ok) { G.vis[s] = false; stopTile(G.tiles[s]); }
    });
    schedule(true);
  }

  /* ---------- viewer ---------- */
  var viewerItem = null, viewerOwner = null, viewerFrame = null;
  function row(dl, k, v) { if (v === null || v === undefined || v === "" || (Array.isArray(v) && !v.length)) return; dl.appendChild(h("dt", { text: k })); var dd = h("dd"); if (v.nodeType) dd.appendChild(v); else dd.textContent = Array.isArray(v) ? v.join(", ") : String(v); dl.appendChild(dd); }
  function openViewer(it) {
    var dlg = JU.$("#viewer"); if (!dlg.showModal) return;
    G.paused = true; Object.keys(G.tiles).forEach(function (s) { stopTile(G.tiles[s]); });
    viewerItem = it;
    var info = JU.$("#v-info"); info.innerHTML = "";
    info.appendChild(h("h3", { id: "v-title", text: it.name }));
    var sw = h("div", { class: "g-power" }, [["on", "Plugged in"], ["off", "Unplugged"], ["archive", "Unplugged + archive"]].map(function (b) {
      return h("button", { type: "button", class: "seg3", "data-mode": b[0], "aria-pressed": "false", text: b[1], onclick: function () { JU.setPower(b[0] === "on" ? "on" : "off", b[0] === "archive", { user: true }); } });
    }));
    info.appendChild(sw);
    info.appendChild(h("p", { class: "v-note", id: "v-verdict" }));
    var dl = h("dl");
    var etherscan = h("a", { href: "https://etherscan.io/token/" + it.contract + "?a=" + encodeURIComponent(it.token), rel: "noopener", text: it.contract });
    row(dl, "Contract", etherscan);
    row(dl, "Token id", it.token);
    row(dl, "Medium", it.medium);
    row(dl, "How the chain stores it", it.storage);
    row(dl, "Asks for (plugged)", it.ext_hosts_A.length ? it.ext_hosts_A : "nothing outside the chain");
    row(dl, "Declared dependencies", it.declared_deps);
    row(dl, "Archived copies", it.archive_urls);
    row(dl, "Errors unplugged", it.console_errors_B || it.page_errors_B ? it.console_errors_B + " console, " + it.page_errors_B + " page" : "none");
    row(dl, "Gas to read", it.gas_est ? JU.fmt(it.gas_est) + (it.needs_fork ? " (more than a public RPC allows; read from a mainnet fork)" : "") : "");
    row(dl, "Verdict unplugged / with archive", it.verdict_B + " / " + it.verdict_C + (it.manual_override ? " (hand-reviewed)" : ""));
    row(dl, "Notes", it.notes.replace(/\bB uses\b/, "Unplugged uses").replace(/blocked in B\b/, "blocked when unplugged").replace(/\bin B\b/g, "unplugged").replace(/; B /g, "; unplugged "));
    info.appendChild(dl);
    var abc = h("div", { class: "v-abc" });
    [["A", "Plugged in"], ["B", "Unplugged"], ["C", "Unplugged + archive"]].forEach(function (p) {
      if (it.thumbs[p[0]]) abc.appendChild(h("figure", null, h("img", { src: "gallery-assets/" + it.thumbs[p[0]], alt: it.name + " " + p[1] + " (screenshot)", loading: "lazy" }), h("figcaption", { text: p[1] })));
    });
    info.appendChild(abc);
    info.appendChild(h("p", { class: "v-note" }, "This is what the piece reports while it runs here:"));
    info.appendChild(h("div", { class: "v-log", id: "v-log", "aria-live": "polite" }));
    info.appendChild(h("p", { class: "v-note" }, h("a", { href: "gallery-assets/" + it.file, text: "Open the unplugged file" }),
      it.archive ? [" · ", h("a", { href: "gallery-assets/" + it.archive, text: "the archive version" })] : null));
    updateModeButtons();
    dlg.showModal();
    fillViewerLive();
  }
  function fillViewerLive() {
    var it = viewerItem, stage = JU.$("#v-stage"), m = mode();
    stage.innerHTML = "";
    if (viewerOwner) { delete G.owners[viewerOwner]; viewerOwner = null; }
    var vb = JU.$("#v-verdict");
    if (vb) { vb.innerHTML = ""; vb.appendChild(badge(it, m)); }
    var log = JU.$("#v-log"); if (log) log.textContent = "";
    if (m === "plugged" && riskyHosts(it).length && !G.consent[it.slug]) {
      stage.appendChild(h("img", { src: thumbFor(it, m), alt: "" }));
      stage.appendChild(h("div", { class: "tile-consent" }, h("span", { text: "Plugged in, this piece asks " + riskyHosts(it).join(", ") + " for something that depends on your IP address." }),
        h("button", { type: "button", text: "Run it anyway", onclick: function () { G.consent[it.slug] = true; fillViewerLive(); } })));
      return;
    }
    stage.appendChild(h("img", { src: thumbFor(it, m), alt: "" }));
    loadDoc(fileFor(it, m)).then(function (text) {
      if (viewerItem !== it || mode() !== m) return;
      var frame = h("iframe"), oid = newOwner(frame, function () {
        var o = G.owners[oid]; if (!o || !log) return;
        log.textContent = eventLines(o).map(function (l) { return (l.bad ? "x " : "  ") + l.txt; }).join("\n") || "";
      }, m);
      frame = makeFrame(it, m, oid, text); G.owners[oid].frame = frame; viewerOwner = oid; viewerFrame = frame;
      frame.style.opacity = "0"; frame.style.transition = "opacity .3s";
      frame.addEventListener("load", function () { frame.style.opacity = "1"; if (log && !log.textContent) log.textContent = m === "plugged" ? "(nothing reported yet)" : "(no blocked requests reported)"; });
      stage.appendChild(frame);
    }, function (e) { if (log) log.textContent = "Could not load: " + e.message; });
  }
  function closeViewer() {
    var stage = JU.$("#v-stage"); if (stage) stage.innerHTML = "";
    if (viewerOwner) { delete G.owners[viewerOwner]; viewerOwner = null; }
    viewerItem = null; viewerFrame = null; G.paused = false;
    schedule(true);
  }

  /* ---------- init ---------- */
  JU.initGallery = function () {
    var err = JU.$("#gallery-error"), grid = JU.$("#g-grid");
    if (JU.data.errors.gallery || !JU.data.gallery) {
      err.hidden = false;
      err.innerHTML = "<b>Could not load the gallery.</b> <code>" + JU.esc((JU.data.errors.gallery || {}).path || "data/gallery.json") + "</code>: " + JU.esc((JU.data.errors.gallery || {}).message || "missing") + "." + JU.esc(JU.fileHint);
      JU.$("#g-controls").hidden = true; return;
    }
    G.items = sortItems(JU.data.gallery.items);
    G.items.forEach(function (it) { G.bySlug[it.slug] = it; });
    var C = JU.data.gallery.counts;
    JU.$("#gallery-lede").textContent = "Pull the plug. See which of these artworks survive.";
    G.items.forEach(function (it) { (FEATURED.indexOf(it.slug) >= 0 ? grid : JU.$("#g-all-grid")).appendChild(buildTile(it)); });
    JU.$("#show-all-label").textContent = "Show all " + JU.fmt(G.items.length) + " pieces (+" + JU.fmt(G.items.length - FEATURED.length) + ")";
    JU.$("#gallery-all").addEventListener("toggle", function () { schedule(true); });
    JU.$$(".seg3", JU.$("#g-controls")).forEach(function (b) {
      b.addEventListener("click", function () { var md = b.getAttribute("data-mode"); JU.setPower(md === "on" ? "on" : "off", md === "archive", { user: true }); });
    });
    JU.$$(".chip", JU.$("#gallery-all")).forEach(function (b) {
      b.addEventListener("click", function () {
        G.filter = b.getAttribute("data-f");
        JU.$$(".chip").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
        applyFilter();
      });
    });
    JU.$("#viewer").addEventListener("close", closeViewer);
    JU.$("#viewer").addEventListener("click", function (e) { if (e.target === JU.$("#viewer")) JU.$("#viewer").close(); });
    var brk = G.items.filter(function (i) { return i.verdict_B !== "identical" && i.verdict_B !== "a-blank"; }).length;
    JU.$("#g-foot").textContent = "Reference verdicts compare screenshots from the same token in each mode. Open any piece for its live sandbox, contract and request log. A lit tile is a rendering result, not a claim of immutable control.";
    updateModeButtons(); modeNote(); updateLiveNote();
    JU.onPower(onPower);
    if (window.matchMedia) { var mq = window.matchMedia("(max-width: 700px)"); var cb = function () { Object.keys(G.tiles).forEach(function (s) { var t = G.tiles[s]; stopTile(t); paintTile(t); }); schedule(true); }; if (mq.addEventListener) mq.addEventListener("change", cb); }
    initObserver();
    schedule(true);
  };
})();
