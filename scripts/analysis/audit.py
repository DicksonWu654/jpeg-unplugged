"""Stage 4: misclassification audit.
(a) independent re-classification of every random-stratum token URI from the saved raw string (my own regex rules, not census's),
(b) liveness consistency: census verdict vs the status codes in its own evidence.jsonl,
(c) a seeded manual-review sample (10 rows per class) dumped with raw evidence for hand inspection.
Writes data/analysis/audit_summary.json, audit_disagreements.csv, audit_sample.csv.
"""
import gzip
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa

ARW = re.compile(r"(^|//|\.)(arweave\.net|ar-io\.(net|dev)|g8way\.io|arweave\.dev|ardrive\.net|turbo-gateway\.com)(/|$|:)", re.I)


def my_class(u):
    if not isinstance(u, str) or not u.strip():
        return "broken"
    s = u.strip()
    if s.startswith("data:") or s.startswith("{") or s.lower().startswith("<svg") or s.lower().startswith("<html"):
        return "onchain"
    if s.startswith("ipfs://") or s.startswith("/ipfs/") or re.match(r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|ba[fgk][a-z2-7]{50,})", s):
        return "ipfs"
    if s.startswith("ar://"):
        return "arweave"
    if re.match(r"^https?://", s, re.I):
        if re.search(r"/ipfs/(Qm|bafy)", s) or re.search(r"//(Qm[1-9A-HJ-NP-Za-km-z]{44}|ba[fgk][a-z2-7]{50,})\.ipfs\.", s):
            return "ipfs"
        if ARW.search(s.split("/", 3)[2] if s.count("/") >= 2 else s):
            return "arweave"
        return "http"
    return "broken"


def w2_group(c):
    return {"data-uri": "onchain", "onchain-renderer": "onchain"}.get(c, c)


def load_result(a):
    d = RAW_CENSUS / a
    p = d / "result.json.gz"
    return json.load(gzip.open(p)) if p.exists() else json.load(open(d / "result.json"))


def decode_abi_string(hexstr):
    b = bytes.fromhex(hexstr[2:] if hexstr.startswith("0x") else hexstr)
    if len(b) < 64:
        return None
    off = int.from_bytes(b[:32], "big")
    ln = int.from_bytes(b[off:off + 32], "big")
    return b[off + 32:off + 32 + ln].decode("utf-8", "replace")


def evidence_fetches(a):
    d = RAW_CENSUS / a
    for name, op in (("evidence.jsonl.gz", gzip.open), ("evidence.jsonl", open)):
        if (d / name).exists():
            return [json.loads(l) for l in op(d / name, "rt") if l.strip()]
    return []


def dns_recheck(f, n=25):
    """Live re-resolution (1.1.1.1) of origin hosts of random-stratum collections classified dead by DNS."""
    import subprocess
    t = read_parquet_safe(DATA / "census" / "census_tokens.parquet")
    t["a"] = t.address.str.lower()
    R = f[(f.stratum == "random") & (f.liveness == "dead") & (f.reason_cat == "dns")]
    x = t[t.a.isin(R.a) & (t.meta_class == "http") & (t.meta_verdict == "dead")].drop_duplicates("a")
    x = x.sample(min(n, len(x)), random_state=SEED)
    res = {"NXDOMAIN": 0, "SERVFAIL": 0, "NOERROR": 0, "other": 0}
    for h in x.meta_host:
        try:
            out = subprocess.run(["dig", "@1.1.1.1", h, "A", "+time=4", "+tries=1"], capture_output=True, text=True, timeout=15).stdout
            m = re.search(r"status: (\w+)", out)
            st = m.group(1) if m else "other"
        except Exception:
            st = "other"
        res[st if st in res else "other"] += 1
    return {"hosts_rechecked": int(len(x)), "still_failing_dns": res["NXDOMAIN"] + res["SERVFAIL"], **res}


def main():
    f = pd.read_parquet(OUT / "collections_enriched.parquet")
    R = f[f.stratum == "random"]
    dis, n_tok, n_dis = [], 0, 0
    live_incons = []
    for r in R.itertuples():
        try:
            res = load_result(r.a)
        except Exception as e:
            continue
        ev = None
        for t in res["tokens"]:
            u = t.get("uri_raw")
            mine, theirs = my_class(u), w2_group(t.get("meta_class"))
            n_tok += 1
            if t.get("meta_class") in (None, "broken") and not u:
                mine = "broken"
            if mine != theirs:
                n_dis += 1
                dis.append({"address": r.a, "token": t.get("token_id"), "w2": t.get("meta_class"), "mine": mine, "uri_head": (u or "")[:120],
                            "reason": t.get("meta_reason")})
            # liveness consistency for decisive verdicts
            der = t.get("derived") or {}
            if der.get("meta_verdict") == "alive" and t.get("meta_class") in ("http", "ipfs", "arweave"):
                if ev is None:
                    ev = evidence_fetches(r.a)
                oks = [e for e in ev if e.get("kind") == "fetch" and e.get("role") == "metadata" and str(e.get("token_id")) == str(t.get("token_id")) and e.get("verdict") == "alive"]
                if not oks or not any(200 <= (e.get("status") or 0) < 300 for e in oks):
                    live_incons.append((r.a, t.get("token_id"), "alive without 2xx evidence"))
            if der.get("meta_verdict") == "dead" and t.get("meta_class") in ("http", "ipfs", "arweave"):
                if ev is None:
                    ev = evidence_fetches(r.a)
                fs = [e for e in ev if e.get("kind") == "fetch" and e.get("role") == "metadata" and str(e.get("token_id")) == str(t.get("token_id"))]
                if any(e.get("verdict") == "alive" for e in fs):
                    live_incons.append((r.a, t.get("token_id"), "dead although some fetch was alive"))
    dd = pd.DataFrame(dis)
    dd.to_csv(OUT / "audit_disagreements.csv", index=False)

    # (c) manual sample
    rng = np.random.default_rng(SEED)
    classes = {
        "meta=ipfs": R.meta_loc == "ipfs", "meta=http": R.meta_loc == "http", "meta=arweave": R.meta_loc == "arweave",
        "meta=onchain": R.meta_onchain, "meta=broken": R.meta_loc == "broken",
        "live=alive": R.liveness == "alive", "live=dead": R.liveness == "dead", "live=degraded": R.liveness == "degraded",
        "live=unknown": R.liveness == "unknown", "truly_onchain": R.truly_onchain, "fake_onchain_A": R.fake_a}
    rows = []
    for k, m in classes.items():
        sub = R[m]
        pick = sub.iloc[rng.choice(len(sub), size=min(10, len(sub)), replace=False)]
        for r in pick.itertuples():
            try:
                res = load_result(r.a)
            except Exception:
                continue
            t0 = res["tokens"][0]
            # independently re-decode the raw eth_call body for token 0
            raw_uri = None
            try:
                z = zipfile.ZipFile(RAW_CENSUS / r.a / "bodies.zip")
                evs = evidence_fetches(r.a)
                e = next(e for e in evs if e.get("kind") == "rpc" and str(e.get("role", "")).startswith("eth_call") and str(e.get("token_id")) == str(t0["token_id"]))
                j = json.loads(z.read(e["body_file"]))
                raw_uri = decode_abi_string(j.get("result", "0x"))
            except Exception:
                pass
            rows.append({"class": k, "address": r.a, "name": r.name, "w2_meta": r.meta_loc, "w2_media": r.media_loc, "w2_live": r.liveness,
                         "w2_reason": r.reason_cat, "token0_uri_w2": (t0.get("uri_raw") or "")[:110], "token0_uri_redecoded": (raw_uri or "")[:110],
                         "redecode_matches": (raw_uri.startswith((t0.get("uri_raw") or "")[:3000]) if raw_uri is not None else None),
                         "my_class": my_class(raw_uri if raw_uri is not None else t0.get("uri_raw")), "reasons": r.liveness_reasons,
                         "exact": r.liveness_exact, "truly": r.truly_onchain})
    sm = pd.DataFrame(rows)
    sm.to_csv(OUT / "audit_sample.csv", index=False)
    summ = {"random_tokens_checked": n_tok, "metadata_class_disagreements_tokens": n_dis,
            "metadata_class_disagreement_rate": round(n_dis / max(n_tok, 1), 5),
            "disagreements_by_pair": dd.groupby(["w2", "mine"]).size().rename("n").reset_index().to_dict("records") if len(dd) else [],
            "liveness_evidence_inconsistencies": len(live_incons), "liveness_inconsistency_examples": live_incons[:10],
            "manual_sample_rows": len(sm), "redecode_match_rate": float(sm.redecode_matches.dropna().mean()) if sm.redecode_matches.notna().any() else None}
    summ["dns_recheck"] = dns_recheck(f)
    jdump(summ, OUT / "audit_summary.json")
    print(json.dumps(summ)[:1500])


if __name__ == "__main__":
    main()
