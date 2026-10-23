/* census.js - census charts and the collections table. Every number comes from data/census.json or data/collections.json. */
(function () {
  "use strict";
  var JU = window.JU, h = JU.h;

  var LOCKEYS = JU.LOC.map(function (l) { return l.key; });
  var STATUS_COLOR = { alive: "#0ca30c", degraded: "#fab219", dead: "#d03b3b", unknown: "#9aa0a8" };
  var VERD_COLOR = { holds: "#0ca30c", partial: "#fab219", fails: "#d03b3b", unverified: "#9aa0a8" };

  function surv(key) {
    return { yes: JU.css("--ink"), partial: JU.css("--ink-3"), no: JU.css("--rule-2"), unknown: JU.css("--paper-2") }[key];
  }
  function locColor(k) { return JU.color(k); }

  /* ---------- building blocks ---------- */
  function legend(items) {
    return h("ul", { class: "legend" }, items.map(function (it) {
      var li = h("li", { class: it.ghost ? "off" : "", style: "--c:" + it.color });
      if (it.icon) li.appendChild(h("span", { class: "ico", "aria-hidden": "true", text: it.icon }));
      li.appendChild(h("span", { class: "sw", "aria-hidden": "true" }));
      li.appendChild(document.createTextNode(it.label + (it.count !== undefined ? " " + JU.fmt(it.count) : "")));
      return li;
    }));
  }
  function seg(s, total) {
    var w = total ? s.value : 0;
    var node = h("div", { class: "seg" + (s.ghost ? " off" : ""), style: "flex:" + w + " 1 0; --c:" + s.color + "; --ink-on:" + JU.inkOn(s.color), tabindex: "0",
      role: "img", "aria-label": s.label + ": " + JU.fmt(s.value) + " of " + JU.fmt(total) + " (" + JU.pct(s.value, total) + ")" },
      h("span", { class: "fill" }), h("span", { class: "hatch" }),
      h("span", { class: "lab", text: JU.pct(s.value, total) }));
    JU.attachTip(node, function () { return "<b>" + JU.esc(s.label) + "</b>" + JU.fmt(s.value) + " collections (" + JU.pct(s.value, total) + ")" + (s.extra ? "<br>" + JU.esc(s.extra) : ""); });
    return node;
  }
  function sbar(segs, total) {
    return h("div", { class: "sbar", role: "group" }, segs.filter(function (s) { return s.value > 0; }).map(function (s) { return seg(s, total); }));
  }
  function brow(label, sub, bar, id) {
    return h("div", { class: "brow", "data-row": id || "" }, h("div", { class: "brow-label" }, label, sub ? h("small", { text: sub }) : null), bar);
  }
  function dataTable(headers, rows) {
    var tbl = h("table", null,
      h("thead", null, h("tr", null, headers.map(function (x) { return h("th", { scope: "col", text: x }); }))),
      h("tbody", null, rows.map(function (r) { return h("tr", null, r.map(function (c, i) { return h(i === 0 ? "th" : "td", i === 0 ? { scope: "row", text: String(c) } : { text: typeof c === "number" ? JU.fmt(c) : String(c) }); })); })));
    return h("details", { class: "view-table" }, h("summary", { text: "View as table" }), h("div", { class: "scroll" }, tbl));
  }
  function locSegs(table) {
    return JU.LOC.map(function (l) { return { key: l.key, label: l.label, value: table[l.key] || 0, color: locColor(l.key), ghost: !l.onchain }; });
  }
  function locLegend(tables) {
    return legend(JU.LOC.filter(function (l) { return tables.some(function (t) { return (t[l.key] || 0) > 0; }); })
      .map(function (l) { return { label: l.label, color: locColor(l.key), ghost: !l.onchain }; }));
  }
  function T(id, html) { var n = JU.$(id); if (n) n.innerHTML = html; }

  /* ---------- A. where does the art live ---------- */
  function renderWhere(c) {
    var root = JU.$("#ch-where"); root.innerHTML = "";
    var N = c.totals.collections, M = c.metadata_location, I = c.media_location;
    root.appendChild(locLegend([M, I]));
    root.appendChild(brow("Metadata", "the token JSON", sbar(locSegs(M), N)));
    root.appendChild(brow("Media", "the image or animation", sbar(locSegs(I), N)));
    root.appendChild(h("p", { class: "note-line", text: "Unplugged, only the first two classes (data stored in or built by the contract) can still be read." }));
    root.appendChild(dataTable(["Class", "Metadata", "Media"], JU.LOC.map(function (l) { return [l.long, M[l.key] || 0, I[l.key] || 0]; })));
    var onM = JU.sum(M, ["data-uri", "onchain-renderer"]), onI = JU.sum(I, ["data-uri", "onchain-renderer"]);
    var top = JU.LOC.filter(function (l) { return l.key !== "unresolved"; }).sort(function (a, b) { return (I[b.key] || 0) - (I[a.key] || 0); })[0];
    var unk = I.unresolved || 0;
    var si = JU.sampleInfo();
    T("#t-where", "Out of <b>" + JU.fmt(N) + "</b> " + (si ? "randomly sampled " : "") + "collections, <b>" + JU.pct(onM, N) + "</b> keep their metadata on-chain and <b>" + JU.pct(onI, N) +
      "</b> keep their media there. The most common home for media is <b>" + JU.esc(top.label) + "</b> (" + JU.pct(I[top.key] || 0, N) + ")." +
      (unk ? " For <b>" + JU.pct(unk, N) + "</b> the media location is unknown: the metadata that names it could not be fetched." : ""));
  }

  /* ---------- B. alive vs dead, today vs unplugged ---------- */
  function renderAlive(c) {
    var root = JU.$("#ch-alive"); root.innerHTML = "";
    var N = c.totals.collections, L = c.liveness, S = c.survival;
    root.appendChild(legend(JU.LIVE.map(function (l) { return { label: l.label, color: STATUS_COLOR[l.key], icon: l.icon, count: L[l.key] || 0 }; })));
    root.appendChild(brow("Today", "plugged in", sbar(JU.LIVE.map(function (l) { return { key: l.key, label: l.label, value: L[l.key] || 0, color: STATUS_COLOR[l.key] }; }), N), "today"));
    root.appendChild(legend(JU.SURV.map(function (l) { return { label: l.label, color: surv(l.key), count: S[l.key] || 0 }; })));
    root.appendChild(brow("Unplugged", "only chain bytes", sbar(JU.SURV.map(function (l) { return { key: l.key, label: l.label, value: S[l.key] || 0, color: surv(l.key) }; }), N), "unplugged"));
    // Count metadata-unavailable rows only; the aggregate reason chart also
    // includes degraded media and its legacy strong bucket includes reverts.
    var reasons = {}, unavailable = JU.data.collections.collections.filter(function (r) { return r.liveness === "dead"; });
    unavailable.forEach(function (r) { reasons[r.dead_reason] = (reasons[r.dead_reason] || 0) + 1; });
    var reverts = reasons["tokenuri-revert"] || 0;
    var misses = (reasons["ipfs-content-not-found"] || 0) + (reasons["arweave-content-not-found"] || 0);
    var direct = unavailable.length - reverts - misses;
    var categories = [["Direct negative evidence", direct], ["Contract call reverts", reverts], ["IPFS / Arweave not found", misses]];
    root.appendChild(dataTable(["Metadata unavailable: evidence category", "Collections"], categories));
    if (Object.keys(reasons).length) {
      var entries = Object.keys(reasons).map(function (k) { return [k, reasons[k]]; }).sort(function (a, b) { return b[1] - a[1]; }).slice(0, 6);
      var max = entries[0][1] || 1;
      root.appendChild(h("p", { class: "hnote", text: "Why metadata did not load (collections, dominant reason):" }));
      root.appendChild(h("div", { class: "hbars" }, entries.map(function (e) {
        return h("div", { class: "hrow" }, h("span", { class: "name", text: JU.reasonLabel(e[0]) }),
          h("span", { class: "track", style: "--c:" + STATUS_COLOR.dead }, h("i", { style: "width:" + (100 * e[1] / max) + "%" })),
          h("span", { class: "val", text: JU.fmt(e[1]) }));
      })));
    }
    root.appendChild(dataTable(["Measure", "Collections"], JU.LIVE.map(function (l) { return ["Today: " + l.label, L[l.key] || 0]; }).concat(JU.SURV.map(function (l) { return ["Unplugged: " + l.label, S[l.key] || 0]; }))));
    T("#t-alive", "<b>" + JU.pct(L.dead || 0, N, 1) + "</b> have metadata that no longer loads; another <b>" + JU.pct(L.degraded || 0, N, 1) + "</b> have sampled media that fails." +
      " Among the <b>" + JU.fmt(unavailable.length) + "</b> collections with metadata unavailable: <b>" + JU.fmt(direct) + "</b> with direct negative evidence, <b>" + JU.fmt(reverts) + "</b> contract reverts, <b>" + JU.fmt(misses) + "</b> gateway misses. A revert establishes read failure; a gateway miss does not establish permanent content loss." +
      " <b>" + JU.pct(S.yes || 0, N, 1) + "</b> have metadata and sampled media fully on-chain (an upper bound on art that survives; render-tested only for the gallery set).");
  }
  function markActiveRow() {
    var on = JU.state.power === "on";
    JU.$$("#ch-alive .brow").forEach(function (r) {
      var mine = r.getAttribute("data-row") === (on ? "today" : "unplugged");
      r.style.opacity = mine ? "1" : "0.45";
      r.style.transition = "opacity .5s";
    });
  }

  /* ---------- C. on-chain JSON, off-chain picture ---------- */
  function renderFake(c) {
    var root = JU.$("#ch-fake"); root.innerHTML = "";
    var H = JU.data.headlines;
    if (!H) { T("#t-fake", "The paper's media headline could not be loaded."); return; }
    var stat = H.random.onchain.fake_onchain_A_offchain_media_of_onchain_metadata;
    root.appendChild(h("p", { class: "stat-line", html: "<b>" + JU.fmt(stat.k) + "</b> of " + JU.fmt(stat.n) + " collections with on-chain metadata have at least one sampled media field off-chain." }));
    var parts = [
      { label: "Any media field off-chain", value: stat.k, color: locColor("http"), ghost: true },
      { label: "No off-chain media field found", value: stat.n - stat.k, color: locColor("data-uri") }
    ];
    root.appendChild(legend(parts)); root.appendChild(sbar(parts, stat.n));
    root.appendChild(dataTable(["Any sampled media field", "Collections"], parts.map(function (p) { return [p.label, p.value]; })));
    T("#t-fake", "On-chain JSON can point off-chain through <code>image</code> or <code>animation_url</code>. We count any sampled media field pointing to HTTP, IPFS or Arweave (" + JU.pct(stat.k, stat.n, 1) + "; CI " + stat.ci95[0].toFixed(1) + "–" + stat.ci95[1].toFixed(1) + "). The remaining " + JU.fmt(stat.n - stat.k) + " include " + JU.fmt(c.survival.yes) + " fully on-chain candidates and " + JU.fmt(stat.n - stat.k - c.survival.yes) + " mixed-metadata collections. Absence of an off-chain field is not a rendering test.");
  }

  /* ---------- D. by deploy year ---------- */
  function renderYear(c) {
    var root = JU.$("#ch-year"); root.innerHTML = "";
    var pooled = { year: "≤2020", collections: 0, media_location: {}, liveness: {}, survival: {} };
    var Y = c.by_year.filter(function (y) {
      if (Number(y.year) > 2020) return true;
      pooled.collections += y.collections;
      ["media_location", "liveness", "survival"].forEach(function (field) {
        Object.keys(y[field] || {}).forEach(function (k) { pooled[field][k] = (pooled[field][k] || 0) + y[field][k]; });
      });
      return false;
    }).sort(function (a, b) { return a.year - b.year; });
    if (pooled.collections) Y.unshift(pooled);
    if (!Y.length) return;
    root.appendChild(locLegend(Y.map(function (y) { return y.media_location; })));
    var Wd = Math.max(320, root.clientWidth || 640), left = 40, right = 6, top = 22;
    var band = (Wd - left - right) / Y.length, cw = Math.min(26, band * 0.66);
    var h1 = 190, gap1 = 70, h2 = 84, bottom = 38;
    var Ht = top + h1 + gap1 + h2 + bottom;
    var svg = h("svg", { class: "yearsvg", viewBox: "0 0 " + Wd + " " + Ht, role: "img", "aria-label": "Share of collections by media location and metadata or media failure, by deploy year. A table follows." });
    var defs = h("defs");
    LOCKEYS.forEach(function (k) {
      var p = h("pattern", { id: "yh-" + k, width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, h("rect", { width: 1.5, height: 5, fill: locColor(k) }));
      defs.appendChild(p);
    });
    svg.appendChild(defs);
    function gridY(y0, hh, title) {
      [0, 0.5, 1].forEach(function (f) {
        var y = y0 + hh - f * hh;
        svg.appendChild(h("line", { class: "grid", x1: left, x2: Wd - right, y1: y, y2: y }));
        svg.appendChild(h("text", { x: left - 6, y: y + 4, "text-anchor": "end", text: Math.round(f * 100) + "%" }));
      });
      svg.appendChild(h("text", { class: "ptitle", x: left, y: y0 - 8, text: title }));
    }
    gridY(top, h1, "Media location (% of collections)");
    var y2 = top + h1 + gap1;
    // two titles for panel two, swapped by the power state
    var tOn = h("text", { class: "ptitle when-on", x: left, y: y2 - 28, text: "Metadata or media fails today" });
    var tOff = h("text", { class: "ptitle when-off", x: left, y: y2 - 28, text: "Share outside the fully on-chain candidate set" });
    [0, 0.5, 1].forEach(function (f) {
      var y = y2 + h2 - f * h2;
      svg.appendChild(h("line", { class: "grid", x1: left, x2: Wd - right, y1: y, y2: y }));
      svg.appendChild(h("text", { x: left - 6, y: y + 4, "text-anchor": "end", text: Math.round(f * 100) + "%" }));
    });
    svg.appendChild(tOn); svg.appendChild(tOff);
    var rows = [];
    Y.forEach(function (y, i) {
      var cx = left + band * i + band / 2, x = cx - cw / 2, N = y.collections || 1;
      // stacked column, grows from the baseline; first class at the bottom
      var yb = top + h1, acc = 0;
      var g = h("g");
      LOCKEYS.forEach(function (k) {
        var v = (y.media_location && y.media_location[k]) || 0; if (!v) return;
        var hh = (v / N) * h1, yy = yb - acc - hh; acc += hh;
        var segH = Math.max(0, hh - 2);
        var onc = JU.LOCMAP[k].onchain;
        var sg = h("g", { class: "yseg" + (onc ? "" : " off") });
        sg.appendChild(h("rect", { class: "fill", x: x, y: yy + 2, width: cw, height: segH, fill: locColor(k), rx: 1 }));
        sg.appendChild(h("rect", { class: "hatch", x: x, y: yy + 2, width: cw, height: segH, fill: "url(#yh-" + k + ")" }));
        g.appendChild(sg);
      });
      svg.appendChild(g);
      var lstep = band < 30 ? 3 : band < 44 ? 2 : 1;
      if (i % lstep === 0 || i === Y.length - 1 && lstep === 1) {
        svg.appendChild(h("text", { x: cx, y: y2 + h2 + 16, "text-anchor": "middle", text: String(y.year) }));
        svg.appendChild(h("text", { x: cx, y: y2 + h2 + 29, "text-anchor": "middle", text: "n=" + y.collections }));
      }
      // panel two: bars grow from baseline, one set per power state
      var L = y.liveness || {}, S = y.survival || {};
      var goneToday = ((L.dead || 0) + (L.degraded || 0)) / N, goneOff = 1 - ((S.yes || 0) / N);
      [["when-on", goneToday, "#d03b3b"], ["when-off", goneOff, JU.css("--ink")]].forEach(function (p) {
        var bh = Math.max(p[1] > 0 ? 1.5 : 0, p[1] * h2);
        var gg = h("g", { class: p[0] });
        gg.appendChild(h("path", { d: "M" + x + " " + (y2 + h2) + "V" + (y2 + h2 - bh + Math.min(4, bh)) + "Q" + x + " " + (y2 + h2 - bh) + " " + (x + Math.min(4, cw / 2)) + " " + (y2 + h2 - bh) + "H" + (x + cw - Math.min(4, cw / 2)) + "Q" + (x + cw) + " " + (y2 + h2 - bh) + " " + (x + cw) + " " + (y2 + h2 - bh + Math.min(4, bh)) + "V" + (y2 + h2) + "Z", fill: p[2] }));
        if (band >= 38 || i % lstep === 0) gg.appendChild(h("text", { class: "val", x: cx, y: y2 + h2 - bh - 4, "text-anchor": "middle", text: Math.round(p[1] * 100) + "%" }));
        svg.appendChild(gg);
      });
      var hit = h("rect", { class: "hit", x: left + band * i, y: top - 10, width: band, height: Ht - top, tabindex: "0", role: "img",
        "aria-label": y.year + ": " + y.collections + " collections" });
      JU.attachTip(hit, function () {
        var lines = LOCKEYS.filter(function (k) { return y.media_location && y.media_location[k]; }).map(function (k) { return JU.LOCMAP[k].label + " " + JU.pct(y.media_location[k], N); });
        return "<b>" + y.year + " (" + JU.fmt(y.collections) + " collections)</b>" + lines.join("<br>") + "<br>Metadata or media fails today: " + JU.pct((L.dead || 0) + (L.degraded || 0), N) + "<br>Outside the fully on-chain candidate set: " + JU.pct(N - (S.yes || 0), N);
      });
      svg.appendChild(hit);
      rows.push([String(y.year), y.collections, JU.pct(JU.sum(y.media_location, ["data-uri", "onchain-renderer"]), N), JU.pct((L.dead || 0) + (L.degraded || 0), N), JU.pct(N - (S.yes || 0), N)]);
    });
    root.appendChild(h("div", { class: "year-chart", tabindex: "0", "aria-label": "By-year chart; all deployment cohorts" }, svg));
    root.appendChild(h("p", { class: "hnote", text: "Years through 2020 each have n < 30 and are pooled, matching the paper and cards. Each bar shows its sample size. Deploy year is a proxy for mint year." }));
    root.appendChild(dataTable(["Deploy year", "Collections", "Media on-chain", "Metadata/media fails today", "Outside fully on-chain candidate set"], rows));
    // takeaway: compare earliest and latest well-populated years
    var big = Y.filter(function (y) { return y.collections >= 30; });
    if (big.length >= 2) {
      var a = big[0], b = big[big.length - 1];
      var sa = (a.survival && a.survival.yes) || 0, sb = (b.survival && b.survival.yes) || 0;
      var da = ((a.liveness.dead || 0) + (a.liveness.degraded || 0));
      var db = ((b.liveness.dead || 0) + (b.liveness.degraded || 0));
      T("#t-year", "Among " + a.year + " deployments (n=" + a.collections + "), <b>" + JU.pct(da, a.collections, 1) + "</b> have metadata or sampled media that no longer loads and <b>" + JU.pct(sa, a.collections) + "</b> are fully on-chain candidates. For " + b.year + " (n=" + b.collections + "): <b>" + JU.pct(db, b.collections, 1) + "</b> and <b>" + JU.pct(sb, b.collections, 1) + "</b>.");
    } else T("#t-year", "Collections grouped by the year their contract was deployed.");
  }

  /* ---------- E. gateways ---------- */
  function renderGateways(c) {
    var root = JU.$("#ch-gw"); root.innerHTML = "";
    var G = (c.gateways || []).slice().sort(function (a, b) { return b.collections - a.collections; }).slice(0, 8);
    if (!G.length) { T("#t-gw", "No hardcoded gateways were recorded."); return; }
    var max = G[0].collections || 1;
    var kindColor = { "ipfs-gateway": locColor("ipfs"), "arweave-gateway": locColor("arweave"), cdn: locColor("http"), api: locColor("http"), other: locColor("broken") };
    var kinds = {}; G.forEach(function (g) { kinds[g.kind] = 1; });
    var kindName = { "ipfs-gateway": "IPFS gateway", "arweave-gateway": "Arweave gateway", cdn: "CDN", api: "API", other: "Other host" };
    root.appendChild(legend(Object.keys(kinds).map(function (k) { return { label: kindName[k] || k, color: kindColor[k] || locColor("broken") }; })));
    root.appendChild(h("div", { class: "hbars gateway-bars" }, G.map(function (g) {
      var row = h("div", { class: "hrow" }, h("span", { class: "name", text: g.host }),
        h("span", { class: "track", style: "--c:" + (kindColor[g.kind] || locColor("broken")) }, h("i", { style: "width:" + (100 * g.dead_collections / max) + "%" })),
        h("span", { class: "val", text: JU.fmt(g.collections) + " (" + JU.fmt(g.dead_collections) + " content failures)" }));
      // the pale track length encodes total: shrink the whole track to its share of the max
      row.querySelector(".track").style.width = (100 * g.collections / max) + "%";
      row.querySelector(".track i").style.width = (g.collections ? 100 * g.dead_collections / g.collections : 0) + "%";
      return row;
    })));
    root.appendChild(h("p", { class: "hnote", text: "Pale bar: collections that hardcode this host. Solid part: content gone or partly gone for any reason, including failures unrelated to the gateway. These are not gateway-caused failure counts. Lighthouse refused our client (402 Payment Required); that does not establish a dead gateway." }));
    root.appendChild(dataTable(["Host", "Kind", "Collections", "Content gone/partly gone (any reason)"], G.map(function (g) { return [g.host, g.kind, g.collections, g.dead_collections]; })));
    var top = G[0];
    var exact = JU.data.headlines && JU.data.headlines.random.exact_url.by_gateway_host;
    var ipfs = exact && exact.filter(function (g) { return g.host === "ipfs.io"; })[0];
    T("#t-gw", "<b>" + JU.esc(top.host) + "</b> is baked into <b>" + JU.fmt(top.collections) + "</b> collections' URLs; <b>" + JU.fmt(top.dead_collections) + "</b> have content gone or partly gone for any reason. IPFS and Arweave content may remain retrievable through another gateway even when a hardcoded URL fails." + (ipfs ? " For <b>ipfs.io</b>, <b>" + JU.fmt(ipfs.exact_unknown) + " of " + JU.fmt(ipfs.collections) + "</b> exact URLs (" + JU.pct(ipfs.exact_unknown, ipfs.collections, 1) + ") were <b>unknown</b>, mainly because our client was blocked." : ""));
  }

  /* ---------- F. claims ---------- */
  function renderClaims(c) {
    var root = JU.$("#ch-claims"); root.innerHTML = "";
    var CL = JU.data.mutability && JU.data.mutability.claims;
    var ex = JU.$("#exhibits"); ex.innerHTML = "";
    if (!CL) {
      T("#t-claims", "The reviewed claims data did not load. See data/mutability.json.");
      return;
    }
    var V = CL.outcomes, N = CL.claimants;
    root.appendChild(legend(JU.VERD.map(function (v) { return { label: v.label, color: VERD_COLOR[v.key], icon: v.icon, count: V[v.outcome] }; })));
    root.appendChild(sbar(JU.VERD.map(function (v) { return { key: v.key, label: v.label, value: V[v.outcome], color: VERD_COLOR[v.key] }; }), N));
    root.appendChild(dataTable(["Reviewed outcome", "Collections"], JU.VERD.map(function (v) { return [v.label, V[v.outcome]]; })));
    root.appendChild(h("details", { class: "view-table" }, h("summary", { text: "What the outcomes mean" }),
      h("dl", null, JU.VERD.map(function (v) { return h("div", null, h("dt", { text: v.label }), h("dd", { text: CL.definitions[v.outcome] })); }))));
    root.appendChild(h("p", { class: "hnote" }, h("a", { href: JU.safeUrl(CL.evidence), rel: "noopener", text: "Reviewed outcomes and evidence" })));
    T("#t-claims", "<b>" + JU.fmt(N) + "</b> collections have accepted project-authored storage statements; <b>" + JU.fmt(CL.explicit) + "</b> explicitly say “100%”, “fully”, “entirely” or “completely” on-chain. Saved evidence supports <b>" + JU.fmt(V.holds) + "</b> statements; <b>" + JU.fmt(V["onchain-data-offchain-pointer"]) + "</b> have on-chain data with an off-chain pointer; <b>" + JU.fmt(V.contradicted) + "</b> are contradicted and <b>" + JU.fmt(V.unverifiable) + "</b> remain unverifiable. “Contradicted” required affirmative evidence; in two explicit or near-explicit cases (Killer GF and Fluffy Polar Bears) the sampled image is off-chain and no alternate data contract was found, so they are counted unverifiable. Zero demonstrated contradictions does not mean every claim checked out.");
    renderExhibits(CL.examples);
  }
  function renderExhibits(rows) {
    var ex = JU.$("#exhibits"); ex.innerHTML = "";
    rows.forEach(function (r) {
      var key = JU.claimVerdict(r);
      var v = JU.VERD.filter(function (x) { return x.key === key; })[0];
      ex.appendChild(h("li", null,
        h("blockquote", { text: "\u201c" + r.text.replace(/\[([^\]]+)\]\(https?:\/\/[^)]+\)/g, "$1") + "\u201d" }),
        h("div", { class: "meta" },
          h("span", { class: "st " + v.cls }, h("span", { class: "ic", "aria-hidden": "true", text: v.icon }), v.label), " ",
          r.name + ": " + r.reason + " ",
          h("a", { href: JU.safeUrl(r.source_url), rel: "noopener", text: "where it says so" }), " ",
          h("a", { href: JU.safeUrl(r.evidence_url), rel: "noopener", text: "our evidence" }))));
    });
  }

  /* ---------- G. table ---------- */
  var COLS = [
    { k: "name", label: "Collection" },
    { k: "standard", label: "Std" },
    { k: "holders", label: "Holders", num: true },
    { k: "deploy_year", label: "Year", num: true },
    { k: "metadata_class", label: "Metadata" },
    { k: "media_class", label: "Media" },
    { k: "liveness", label: "Today" },
    { k: "survives_unplugged", label: "Unplugged" },
    { k: "claim", label: "Claim" },
    { k: "evidence_url", label: "Links", nosort: true }
  ];
  var tbl = { q: "", meta: "", media: "", live: "", surv: "", year: "", claim: "", key: "holders", dir: -1, shown: 80, rows: [], filtered: [] };

  function opt(sel, items, anyLabel) {
    sel.innerHTML = "";
    sel.appendChild(h("option", { value: "", text: anyLabel }));
    items.forEach(function (i) { sel.appendChild(h("option", { value: i[0], text: i[1] })); });
  }
  function chip(k) { var l = JU.LOCMAP[k]; return h("span", { class: "chipc", style: "--c:" + locColor(k) }, h("i"), l ? l.label : k); }
  function stat(list, k) {
    var o = list.filter(function (x) { return x.key === k; })[0] || { label: k, icon: "?", cls: "unk" };
    return h("span", { class: "st " + o.cls }, h("span", { class: "ic", "aria-hidden": "true", text: o.icon }), o.label);
  }
  function claimRank(r) { return r.claim ? { holds: 1, partial: 2, fails: 3, unverified: 4 }[JU.claimVerdict(r.claim)] || 5 : 0; }

  function applyFilters() {
    var q = tbl.q.trim().toLowerCase();
    tbl.filtered = tbl.rows.filter(function (r) {
      if (q && r.name.toLowerCase().indexOf(q) < 0 && r.address.toLowerCase().indexOf(q) < 0) return false;
      if (tbl.meta && r.metadata_class !== tbl.meta) return false;
      if (tbl.media && r.media_class !== tbl.media) return false;
      if (tbl.live && r.liveness !== tbl.live) return false;
      if (tbl.surv && r.survives_unplugged !== tbl.surv) return false;
      if (tbl.year && String(r.deploy_year) !== tbl.year) return false;
      if (tbl.claim === "any" && !r.claim) return false;
      if (tbl.claim === "none" && r.claim) return false;
      if (tbl.claim && tbl.claim !== "any" && tbl.claim !== "none" && !(r.claim && JU.claimVerdict(r.claim) === tbl.claim)) return false;
      return true;
    });
    var k = tbl.key, d = tbl.dir;
    tbl.filtered.sort(function (a, b) {
      var x, y;
      if (k === "claim") { x = claimRank(a); y = claimRank(b); }
      else if (k === "metadata_class" || k === "media_class") { x = LOCKEYS.indexOf(a[k]); y = LOCKEYS.indexOf(b[k]); }
      else { x = a[k]; y = b[k]; if (typeof x === "string") { x = x.toLowerCase(); y = String(y).toLowerCase(); } }
      return (x < y ? -1 : x > y ? 1 : 0) * d || (b.holders - a.holders);
    });
  }
  function renderRows() {
    var body = JU.$("#coll-table tbody"); body.innerHTML = "";
    var list = tbl.filtered.slice(0, tbl.shown);
    var frag = document.createDocumentFragment();
    list.forEach(function (r) {
      var cl = r.claim ? stat(JU.VERD, JU.claimVerdict(r.claim)) : h("span", { class: "st unk", text: "-" });
      if (r.claim) cl.title = r.claim.text;
      frag.appendChild(h("tr", { class: r.survives_unplugged === "yes" ? "" : "gone" },
        h("td", { title: r.address }, h("span", { class: "nm", text: r.name }), r._x ? h("span", { class: "xtag", title: "High-holder collection outside the random sample; not part of any percentage", text: "outside sample" }) : null),
        h("td", { text: r.standard }),
        h("td", { class: "num", text: JU.fmt(r.holders) }),
        h("td", { class: "num", text: String(r.deploy_year) }),
        h("td", null, chip(r.metadata_class)),
        h("td", null, chip(r.media_class)),
        h("td", { title: r.dead_reason ? JU.reasonLabel(r.dead_reason) : "" }, r.liveness === "dead" ? h("span", { class: "st warn", text: JU.reasonLabel(r.dead_reason) }) : stat(JU.LIVE, r.liveness)),
        h("td", null, stat(JU.SURV, r.survives_unplugged)),
        h("td", null, cl),
        h("td", { class: "lnk" },
          r.evidence_url ? h("a", { href: JU.safeUrl(r.evidence_url), rel: "noopener", text: "evidence" }) : null,
          h("a", { href: "https://etherscan.io/address/" + encodeURIComponent(r.address), rel: "noopener", text: "etherscan" }))));
    });
    body.appendChild(frag);
    var total = tbl.rows.length, n = tbl.filtered.length;
    var xn = tbl.rows.filter(function (r) { return r._x; }).length, xnote = xn ? " Rows tagged \u201coutside sample\u201d (" + JU.fmt(xn) + ") are high-holder collections added for browsing; they are not part of any percentage on this page." : "";
    JU.$("#table-count").textContent = (n === total ? "Showing " + JU.fmt(Math.min(list.length, n)) + " of " + JU.fmt(total) + " collections." : JU.fmt(n) + " of " + JU.fmt(total) + " collections match. Showing " + JU.fmt(list.length) + ".") + xnote;
    JU.$("#more-rows").hidden = list.length >= n;
    JU.$("#more-rows").textContent = "Show " + JU.fmt(Math.min(200, n - list.length)) + " more";
    JU.$$("#coll-table th").forEach(function (th) { th.setAttribute("aria-sort", th.getAttribute("data-k") === tbl.key ? (tbl.dir > 0 ? "ascending" : "descending") : "none"); });
  }
  function refresh() { tbl.shown = 80; applyFilters(); renderRows(); }
  function csv() {
    var head = ["address", "name", "standard", "holders", "deploy_year", "metadata_class", "media_class", "liveness", "dead_reason", "survives_unplugged", "claim_verdict", "claim_text", "evidence_url", "in_random_sample"];
    var q = function (v) { v = v === null || v === undefined ? "" : String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
    var lines = [head.join(",")].concat(tbl.filtered.map(function (r) {
      return [r.address, r.name, r.standard, r.holders, r.deploy_year, r.metadata_class, r.media_class, r.liveness, r.dead_reason, r.survives_unplugged, r.claim && JU.claimVerdict(r.claim), r.claim && r.claim.text, r.evidence_url, r._x ? "no" : "yes"].map(q).join(",");
    }));
    var a = h("a", { href: URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" })), download: "jpeg-unplugged-collections.csv" });
    document.body.appendChild(a); a.click(); a.remove();
  }
  function initTable() {
    var rows = JU.data.collections && JU.data.collections.collections;
    if (!rows) { T("#t-table", "collections.json did not load, so the table is empty."); return; }
    tbl.rows = rows;
    var head = JU.$("#coll-table thead"); head.innerHTML = "";
    head.appendChild(h("tr", null, COLS.map(function (c) {
      var th = h("th", { scope: "col", class: c.num ? "num" : "", "data-k": c.k, "aria-sort": "none" });
      if (c.nosort) th.textContent = c.label;
      else th.appendChild(h("button", { type: "button", text: c.label, onclick: function () { if (tbl.key === c.k) tbl.dir = -tbl.dir; else { tbl.key = c.k; tbl.dir = c.num ? -1 : 1; } refresh(); } }));
      return th;
    })));
    function buildOpts() {
      var years = {}; tbl.rows.forEach(function (r) { years[r.deploy_year] = 1; });
      var locs = function (field) { var seen = {}; tbl.rows.forEach(function (r) { seen[r[field]] = 1; }); return JU.LOC.filter(function (l) { return seen[l.key]; }).map(function (l) { return [l.key, l.label]; }); };
      opt(JU.$("#f-meta"), locs("metadata_class"), "Any");
      opt(JU.$("#f-media"), locs("media_class"), "Any");
      opt(JU.$("#f-year"), Object.keys(years).sort().map(function (y) { return [y, y]; }), "Any");
      JU.$("#f-meta").value = tbl.meta; JU.$("#f-media").value = tbl.media; JU.$("#f-year").value = tbl.year;
    }
    buildOpts();
    if (JU.hasExtra()) {
      var xw = JU.$("#f-extra-wrap"), xb = JU.$("#f-extra"); xw.hidden = false;
      xb.addEventListener("change", function () {
        if (!xb.checked) { tbl.rows = rows; buildOpts(); refresh(); return; }
        xb.disabled = true;
        JU.loadExtra().then(function (d) {
          xb.disabled = false;
          if (!d || !d.collections) { xb.checked = false; JU.$("#table-count").textContent = "Could not load the high-holder collections."; return; }
          d.collections.forEach(function (r) { r._x = 1; });
          tbl.rows = rows.concat(d.collections); buildOpts(); refresh();
        });
      });
    }
    opt(JU.$("#f-live"), JU.LIVE.map(function (l) { return [l.key, l.label]; }), "Any");
    opt(JU.$("#f-surv"), JU.SURV.map(function (l) { return [l.key, l.label]; }), "Any");
    opt(JU.$("#f-claim"), [["any", "Makes a claim"]].concat(JU.VERD.map(function (v) { return [v.key, v.label]; }), [["none", "No claim"]]), "Any");
    var wire = { "#f-meta": "meta", "#f-media": "media", "#f-live": "live", "#f-surv": "surv", "#f-year": "year", "#f-claim": "claim" };
    Object.keys(wire).forEach(function (sel) { JU.$(sel).addEventListener("change", function (e) { tbl[wire[sel]] = e.target.value; refresh(); }); });
    var qT; JU.$("#f-q").addEventListener("input", function (e) { clearTimeout(qT); qT = setTimeout(function () { tbl.q = e.target.value; refresh(); }, 120); });
    JU.$("#f-reset").addEventListener("click", function () {
      tbl.q = tbl.meta = tbl.media = tbl.live = tbl.surv = tbl.year = tbl.claim = ""; JU.$("#f-q").value = "";
      ["#f-meta", "#f-media", "#f-live", "#f-surv", "#f-year", "#f-claim"].forEach(function (s) { JU.$(s).value = ""; }); refresh();
    });
    JU.$("#f-csv").addEventListener("click", csv);
    JU.$("#more-rows").addEventListener("click", function () { tbl.shown += 200; renderRows(); });
    T("#t-table", "Search, filter and sort all <b>" + JU.fmt(rows.length) + "</b> " + (JU.sampleInfo() ? "sampled " : "") + "collections. Each row links to its call and fetch records (URL, status, time and SHA-256), loaded only when opened. Unplugged, rows outside the fully on-chain candidate set fade.");
    refresh();
  }

  /* ---------- orchestration ---------- */
  function renderLede() {
    var si = JU.sampleInfo(), el = JU.$("#census-lede"), ms = JU.$("#m-sample"); if (ms) ms.hidden = !si; if (!el || !si) return;
    el.textContent = "A uniform random sample of " + JU.fmt(si.n) + " of the " + JU.fmt(si.universe) + " non-spam Ethereum NFT collections with at least 100 holders, and what each one's token pointers point at. Percentages are shares of the sample.";
  }
  function renderAll() {
    renderLede();
    var c = JU.data.census, err = JU.$("#census-error");
    err.hidden = true;
    if (JU.data.errors.census) {
      err.hidden = false;
      err.innerHTML = "<b>Could not load the census.</b> <code>" + JU.esc(JU.data.errors.census.path) + "</code>: " + JU.esc(JU.data.errors.census.message) + "." + JU.esc(JU.fileHint);
    } else {
      var miss = JU.missingKeys(c);
      if (miss.length) { err.hidden = false; err.innerHTML = "<b>census.json is missing required keys:</b> <code>" + JU.esc(miss.join(", ")) + "</code>. See data/SCHEMA.md."; }
      else {
        [renderWhere, renderAlive, renderFake, renderYear, renderGateways, renderClaims].forEach(function (f) {
          try { f(c); } catch (e) { console.error(f.name, e); err.hidden = false; err.innerHTML += "<div>Chart " + JU.esc(f.name) + " failed: " + JU.esc(e.message) + "</div>"; }
        });
        markActiveRow(); JU.fitLabels(document);
      }
    }
    initTable();
  }
  JU.ui = { legend: legend, sbar: sbar, brow: brow, dataTable: dataTable, T: T };
  JU.initCensus = function () {
    renderAll();
    JU.onPower(markActiveRow);
    JU.afterResize.push(function () { if (JU.data.census && !JU.missingKeys(JU.data.census).length) { try { renderYear(JU.data.census); } catch (e) { console.error(e); } } });
    JU.onTheme.push(function () { if (JU.data.census && !JU.missingKeys(JU.data.census).length) { renderWhere(JU.data.census); renderAlive(JU.data.census); renderFake(JU.data.census); renderYear(JU.data.census); renderGateways(JU.data.census); renderClaims(JU.data.census); markActiveRow(); JU.fitLabels(document); } });
  };
})();
