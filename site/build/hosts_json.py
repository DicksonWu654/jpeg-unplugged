#!/usr/bin/env python3
"""Build site/data/hosts.json (AGGREGATE counts only) from data/hosts/hosts.csv.

  .venv/bin/python site/build/hosts_json.py [--csv data/hosts/hosts.csv] [--map host=col status=col ...]

The CSV has one row per hostname. Columns are matched by common names (override with --map). Needed: a hostname column and a
status column. Optional: registrable (bool: anyone can register the domain today), dangling (bool), expiring_soon (bool),
collections (a number, or a list separated by ; or , or |), kind (ipfs-gateway, arweave-gateway, cdn, api, other...),
Individual hostnames and examples are never written to hosts.json. Then it refreshes
site/data/available.json, which switches the section on.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
ROOT = os.path.dirname(SITE)
CAND = {
    "host": ["host", "hostname", "domain", "fqdn"],
    "status": ["status", "liveness", "state", "dns_status", "host_status", "verdict"],
    "registrable": ["registrable", "claimable", "available", "takeover", "unregistered", "takeover_candidate"],
    "dangling": ["dangling", "dangling_subdomain", "subdomain_takeover"],
    "expiring_soon": ["expiring_soon", "expiring", "expires_soon"],
    "collections": ["collections", "n_collections", "collection_count", "collection_addresses"],
    "kind": ["kind", "category", "type", "host_kind"],
    "public_example": ["public_example", "famous", "public"],
    "what": ["what", "note", "notes", "description"],
    "source_url": ["source_url", "source", "url"],
}


def pick(cols, key, over):
    if key in over:
        return over[key]
    low = {c.lower(): c for c in cols}
    for c in CAND[key]:
        if c in low:
            return low[c]
    return None


def truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "y", "t")


def norm_status(v):
    s = str(v).lower()
    measured = {"alive-serving": "live", "alive-but-wrong-content": "parked",
                "dead-http": "http-error", "domain-likely-available": "dns-nxdomain",
                "dangling-cloud-claimable": "http-error", "rereg-after-deploy": "http-error"}
    if s in measured:
        return measured[s]
    if any(k in s for k in ("nxdomain", "dns", "no-such", "not-resolv")):
        return "dns-nxdomain"
    if any(k in s for k in ("tls", "cert", "ssl")):
        return "tls-error"
    if "park" in s or "sinkhole" in s:
        return "parked"
    if any(k in s for k in ("4xx", "5xx", "http-error", "error", "http_4", "http_5", "404", "403", "500")):
        return "http-error"
    if any(k in s for k in ("alive", "live", "ok", "200", "up", "resolves")):
        return "live"
    return "unknown"


def ncoll(series):
    """(count, is_exact_union)"""
    sets, total, listy = set(), 0, False
    for v in series.dropna():
        sv = str(v).strip()
        if re.fullmatch(r"\d+(\.0)?", sv):
            total += int(float(sv))
        else:
            listy = True
            sets.update(x.strip().lower() for x in re.split(r"[;,|\s]+", sv) if x.strip())
    return (len(sets), True) if listy else (total, False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=os.path.join(ROOT, "data", "hosts", "hosts.csv"))
    ap.add_argument("--map", nargs="*", default=[])
    ap.add_argument("--snapshot-date", default="2026-10-21")
    a = ap.parse_args()
    over = dict(m.split("=", 1) for m in a.map)
    df = pd.read_csv(a.csv)
    c = {k: pick(df.columns, k, over) for k in CAND}
    if not c["host"] or not c["status"]:
        sys.exit("cannot find host/status columns. CSV columns: %s\nPass --map host=<col> status=<col> ..." % list(df.columns))
    df["_status"] = df[c["status"]].map(norm_status)
    n = len(df)
    out = {"schema_version": 1, "snapshot_date": a.snapshot_date,
           "totals": {"hosts": int(n)}, "by_status": {k: int(v) for k, v in Counter(df["_status"]).items()}}
    gone = df["_status"].isin(["dns-nxdomain", "tls-error", "http-error", "parked"])
    if c["collections"]:
        count, exact = ncoll(df[c["collections"]])
        if exact:
            out["totals"]["collections"] = int(count)
        else:
            out["collection_dependencies"] = int(count)
    takeover = {}
    for key, flag in (("registrable", "registrable_hosts"), ("dangling", "dangling_hosts"), ("expiring_soon", "expiring_soon_hosts")):
        if c[key]:
            m = df[c[key]].map(truthy)
            takeover[flag] = int(m.sum())
            if c["collections"]:
                takeover[flag.replace("_hosts", "_collections_affected")] = int(ncoll(df.loc[m, c["collections"]])[0])
    if "registrable_hosts" in takeover:
        takeover["collections_affected"] = takeover.pop("registrable_collections_affected", 0)
        out["takeover"] = takeover
    if c["status"] == "verdict":
        # Evidence classes are candidates; none was tested by registering a resource.
        out["takeover"] = {"evidence_counts": {
            "cloud_candidates": int(df.verdict.eq("dangling-cloud-claimable").sum()),
            "registry_404": int(df.get("available_evidence", pd.Series(dtype=str)).eq("rdap-404").sum()),
            "dns_only": int(df.get("available_evidence", pd.Series(dtype=str)).eq("ns-nxdomain-only").sum()),
            "registration_after_deploy": int(df.verdict.eq("rereg-after-deploy").sum()),
        }}
    if c["kind"]:
        g = df.groupby(c["kind"])
        out["by_kind"] = sorted(({"kind": str(k), "hosts": int(len(x)), "dead_hosts": int(gone.loc[x.index].sum())} for k, x in g), key=lambda d: -d["hosts"])
    json.dump(out, open(os.path.join(SITE, "data", "hosts.json"), "w"), indent=1)
    print("wrote hosts.json", {k: v for k, v in out.items() if k != "examples"})
    subprocess.run([sys.executable, os.path.join(HERE, "available.py")], check=False)


if __name__ == "__main__":
    main()
