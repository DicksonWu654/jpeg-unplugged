/* Findings follow article/key-findings.md. Values are derived only from site/data JSON. */
(function () {
  "use strict";
  var JU = window.JU, h = JU.h;
  // Small, code-native pixel icons. Coordinates are artwork, never research counts.
  var ICONS = {
    chain: "M2 5h3v2H4v5h4v-2h2v4H2zm7-3h7v9h-4V9h2V4h-3v3H9zM6 7h6v2H6z",
    file: "M3 1h8l4 4v10H3zm2 2v10h8V7H9V3zm1 5h2v2H6zm4 0h2v2h-2zM6 11h6v1H6z",
    plug: "M4 1h2v4h4V1h2v4h2v6h-4v4H8v-4H4V5H2v2h2z",
    pen: "M11 1h3v3h-3zm-2 3h3v3H9zM7 6h3v3H7zM5 8h3v3H5zM3 10h3v3H3zm-1 3h12v2H2z",
    host: "M2 1h12v6H2zm2 2v2h2V3zm5 0v2h3V3zM2 9h12v6H2zm2 2v2h2v-2zm5 0v2h3v-2z"
  };
  function card(icon, value, text, note, href, cls) {
    return h("a", { class: "finding " + cls, href: href },
      h("svg", { viewBox: "0 0 16 16", "aria-hidden": "true", class: "pixel-icon" }, h("path", { d: ICONS[icon], fill: "currentColor" })),
      h("strong", { class: "finding-value", text: value }),
      h("p", { class: "finding-text", text: text }),
      h("p", { class: "finding-fine", text: note }), h("span", { class: "finding-arrow", "aria-hidden": "true", text: "↗" }));
  }
  JU.initFindings = function () {
    var c = JU.data.census, m = JU.data.mutability, hosts = JU.data.hosts, g = JU.data.gallery;
    var root = JU.$("#finding-grid"); if (!root || !c) return;
    root.textContent = "";
    root.appendChild(card("chain", JU.pct(c.survival.yes, c.totals.collections, 1), "have metadata and sampled media fully on-chain.", "A candidate set; an upper bound on rendering.", "#c-where", "finding-green"));
    root.appendChild(card("file", JU.pct(c.liveness.dead, c.totals.collections, 1), "have metadata that no longer loads today.", "Includes contract reverts and public-gateway misses.", "#c-alive", "finding-pink"));
    if (g) {
      var genesis = g.items.filter(function (it) { return it.slug === "ab-1"; })[0];
      if (genesis) root.appendChild(card("plug", genesis.name.replace(/^Art Blocks #\d+ /, "").replace(/ \(.+\)$/, ""), "goes blank without its CDN library.", "On-chain script. Off-chain dependency.", "#gallery", "finding-yellow"));
    }
    if (m) root.appendChild(card("pen", JU.pct(m.funnel.explicit_repointable, m.funnel.explicit), "of explicit on-chain claimants can still repoint the art.", JU.fmt(m.funnel.explicit_repointable) + " of " + JU.fmt(m.funnel.explicit) + " reviewed; EOA or multisig control.", "#pen", "finding-purple"));
    if (hosts) root.appendChild(card("host", JU.fmt(hosts.takeover.evidence_counts.cloud_candidates), "hosts look like deleted cloud resources.", "Names may be re-creatable; reclaimability untested.", "#hosts", "finding-blue"));
    JU.$("#finding-note").textContent = "Census: a random sample of " + JU.fmt(c.totals.collections) + " collections with at least " + JU.fmt(c.criteria.min_holders) + " holders. Only the gallery is render-tested. Claims and hosts are separate, selected sets. See the data for intervals and evidence.";
  };
})();
