/* core.js - shared state, data loading, helpers. Classic script, no modules, no network except same-origin JSON. */
(function () {
  "use strict";
  var JU = (window.JU = {});

  /* ---------- vocabulary (labels only; every count comes from the JSON files) ---------- */
  JU.LOC = [
    { key: "data-uri", label: "Data URI", long: "A data: URI stored in the contract", onchain: true },
    { key: "onchain-renderer", label: "Built by contract", long: "A data: URI the contract builds when called", onchain: true },
    { key: "arweave", label: "Arweave", long: "Arweave (ar:// or a gateway URL)", onchain: false },
    { key: "ipfs", label: "IPFS", long: "IPFS (ipfs:// or a gateway URL)", onchain: false },
    { key: "http", label: "HTTP server", long: "An ordinary web server or CDN", onchain: false },
    { key: "broken", label: "Read failed", long: "Reverts, empty or undecodable", onchain: false },
    { key: "unresolved", label: "Unknown (metadata unreachable)", long: "Media location unknown: the metadata that names it could not be fetched", onchain: false },
    { key: "other", label: "None / other", long: "No media field or unrecognised scheme", onchain: false }
  ];
  JU.LOCMAP = {};
  JU.LOC.forEach(function (l) { JU.LOCMAP[l.key] = l; });
  JU.LIVE = [
    { key: "alive", label: "Loads", icon: "✓", cls: "good" },
    { key: "degraded", label: "Partly loads", icon: "!", cls: "warn" },
    { key: "dead", label: "Metadata unavailable", icon: "×", cls: "crit" },
    { key: "unknown", label: "Unknown", icon: "?", cls: "unk" }
  ];
  JU.reasonLabel = function (reason) {
    return {
      "dns-failure": "DNS lookup failed", "ipfs-content-not-found": "IPFS not found",
      "arweave-content-not-found": "Arweave not found", "tokenuri-revert": "Contract call reverts",
      "bad-tokenuri": "Invalid token URI", "not-json": "Invalid metadata JSON",
      "http-4xx": "HTTP client error", "http-5xx": "HTTP server error",
      "tls-error": "TLS connection failed", "connection-error": "Connection failed",
      "parked-domain": "Parked domain", "other": "Other read failure"
    }[reason] || "Metadata unavailable";
  };
  JU.SURV = [
    { key: "yes", label: "Fully on-chain candidate", icon: "✓", cls: "neutral" },
    { key: "partial", label: "Partly", icon: "½", cls: "warn" },
    { key: "no", label: "Outside candidate set", icon: "×", cls: "crit" },
    { key: "unknown", label: "Unknown", icon: "?", cls: "unk" }
  ];
  JU.VERD = [
    { key: "holds", outcome: "holds", label: "Holds", icon: "✓", cls: "good" },
    { key: "partial", outcome: "onchain-data-offchain-pointer", label: "On-chain data; off-chain pointer", icon: "↗", cls: "neutral" },
    { key: "fails", outcome: "contradicted", label: "Contradicted", icon: "×", cls: "crit" },
    { key: "unverified", outcome: "unverifiable", label: "Unverifiable", icon: "?", cls: "unk" }
  ];
  // Legacy verdict keys remain transport/filter keys; only a reviewed outcome can label a claim.
  JU.claimVerdict = function (claim) {
    var verdict = JU.VERD.filter(function (v) { return claim && v.outcome === claim.outcome; })[0];
    return verdict ? verdict.key : "unverified";
  };

  /* ---------- tiny helpers ---------- */
  var SVGNS = "http://www.w3.org/2000/svg";
  JU.h = function (tag, attrs) {
    var svg = /^(svg|g|path|rect|circle|line|text|defs|pattern|clipPath|title|tspan)$/.test(tag);
    var n = svg ? document.createElementNS(SVGNS, tag) : document.createElement(tag);
    if (attrs) for (var k in attrs) {
      var v = attrs[k];
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") n.setAttribute("class", v);
      else if (k === "text") n.textContent = v;
      else if (k === "html") n.innerHTML = v;
      else if (k.slice(0, 2) === "on" && typeof v === "function") n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i];
      if (c === null || c === undefined || c === false) continue;
      if (Array.isArray(c)) c.forEach(function (x) { if (x) n.appendChild(typeof x === "string" ? document.createTextNode(x) : x); });
      else n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    }
    return n;
  };
  JU.$ = function (s, root) { return (root || document).querySelector(s); };
  JU.$$ = function (s, root) { return Array.prototype.slice.call((root || document).querySelectorAll(s)); };
  JU.fmt = function (n) { return (n === null || n === undefined || isNaN(n)) ? "-" : Number(n).toLocaleString("en-US"); };
  JU.pct = function (x, total, digits) {
    if (!total) return "0%";
    var p = (100 * x) / total;
    if (digits === undefined) digits = p > 0 && p < 10 ? 1 : 0;
    return p.toFixed(digits).replace(/\.0$/, "") + "%";
  };
  JU.sum = function (obj, keys) { return keys.reduce(function (a, k) { return a + ((obj && obj[k]) || 0); }, 0); };
  JU.css = function (name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); };
  JU.color = function (key) { return JU.css("--c-" + key) || JU.css("--c-other"); };
  JU.inkOn = function (hex) {
    var m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || "");
    if (!m) return "#fff";
    var l = [1, 2, 3].map(function (i) { var c = parseInt(m[i], 16) / 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); });
    var L = 0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2];
    return L > 0.3 ? "#101418" : "#ffffff";
  };
  JU.esc = function (s) { return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  JU.safeUrl = function (u) {
    if (!u || u === "#") return "#";
    try { var x = new URL(u, location.href); return (x.protocol === "http:" || x.protocol === "https:") ? x.href : "#"; } catch (e) { return "#"; }
  };
  JU.shortAddr = function (a) { return a && a.length > 12 ? a.slice(0, 6) + "…" + a.slice(-4) : a || ""; };
  JU.reduceMotion = function () { return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches; };

  /* ---------- power state: the one global switch ---------- */
  JU.state = { power: "on", archive: false };
  var powerListeners = [];
  JU.onPower = function (fn) { powerListeners.push(fn); };
  JU.setPower = function (power, archive, opts) {
    var s = JU.state;
    var next = { power: power === "off" ? "off" : "on", archive: power === "off" && !!archive };
    if (next.power === s.power && next.archive === s.archive && !(opts && opts.force)) return;
    var changed = next.power !== s.power;
    s.power = next.power; s.archive = next.archive;
    document.body.setAttribute("data-power", s.power);
    var on = s.power === "on";
    var pill = JU.$("#pill"); if (pill) pill.setAttribute("aria-checked", String(on));
    var pb = JU.$("#plug-btn"); if (pb) pb.setAttribute("aria-checked", String(on));
    var lab = JU.$("#plug-btn-label"); if (lab) lab.textContent = on ? "Unplug the internet" : "Plug it back in";
    try {
      var u = new URL(location.href);
      if (on) u.searchParams.delete("power"); else u.searchParams.set("power", s.archive ? "archive" : "off");
      history.replaceState(null, "", u.pathname + u.search + u.hash);
    } catch (e) { /* file:// or sandboxed: ignore */ }
    powerListeners.forEach(function (fn) { try { fn(s, changed, opts || {}); } catch (e) { console.error(e); } });
  };
  JU.togglePower = function () { JU.setPower(JU.state.power === "on" ? "off" : "on", false, { user: true }); };

  /* ---------- toast ---------- */
  var toastTimer;
  JU.toast = function (msg, ms) {
    var t = JU.$("#toast"); if (!t) return;
    t.textContent = msg; t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.hidden = true; }, ms || 5000);
  };

  /* ---------- tooltip (one shared element; hover + keyboard focus) ---------- */
  var tipEl;
  function tipNode() { if (!tipEl) { tipEl = JU.h("div", { class: "tip", role: "tooltip", hidden: true }); document.body.appendChild(tipEl); } return tipEl; }
  JU.tipShow = function (html, x, y) {
    var t = tipNode(); t.innerHTML = html; t.hidden = false;
    var w = t.offsetWidth, hh = t.offsetHeight;
    var nx = Math.min(Math.max(8, x + 14), window.innerWidth - w - 8);
    var ny = y + 18 + hh > window.innerHeight ? y - hh - 12 : y + 18;
    t.style.left = nx + "px"; t.style.top = Math.max(8, ny) + "px";
  };
  JU.tipHide = function () { if (tipEl) tipEl.hidden = true; };
  JU.attachTip = function (node, htmlFn) {
    var touchT;
    var show = function (e) {
      JU.tipShow(htmlFn(), e.clientX, e.clientY);
      if (e.pointerType === "touch" || e.pointerType === "pen") { clearTimeout(touchT); touchT = setTimeout(JU.tipHide, 2600); }
    };
    node.addEventListener("pointerenter", show);
    node.addEventListener("pointermove", show);
    node.addEventListener("pointerleave", JU.tipHide);
    node.addEventListener("focus", function () { var r = node.getBoundingClientRect(); JU.tipShow(htmlFn(), r.left + r.width / 2, r.top); });
    node.addEventListener("blur", JU.tipHide);
  };

  /* ---------- data ---------- */
  JU.data = { census: null, collections: null, gallery: null, mutability: null, hosts: null, errors: {} };
  function getJson(path) {
    return fetch(path, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }
  JU.load = function () {
    var jobs = [["census", "data/census.json"], ["collections", "data/collections.json"], ["headlines", "data/headlines.json"], ["top100", "data/top100.json"]];
    /* optional datasets are listed in data/available.json (written by the build scripts), so a missing one costs no failed request */
    return getJson("data/available.json").catch(function () { return {}; }).then(function (av) {
      JU.data.available = av;
      if (av.mutability) jobs.push(["mutability", "data/mutability.json"]);
      if (av.hosts) jobs.push(["hosts", "data/hosts.json"]);
      return Promise.all(jobs.map(function (j) {
        return getJson(j[1]).then(function (d) { JU.data[j[0]] = d; }, function (e) { JU.data.errors[j[0]] = { path: j[1], message: String(e.message || e) }; });
      }));
    });
  };
  JU.loadGallery = function () {
    return getJson("data/gallery.json").then(function (d) { JU.data.gallery = d; }, function (e) {
      JU.data.errors.gallery = { path: "data/gallery.json", message: String(e.message || e) };
    });
  };
  /* optional high-holder rows (outside the random sample): fetched on demand, never part of any percentage */
  var extraP = null;
  JU.hasExtra = function () { return !!(JU.data.available && JU.data.available.collections_extra); };
  JU.loadExtra = function () {
    if (!JU.hasExtra()) return Promise.resolve(null);
    if (!extraP) extraP = getJson("data/collections_extra.json").then(function (d) { JU.data.extra = d; return d; }, function (e) { JU.data.errors.extra = { path: "data/collections_extra.json", message: String(e.message || e) }; return null; });
    return extraP;
  };
  /* {n, universe} when the census is a random sample of a larger universe, else null */
  JU.sampleInfo = function () {
    var c = JU.data.census, S = c && c.sampling;
    if (!S || !S.universe_collections_non_spam || !c.totals || S.universe_collections_non_spam <= c.totals.collections) return null;
    return { n: c.totals.collections, universe: S.universe_collections_non_spam };
  };
  JU.isSample = function () {
    var d = JU.data;
    return !!((d.census && d.census.sample) || (d.collections && d.collections.sample));
  };
  JU.fileHint = location.protocol === "file:" ? " Browsers block fetch() on file:// pages: serve this folder, for example with `python -m http.server` from site/." : "";

  var REQUIRED = {
    top: ["schema_version", "totals", "metadata_location", "media_location", "liveness", "survival", "by_year", "gateways", "fake_onchain", "claims"]
  };
  JU.missingKeys = function (c) {
    if (!c) return REQUIRED.top.slice();
    return REQUIRED.top.filter(function (k) { return c[k] === undefined || c[k] === null; });
  };
  /* recount collections.json and compare with census.json; returns array of human-readable mismatches */
  JU.crossCheck = function (census, coll) {
    var out = [];
    if (!census || !coll) return out;
    var rows = coll.collections || [];
    if (!!census.sample !== !!coll.sample) out.push("sample flag differs between census.json and collections.json");
    if (census.totals && census.totals.collections !== rows.length) out.push("totals.collections " + census.totals.collections + " vs " + rows.length + " rows");
    function cmp(label, tableObj, field, keys) {
      if (!tableObj) return;
      keys.forEach(function (k) {
        var n = rows.filter(function (r) { return r[field] === k; }).length;
        if ((tableObj[k] || 0) !== n) out.push(label + "." + k + " " + (tableObj[k] || 0) + " vs " + n);
      });
    }
    var lk = JU.LOC.map(function (l) { return l.key; });
    cmp("metadata_location", census.metadata_location, "metadata_class", lk);
    cmp("media_location", census.media_location, "media_class", lk);
    cmp("liveness", census.liveness, "liveness", JU.LIVE.map(function (l) { return l.key; }));
    cmp("survival", census.survival, "survives_unplugged", JU.SURV.map(function (l) { return l.key; }));
    if (census.by_year) {
      var s = census.by_year.reduce(function (a, y) { return a + y.collections; }, 0);
      if (s !== rows.length) out.push("sum(by_year.collections) " + s + " vs " + rows.length);
    }
    if (census.claims) {
      var cl = rows.filter(function (r) { return r.claim; }).length;
      if (census.claims.claimed !== cl) out.push("claims.claimed " + census.claims.claimed + " vs " + cl);
    }
    return out;
  };

  /* data-bind="census.totals.collections" -> formatted number from the loaded JSON */
  JU.bindAll = function () {
    JU.$$("[data-bind]").forEach(function (n) {
      var path = n.getAttribute("data-bind").split(".");
      var v = JU.data[path[0]];
      for (var i = 1; i < path.length && v !== undefined && v !== null; i++) v = v[path[i]];
      if (v === undefined || v === null) return;
      n.textContent = typeof v === "number" && !n.hasAttribute("data-raw") ? JU.fmt(v) : String(v);
    });
  };

  /* hide in-bar labels that do not fit (never clip text) */
  JU.fitLabels = function (root) {
    JU.$$(".seg .lab", root).forEach(function (l) {
      l.classList.remove("hide");
      var seg = l.parentNode;
      if (l.offsetWidth + 6 > seg.clientWidth) l.classList.add("hide");
    });
  };
  var rsT;
  window.addEventListener("resize", function () { clearTimeout(rsT); rsT = setTimeout(function () { JU.fitLabels(document); (JU.afterResize || []).forEach(function (f) { f(); }); }, 120); });
  JU.afterResize = [];

  /* re-render charts that read CSS colours when the OS theme flips */
  if (window.matchMedia) {
    var mq = window.matchMedia("(prefers-color-scheme: dark)");
    var themeCb = function () { (JU.onTheme || []).forEach(function (f) { f(); }); };
    if (mq.addEventListener) mq.addEventListener("change", themeCb); else if (mq.addListener) mq.addListener(themeCb);
  }
  JU.onTheme = [];
})();
