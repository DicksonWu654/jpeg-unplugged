/* The famous-collection panel uses its own snapshot, never census estimates. */
(function () {
  "use strict";
  var JU = window.JU, h = JU.h;
  var locations = { onchain: "On-chain", arweave: "Arweave", ipfs: "IPFS", http: "Web server", broken: "Broken" };
  var live = { alive: "Loads", dead: "Metadata unavailable", degraded: "Degraded delivery", unknown: "Unknown" };
  var control = { immutable: "No live contract edit path found", "eoa-mutable": "One key can edit", "multisig-mutable": "Multisig can edit", "dao-or-timelock-mutable": "DAO or timelock can edit", unknown: "Control unknown" };
  function route(r) {
    if (r.fully_onchain_all_declared_media) return "onchain";
    if (r.metadata_location === "broken") return "broken";
    var classes = r.media_classes.length ? r.media_classes : r.metadata_classes;
    return ["http", "ipfs", "arweave"].filter(function (k) { return classes.indexOf(k) >= 0; })[0] || "broken";
  }
  function locationLabel(value) {
    var names = { "data-uri": "On-chain data URI", "onchain-renderer": "On-chain renderer", "legacy-no-tokenURI": "Legacy data renderer", http: "Web server", ipfs: "IPFS", arweave: "Arweave", broken: "No usable metadata", unresolved: "Unresolved" };
    if (value.indexOf("mixed(") === 0) return value.slice(6, -1).split(",").map(locationLabel).join(" + ");
    return names[value] || value;
  }
  function receipt(r) { return "data/top100-evidence/" + r.contract + ".json"; }
  function field(dl, label, value) {
    dl.appendChild(h("dt", { text: label }));
    dl.appendChild(h("dd", null, value && value.nodeType ? value : String(value || "Unknown")));
  }
  function openRow(r) {
    var body = JU.$("#top100-detail-body"), dl = h("dl");
    body.replaceChildren(h("p", { class: "eyebrow", text: "Top 100 / #" + r.rank }), h("h3", { id: "top100-detail-title", text: r.name }));
    field(dl, "Metadata", locationLabel(r.metadata_location));
    field(dl, "Media", locationLabel(r.media_location));
    field(dl, "Liveness", live[r.liveness]);
    field(dl, "Who can change it", control[r.mutability_class]);
    field(dl, "Can one key repoint it?", r.single_key_repointable ? "Yes" : "No live one-key repointing path found");
    field(dl, "Pointer / renderer", r.base_uri_or_renderer);
    field(dl, "Contract", r.contract);
    field(dl, "Sample", r.samples + " token units; " + r.distinct_token_ids + " distinct IDs");
    field(dl, "Checked", r.refreshed_at);
    body.appendChild(dl);
    if (r.delivery_note) body.appendChild(h("p", { class: "top100-delivery-note", text: r.delivery_note }));
    if (r.sample_note) body.appendChild(h("p", { text: r.sample_note }));
    var details = h("details", null, h("summary", { text: "Control evidence" }));
    r.control.forEach(function (c) {
      details.appendChild(h("p", { text: c.contract + ": " + c.reason + (c.history_incomplete ? " (history incomplete)" : "") }));
    });
    body.appendChild(details);
    body.appendChild(h("p", null, h("a", { href: receipt(r), text: "Open saved evidence: samples, fetch results and packet hashes →" })));
    JU.$("#top100-detail").showModal();
  }
  JU.initTop100 = function () {
    var data = JU.data.top100;
    if (!data) {
      var err = JU.$("#top100-error"); err.hidden = false;
      err.textContent = "The top-100 snapshot could not load. Reload to try again.";
      return;
    }
    var rows = data.collections.slice().sort(function (a, b) { return a.rank - b.rank; }), counts = data.summary.counts;
    [
      ["fully_onchain_all_declared_media", "fully on-chain", "onchain"],
      ["dead_or_degraded", "already dead or degraded", "dead"],
      ["single_key_repointable", "one key can repoint", "key"],
      ["http_origin_dependency", "depend on someone’s web server", "server"]
    ].forEach(function (s) {
      JU.$("#top100-stats").appendChild(h("div", { class: "top100-stat top100-stat-" + s[2] }, h("strong", { text: counts[s[0]] }), h("span", { text: s[1] })));
    });
    Object.keys(locations).forEach(function (k) {
      JU.$("#top100-legend").appendChild(h("li", { class: "top100-color-" + k }, h("i", { "aria-hidden": "true" }), locations[k]));
    });
    rows.forEach(function (r) {
      var bad = r.liveness === "dead" || r.liveness === "degraded";
      var button = h("button", {
        type: "button", class: "top100-tile top100-color-" + route(r),
        "data-onchain": String(r.fully_onchain_all_declared_media),
        "aria-label": "#" + r.rank + " " + r.name + ". " + locations[route(r)] + ". " + live[r.liveness] + ". Open row and evidence.",
        onclick: function () { openRow(r); }
      }, h("span", { class: "top100-rank", text: "#" + r.rank }),
      h("span", { class: "top100-name", text: r.name }),
      bad ? h("span", { class: "top100-marker", "aria-hidden": "true", text: "×" }) : null);
      JU.$("#top100-wall").appendChild(h("li", null, button));
      var tr = h("tr", null, h("td", { text: r.rank }),
        h("th", { scope: "row" }, h("button", { type: "button", class: "top100-row-link", text: r.name, onclick: function () { openRow(r); } })),
        h("td", { text: locationLabel(r.metadata_location) }), h("td", { text: locationLabel(r.media_location) }),
        h("td", { text: live[r.liveness] }), h("td", { text: control[r.mutability_class] }),
        h("td", null, h("a", { href: receipt(r), text: "Evidence" })));
      JU.$("#top100-rows").appendChild(tr);
    });
    function callout(ranks, text) {
      var li = h("li");
      ranks.forEach(function (rank, i) {
        var r = rows[rank - 1];
        if (i) li.appendChild(document.createTextNode(" + "));
        li.appendChild(h("button", { type: "button", class: "top100-row-link", text: r.name + " (#" + r.rank + ")", onclick: function () { openRow(r); } }));
      });
      li.appendChild(document.createTextNode(" — " + text));
      JU.$("#top100-callouts").appendChild(li);
    }
    callout([2, 69], "on-chain routes survive the switch.");
    callout([1], "metadata and images live on IPFS.");
    callout([30], "sampled metadata failed DNS in both passes.");
    callout([68], "empty wrapper metadata; legacy artwork is a separate question.");
    callout([94], "degraded: two samples load, one returns 404.");
    JU.$("#top100-power").addEventListener("click", JU.togglePower);
    function power() {
      var off = JU.state.power === "off";
      JU.$("#top100-power").textContent = off ? "Plug it back in" : "Unplug the internet";
      JU.$("#top100-status").textContent = off ? counts.fully_onchain_all_declared_media + " of 100 stay lit. The rest need the internet." : "100 collections. Pull the plug.";
    }
    JU.onPower(power); power();
    var dialog = JU.$("#top100-detail");
    dialog.addEventListener("click", function (e) { if (e.target === dialog) { var box = dialog.getBoundingClientRect(); if (e.clientX < box.left || e.clientX > box.right || e.clientY < box.top || e.clientY > box.bottom) dialog.close(); } });
  };
})();
