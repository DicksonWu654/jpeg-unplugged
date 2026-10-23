#!/usr/bin/env python3
"""Build site/data/gallery.json from data/gallery/results.csv + site/gallery-assets/manifest.json.

Run:  .venv/bin/python site/build/gallery_json.py

Verdict rule: the page shows the FINAL verdict = manual review override when the
`manual_verdict_*` column is non-empty, otherwise the automatic verdict. Both are kept in the JSON.
Everything in the output is copied from the two inputs; nothing is invented here.
"""
import csv
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
ROOT = os.path.dirname(SITE)
CSV_PATH = os.path.join(ROOT, "data", "gallery", "results.csv")
MANIFEST = os.path.join(SITE, "gallery-assets", "manifest.json")
OUT = os.path.join(SITE, "data", "gallery.json")
ASSETS = os.path.join(SITE, "gallery-assets")


def to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def to_bool(v):
    return str(v).strip().lower() in ("true", "1", "yes")


def split(v, sep):
    return [x.strip() for x in (v or "").split(sep) if x.strip()]


def main():
    manifest = {m["slug"]: m for m in json.load(open(MANIFEST))}
    rows = {r["slug"]: r for r in csv.DictReader(open(CSV_PATH))}
    missing = set(manifest) ^ set(rows)
    if missing:
        sys.exit("slug mismatch between manifest and results.csv: %s" % sorted(missing))

    items = []
    for slug, m in manifest.items():
        r = rows[slug]
        ext = m["unplugged"].rsplit(".", 1)[-1]
        thumbs = {}
        for c in "ABC":
            fn = "%s_%s.jpg" % (slug, c)
            if os.path.exists(os.path.join(ASSETS, fn)):
                thumbs[c] = fn
        storage = r["chain_storage_method"]
        item = {
            "slug": slug,
            "name": r["collection"],
            "family": "art-blocks" if storage.startswith("Art Blocks") else "other",
            "contract": r["contract"],
            "token": r["token"],
            "medium": r["medium"],
            "storage": storage,
            "file": m["unplugged"],
            "file_type": ext,
            "bytes": m["unplugged_bytes"],
            "archive": m.get("archive"),
            "archive_bytes": m.get("archive_bytes"),
            "archive_urls": m.get("archive_urls") or [],
            "verdict_B": r["manual_verdict_B"] or r["verdict_B"],
            "verdict_C": r["manual_verdict_C"] or r["verdict_C"],
            "auto_verdict_B": r["verdict_B"],
            "auto_verdict_C": r["verdict_C"],
            "manual_override": bool(r["manual_verdict_B"] or r["manual_verdict_C"]),
            "diff_B": to_float(r["diff_B"]),
            "diff_C": to_float(r["diff_C"]),
            "noise": to_float(r["noise"]),
            "ext_requests_A": to_int(r["external_requests_A"]) or 0,
            "ext_hosts_A": split(r["external_hosts_A"], ";"),
            "blocked_B": to_int(r["external_blocked_B"]) or 0,
            "still_blocked_C": to_int(r["still_blocked_C"]) or 0,
            "console_errors_B": to_int(r["B_console_errors"]) or 0,
            "page_errors_B": to_int(r["B_page_errors"]) or 0,
            "declared_deps": split(r["declared_deps"], " | "),
            "gas_est": to_int(r["est_gas"]),
            "needs_fork": to_bool(r["read_needed_fork"]),
            "notes": r["notes"],
            "thumbs": thumbs,
        }
        for k in ("file", "archive"):
            if item[k] and not os.path.exists(os.path.join(ASSETS, item[k])):
                sys.exit("missing asset " + item[k])
        items.append(item)

    out = {
        "schema_version": 1,
        "source": "data/gallery/results.csv + site/gallery-assets/manifest.json",
        "snapshot_date": "2026-10-21",
        "counts": {
            "tokens": len(items),
            "verdict_B": dict(Counter(i["verdict_B"] for i in items)),
            "verdict_C": dict(Counter(i["verdict_C"] for i in items)),
            "made_request_in_A": sum(1 for i in items if i["ext_requests_A"] > 0),
        },
        "items": items,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print("wrote", OUT, len(items), "items", out["counts"])


if __name__ == "__main__":
    main()
