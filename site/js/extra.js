/* extra.js - "who holds the pen" (data/mutability.json) and "dead and claimable servers" (data/hosts.json, hidden until it exists).
   Every number comes from the JSON. Hosts data is aggregate only. */
(function () {
  "use strict";
  var JU = window.JU, h = JU.h;

  /* ---------------- mutability ---------------- */
  var CLS = [
    { key: "immutable", label: "No live mutator found", css: "--ink" },
    { key: "dao-or-timelock-mutable", label: "DAO or timelock", css: "--c-data-uri" },
    { key: "multisig-mutable", label: "Multisig", css: "--c-onchain-renderer" },
    { key: "eoa-mutable", label: "EOA mutation (including data edits)", css: "--c-http" },
    { key: "unknown", label: "Unresolved", css: "--c-broken" }
  ];
  function clsColor(k) { var c = CLS.filter(function (x) { return x.key === k; })[0]; return JU.css(c ? c.css : "--c-broken"); }
  function segs(counts) { return CLS.map(function (c) { return { key: c.key, label: c.label, value: counts[c.key] || 0, color: clsColor(c.key) }; }); }
  var SHAPES = { "renderer-swap": "●", "uri-pointer": "◆", "descriptor-update": "○", sealed: "■" };
  var SHAPELAB = { "renderer-swap": "Renderer address set", "uri-pointer": "Base URI set", "descriptor-update": "Descriptor replaced", sealed: "Sealed" };

  function renderTimeline(M) {
    var root = JU.$("#ch-ptime"); root.innerHTML = "";
    var T = M.timeline || [], L = M.lanes || [];
    if (!T.length) return;
    var kinds = {}; T.forEach(function (t) { kinds[t.kind] = 1; });
    root.appendChild(h("ul", { class: "legend" }, Object.keys(kinds).map(function (k) { return h("li", null, h("span", { class: "ico", "aria-hidden": "true", style: "color:" + JU.css("--ink-2"), text: SHAPES[k] }), SHAPELAB[k] || k); })));
    var W = Math.max(320, root.clientWidth || 520), labW = W < 460 ? 92 : 120, right = 10, rowH = 32, top = 8, axisH = 24;
    var d0 = new Date(T[0].date.slice(0, 4) + "-01-01").getTime();
    var dl = new Date(T[T.length - 1].date).getTime();
    var endY = new Date(dl).getUTCFullYear() + 1, d1 = new Date(endY + "-01-01").getTime();
    var x = function (d) { return labW + (new Date(d).getTime() - d0) / (d1 - d0) * (W - labW - right); };
    var H = top + L.length * rowH + axisH;
    var svg = h("svg", { class: "yearsvg tl", viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Timeline of pointer changes by collection; a table follows." });
    for (var y = new Date(d0).getUTCFullYear(); y < endY; y++) {
      var gx = x(y + "-01-01");
      svg.appendChild(h("line", { class: "grid", x1: gx, x2: gx, y1: top, y2: top + L.length * rowH }));
      if ((endY - new Date(d0).getUTCFullYear()) < 8 || (y % 2 === 0)) svg.appendChild(h("text", { x: gx + 3, y: H - 6, text: String(y) }));
    }
    L.forEach(function (l, i) {
      var cy = top + i * rowH + rowH / 2, col = clsColor(l.class);
      svg.appendChild(h("line", { class: "grid", x1: labW, x2: W - right, y1: cy, y2: cy }));
      svg.appendChild(h("text", { x: labW - 8, y: cy + 4, "text-anchor": "end", class: "lane-label", text: l.lane }));
      var same = {};
      T.filter(function (t) { return t.lane === l.lane; }).forEach(function (t) {
        var n = same[t.date] = (same[t.date] || 0) + 1;
        var cx = x(t.date) + (n - 1) * 11, g = h("g", { tabindex: "0", role: "img", "aria-label": l.lane + ", " + t.date + ": " + t.what });
        var r = 6, surf = JU.css("--paper");
        if (t.kind === "renderer-swap") g.appendChild(h("circle", { cx: cx, cy: cy, r: r, fill: col, stroke: surf, "stroke-width": 2 }));
        else if (t.kind === "descriptor-update") g.appendChild(h("circle", { cx: cx, cy: cy, r: r - 1, fill: surf, stroke: col, "stroke-width": 3 }));
        else if (t.kind === "uri-pointer") g.appendChild(h("rect", { x: cx - 5, y: cy - 5, width: 10, height: 10, fill: col, stroke: surf, "stroke-width": 2, transform: "rotate(45 " + cx + " " + cy + ")" }));
        else g.appendChild(h("rect", { x: cx - 6, y: cy - 6, width: 12, height: 12, rx: 2, fill: col, stroke: surf, "stroke-width": 2 }));
        g.appendChild(h("circle", { cx: cx, cy: cy, r: 11, fill: "transparent" }));
        JU.attachTip(g, function () { return "<b>" + JU.esc(l.lane) + "</b>" + JU.esc(t.date) + "<br>" + JU.esc(t.what); });
        svg.appendChild(g);
      });
    });
    root.appendChild(svg);
    var rows = T.map(function (t) {
      return h("tr", null, h("th", { scope: "row", text: t.date }), h("td", { text: t.lane }), h("td", { text: t.what }),
        h("td", null, h("a", { href: "https://etherscan.io/tx/" + encodeURIComponent(t.tx), rel: "noopener", text: "transaction" })));
    });
    root.appendChild(h("details", { class: "view-table" }, h("summary", { text: "View as table" }),
      h("div", { class: "scroll" }, h("table", null, h("thead", null, h("tr", null, ["Date", "Collection", "Change", "Evidence"].map(function (x) { return h("th", { scope: "col", text: x }); }))), h("tbody", null, rows)))));
    root.appendChild(h("p", { class: "hnote" }, h("a", { href: JU.safeUrl(M.timeline_evidence), rel: "noopener", text: "Setter history data" })));
    var ul = JU.$("#pen-lanes"); ul.innerHTML = "";
    L.forEach(function (l) {
      var c = CLS.filter(function (k) { return k.key === l.class; })[0];
      ul.appendChild(h("li", null, h("span", { class: "chipc", style: "--c:" + clsColor(l.class) }, h("i"), h("b", { text: l.lane })), " ",
        h("span", { class: "lane-class", text: "(" + (l.class_label || (c ? c.label.toLowerCase() : l.class)) + ") " }), l.summary + " ",
        h("a", { href: JU.safeUrl(l.evidence), rel: "noopener", text: "evidence" })));
    });
  }

  function renderPen(M) {
    var sec = JU.$("#pen");
    var N = M.universe.contracts, C = M.classes, F = M.funnel, P = M.pointer_power, B = M.by_claim;
    JU.$("#pen-lede").textContent = "The historical mutation audit covers " + JU.fmt(N) + " contracts. We distinguish live URI, renderer and upgrade control from broader data edits. Storage outcomes are assessed separately: a live controller does not refute an on-chain storage statement.";
    var root = JU.$("#ch-pclass"); root.innerHTML = "";
    root.appendChild(JU.ui.legend(CLS.map(function (c) { return { label: c.label, color: clsColor(c.key), count: C[c.key] || 0 }; })));
    var groups = [
      ["All audited contracts", C],
      ["Explicit “100%” / “fully” claims", B.explicit],
      ["Generic on-chain claims", B.generic],
      ["Storage-forever claims", B.forever],
      ["No accepted reviewed claim", B.none]
    ];
    groups.forEach(function (g) { root.appendChild(JU.ui.brow(g[0], JU.fmt(g[1].total), JU.ui.sbar(segs(g[1]), g[1].total))); });
    root.appendChild(JU.ui.dataTable(["Group", "Contracts"].concat(CLS.map(function (c) { return c.label; })),
      groups.map(function (g) { return [g[0], g[1].total].concat(CLS.map(function (c) { return g[1][c.key] || 0; })); })));
    JU.$("#t-pclass").innerHTML = "<b>" + JU.fmt(P.eoa) + "</b> of " + JU.fmt(N) + " contracts (" + JU.pct(P.eoa, N) + ") have live pointer control by a single EOA. The broader EOA-mutable class contains <b>" + JU.fmt(M.broad_eoa_mutable) + "</b>, including data-only edits. <b>" + JU.fmt(C.immutable) + "</b> have no live mutator found, <b>" + JU.fmt(C["multisig-mutable"]) + "</b> are broadly multisig-mutable, <b>" + JU.fmt(C["dao-or-timelock-mutable"]) + "</b> DAO/timelock-mutable, and <b>" + JU.fmt(C.unknown) + "</b> unresolved. Classes include the recorded renderer dependencies and are broader than repointing.";
    var f = JU.$("#ch-pfunnel"); f.innerHTML = "";
    var col = clsColor("eoa-mutable");
    var rowsF = [["Reviewed claimants", F.claimants, F.claimants_repointable], ["Explicit “100%” / “fully”", F.explicit, F.explicit_repointable]];
    f.appendChild(h("div", { class: "hbars funnel" }, rowsF.map(function (r) {
      return h("div", { class: "hrow" }, h("span", { class: "name sans", text: r[0] }),
        h("span", { class: "track", style: "--c:" + col + ";width:" + (100 * r[1] / F.claimants) + "%" }, h("i", { style: "width:" + (r[1] ? 100 * r[2] / r[1] : 0) + "%" })),
        h("span", { class: "val", text: JU.fmt(r[2]) + " of " + JU.fmt(r[1]) }));
    })));
    f.appendChild(h("p", { class: "hnote", text: "Solid part: a live EOA or multisig account can repoint the ordinary metadata/art path. A multisig may require several signatures. Data-only edits are excluded." }));
    f.appendChild(h("p", { class: "hnote", text: F.definition }));
    f.appendChild(h("p", { class: "hnote", text: "Across the historical audit, live pointer control is EOA-held in " + JU.fmt(P.eoa) + " contracts, multisig-held in " + JU.fmt(P.multisig) + ", and DAO/timelock-held in " + JU.fmt(P["dao-or-timelock"]) + ". " + JU.fmt(P.none) + " contracts have no live pointer setter recorded." }));
    f.appendChild(JU.ui.dataTable(["Measure", "Contracts"], [["Reviewed claimants", F.claimants], ["Claimants repointable by EOA or multisig", F.claimants_repointable], ["Explicit claimants", F.explicit], ["Explicit repointable by EOA or multisig", F.explicit_repointable], ["Claimants with data-only mutation", F.data_only_mutable], ["Audit: EOA pointer control", P.eoa], ["Audit: multisig pointer control", P.multisig], ["Audit: DAO/timelock pointer control", P["dao-or-timelock"]], ["Audit: no live pointer setter", P.none]]));
    JU.$("#t-pfunnel").innerHTML = "<b>" + JU.fmt(F.claimants_repointable) + "</b> of " + JU.fmt(F.claimants) + " reviewed claimants (" + JU.pct(F.claimants_repointable, F.claimants) + ") are repointable by a live EOA or multisig account. Among the <b>" + JU.fmt(F.explicit) + "</b> explicit claimants, <b>" + JU.fmt(F.explicit_repointable) + "</b> are (" + JU.fmt(F.explicit_repointable_eoa) + " through an EOA). This measures capability, not an observed art change or a false storage claim.";
    JU.$("#t-ptime").textContent = "The saved audit records renderer-address changes for " + JU.fmt(M.swaps_observed) + " contracts. The selected history below contains only entries in setter_events.csv; dates and transaction links refer to those rows.";
    renderTimeline(M);
    sec.hidden = false;
    JU.fitLabels(sec);
  }

  /* ---------------- hosts (aggregate counts only) ---------------- */
  var HSTAT = [
    ["live", "Answers", "#0ca30c"], ["dns-nxdomain", "Name no longer resolves", "#d03b3b"], ["tls-error", "Certificate or TLS failure", "#ec835a"],
    ["http-error", "Answers with an error", "#fab219"], ["parked", "Parked or repurposed", "#8f6bd6"], ["unknown", "Unknown", "#9aa0a8"]
  ];
  function renderHosts(H) {
    var sec = JU.$("#hosts"), T = H.totals, S = H.by_status;
    JU.$("#hosts-lede").textContent = "NFT metadata and images often live behind a hostname someone has to keep paying for. We counted the hostnames the census collections point at, whether they still answer, and which show missing-resource or missing-registration evidence.";
    var root = JU.$("#ch-hstatus"); root.innerHTML = "";
    var known = {}; HSTAT.forEach(function (s) { known[s[0]] = 1; });
    var list = HSTAT.filter(function (s) { return S[s[0]]; }).concat(Object.keys(S).filter(function (k) { return !known[k]; }).map(function (k) { return [k, k, "#9aa0a8"]; }));
    root.appendChild(JU.ui.legend(list.map(function (s) { return { label: s[1], color: s[2], count: S[s[0]] }; })));
    root.appendChild(JU.ui.sbar(list.map(function (s) { return { key: s[0], label: s[1], value: S[s[0]], color: s[2], extra: "hostnames" }; }), T.hosts));
    root.appendChild(JU.ui.dataTable(["Status", "Hostnames"], list.map(function (s) { return [s[1], S[s[0]]]; })));
    var gone = T.hosts - (S.live || 0) - (S.unknown || 0);
    JU.$("#t-hstatus").innerHTML = "The census collections point at <b>" + JU.fmt(T.hosts) + "</b> distinct hostnames" + (T.collections ? " across <b>" + JU.fmt(T.collections) + "</b> collections" : "") + ". Today <b>" + JU.fmt(S.live || 0) + "</b> answer and <b>" + JU.fmt(gone) + "</b> are gone or failing.";
    var tk = JU.$("#ch-htakeover"); tk.innerHTML = "";
    var K = H.takeover;
    if (K && K.evidence_counts) {
      var E = K.evidence_counts;
      var evidenceRows = [
        ["Cloud-resource candidates", E.cloud_candidates],
        ["Registry RDAP 404", E.registry_404],
        ["DNS-only availability candidates", E.dns_only],
        ["Registration after deployment candidates", E.registration_after_deploy]
      ];
      var maximum = Math.max.apply(null, evidenceRows.map(function (r) { return r[1] || 0; })) || 1;
      tk.appendChild(h("div", { class: "hbars gateway-bars" }, evidenceRows.map(function (r) {
        return h("div", { class: "hrow" }, h("span", { class: "name sans", text: r[0] }),
          h("span", { class: "track", style: "--c:" + JU.css("--c-http") }, h("i", { style: "width:" + (100 * (r[1] || 0) / maximum) + "%" })),
          h("span", { class: "val", text: JU.fmt(r[1]) }));
      })));
      tk.appendChild(JU.ui.dataTable(["Evidence", "Hostnames"], evidenceRows));
      JU.$("#t-htakeover").textContent = "The " + JU.fmt(E.cloud_candidates) + " cloud candidates look like deleted cloud resources (195 with a provider missing-resource response, 9 DNS-only). Their names may be re-creatable; reclaimability was not tested. Registry 404 is stronger evidence of a missing registration than DNS alone. Later registration dates are candidates for further checks. Evidence groups can overlap. Counts pool the random and high-holder strata. Hostnames are withheld.";
    } else if (K) {
      var rows = [["Missing-registration candidates", K.registrable_hosts, K.collections_affected]];
      if (K.dangling_hosts !== undefined) rows.push(["Subdomains pointing at a deleted third-party service", K.dangling_hosts, K.dangling_collections_affected]);
      if (K.expiring_soon_hosts !== undefined) rows.push(["Domains that expire within 90 days", K.expiring_soon_hosts, K.expiring_soon_collections_affected]);
      var max = Math.max.apply(null, rows.map(function (r) { return r[1] || 0; })) || 1;
      tk.appendChild(h("div", { class: "hbars funnel" }, rows.map(function (r) {
        return h("div", { class: "hrow" }, h("span", { class: "name sans", text: r[0] }),
          h("span", { class: "track", style: "--c:" + JU.css("--c-http") }, h("i", { style: "width:" + (100 * (r[1] || 0) / max) + "%" })),
          h("span", { class: "val", text: JU.fmt(r[1]) + (r[2] !== undefined ? " hostnames, " + JU.fmt(r[2]) + " collections" : "") }));
      })));
      tk.appendChild(JU.ui.dataTable(["Measure", "Hostnames", "Collections"], rows.map(function (r) { return [r[0], r[1], r[2] === undefined ? "-" : r[2]]; })));
      JU.$("#t-htakeover").innerHTML = "<b>" + JU.fmt(K.registrable_hosts) + "</b> hostnames have missing-registration evidence; <b>" + JU.fmt(K.collections_affected) + "</b> collections point at them. Reclaimability was not tested. This page gives counts only.";
    } else { JU.$("#c-htakeover").hidden = true; }
    var kinds = H.by_kind || [];
    JU.$("#c-hkind").hidden = !kinds.length;
    if (kinds.length) {
      var kr = JU.$("#ch-hkind"); kr.innerHTML = "";
      var mx = Math.max.apply(null, kinds.map(function (k) { return k.hosts; })) || 1;
      kr.appendChild(h("div", { class: "hbars" }, kinds.map(function (k) {
        var r = h("div", { class: "hrow" }, h("span", { class: "name sans", text: k.kind }),
          h("span", { class: "track", style: "--c:" + JU.css("--c-ipfs") }, h("i", { style: "width:" + (k.hosts ? 100 * (k.dead_hosts || 0) / k.hosts : 0) + "%" })),
          h("span", { class: "val", text: JU.fmt(k.hosts) + " hostnames (" + JU.fmt(k.dead_hosts || 0) + " gone)" }));
        r.querySelector(".track").style.width = (100 * k.hosts / mx) + "%"; return r;
      })));
      JU.$("#t-hkind").textContent = "Pale bar: hostnames of that kind. Solid part: of those, gone or failing today.";
    }
    var ex = H.examples || [];
    JU.$("#c-hex").hidden = !ex.length;
    var ol = JU.$("#hosts-examples"); ol.innerHTML = "";
    ex.forEach(function (e) {
      ol.appendChild(h("li", null, h("blockquote", { text: e.host }), h("div", { class: "meta" }, e.what + " ", e.source_url ? h("a", { href: JU.safeUrl(e.source_url), rel: "noopener", text: "source" }) : null)));
    });
    sec.hidden = false;
    JU.fitLabels(sec);
    var nav = JU.$("#nav-hosts"); if (nav) nav.hidden = false;
  }

  JU.initExtra = function () {
    var D = JU.data;
    try {
      if (D.mutability && D.mutability.classes) renderPen(D.mutability);
      else { JU.$("#pen").hidden = true; var n = JU.$("#nav-pen"); if (n) n.hidden = true; }
    } catch (e) { console.error("pen", e); }
    try { if (D.hosts && D.hosts.totals && D.hosts.by_status) renderHosts(D.hosts); } catch (e) { console.error("hosts", e); }
    JU.afterResize.push(function () { if (D.mutability && D.mutability.timeline) { try { renderTimeline(D.mutability); } catch (e) { console.error(e); } } });
    JU.onTheme.push(function () { if (D.mutability && D.mutability.classes) { try { renderPen(D.mutability); } catch (e) { console.error(e); } } });
  };
})();
