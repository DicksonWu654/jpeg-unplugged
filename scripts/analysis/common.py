"""Shared helpers for the analysis analysis layer (read-only on every other study area's data)."""
import json
import math
import os
import re
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = DATA / "analysis"
SITE = ROOT / "site"
NOTES = ROOT / "notes"
RAW_CENSUS = DATA / "raw" / "census"

ONCHAIN = ("data-uri", "onchain-renderer")
OFFCHAIN = ("ipfs", "arweave", "http")
LOCS = ["data-uri", "onchain-renderer", "ipfs", "arweave", "http", "broken", "none"]
SEED = 20261021
N_BOOT = 2000


def read_parquet_safe(path, retries=8, delay=3.0):
    """Copy to a temp file first (census rewrites these while running) and retry on read errors."""
    last = None
    for i in range(retries):
        tmpd = tempfile.mkdtemp(prefix="w7_")
        try:
            tmp = Path(tmpd) / Path(path).name
            shutil.copy2(path, tmp)
            return pd.read_parquet(tmp)
        except Exception as e:  # truncated copy while being rewritten
            last = e
            time.sleep(delay)
        finally:
            shutil.rmtree(tmpd, ignore_errors=True)
    raise RuntimeError("could not read %s: %r" % (path, last))


def wilson(k, n, z=1.959964):
    """Wilson score interval; returns (lo, hi) as fractions."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def prop(k, n):
    """dict with k, n, pct and Wilson CI (in percent, 1 decimal kept at full precision)."""
    k = int(k)
    n = int(n)
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "pct": round(100 * k / n, 3) if n else None,
            "ci95": [round(100 * lo, 3), round(100 * hi, 3)] if n else None}


def boot_ratio(x, w, rng=None, n_boot=N_BOOT, seed=SEED):
    """Weighted share sum(w*x)/sum(w) with a percentile bootstrap CI over collections (percent)."""
    x = np.asarray(x, float)
    w = np.asarray(w, float)
    m = ~(np.isnan(x) | np.isnan(w))
    x, w = x[m], w[m]
    n = len(x)
    if n == 0 or w.sum() == 0:
        return {"pct": None, "ci95": None, "n": int(n)}
    rng = np.random.default_rng(seed)
    est = (w * x).sum() / w.sum()
    idx = rng.integers(0, n, size=(n_boot, n))
    num = (w[idx] * x[idx]).sum(1)
    den = w[idx].sum(1)
    b = num / den
    return {"pct": round(100 * est, 3), "ci95": [round(100 * np.percentile(b, 2.5), 3), round(100 * np.percentile(b, 97.5), 3)],
            "n": int(n), "weight_total": float(w.sum())}


def jdump(obj, path, indent=1):
    def default(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return None if np.isnan(o) else float(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if isinstance(o, (set, tuple)):
            return list(o)
        raise TypeError(type(o))
    Path(path).write_text(json.dumps(obj, indent=indent, default=default, ensure_ascii=False) + "\n")


# ---- reason vocabulary --------------------------------------------------------------------------
REASON_PRIORITY = ["dns", "tls", "parked", "ipfs-not-found", "arweave-not-found", "http-4xx", "http-5xx", "connection",
                   "timeout", "tokenuri-revert", "bad-tokenuri", "not-json", "other"]
REASON_SITE = {  # analysis category -> site dead_reasons key
    "dns": "dns-failure", "tls": "tls-error", "parked": "parked-domain", "ipfs-not-found": "ipfs-content-not-found",
    "arweave-not-found": "arweave-content-not-found", "http-4xx": "http-4xx", "http-5xx": "http-5xx",
    "connection": "connection-error", "timeout": "timeout", "tokenuri-revert": "tokenuri-revert",
    "bad-tokenuri": "bad-tokenuri", "not-json": "not-json", "other": "other"}


def reason_cat(reason, cls=None):
    """Map a census reason string for ONE failing target to a coarse category."""
    if reason is None or (isinstance(reason, float) and np.isnan(reason)):
        return None
    r = str(reason)
    for pre in ("media-dead:", "media-unknown:", "dead-candidate:", "mixed:"):
        if r.startswith(pre):
            r = r[len(pre):]
    if r.startswith("tokenuri-revert"):
        return "tokenuri-revert"
    if r.startswith("tokenuri-") or r in ("no-scheme", "ipfs-malformed-cid", "ar-malformed", "empty-or-undecodable") or "malformed" in r:
        return "bad-tokenuri"
    if r.startswith("gateway-not-found"):
        return "arweave-not-found" if cls == "arweave" else "ipfs-not-found"
    if r.startswith("dns-"):
        return "dns"
    if r.startswith("tls"):
        return "tls"
    if r.startswith("parked"):
        return "parked"
    if re.match(r"http-4\d\d", r):
        return "http-4xx"
    if re.match(r"http-5\d\d", r):
        return "http-5xx"
    if r.startswith("timeout"):
        return "timeout"
    if r.startswith("conn-"):
        return "connection"
    if r.startswith("not-json") or r.startswith("html-instead"):
        return "not-json"
    return "other"


def pick_reason(cats):
    """Most frequent category; ties broken by REASON_PRIORITY."""
    cats = [c for c in cats if c]
    if not cats:
        return None
    from collections import Counter
    cnt = Counter(cats)
    top = max(cnt.values())
    for c in REASON_PRIORITY:
        if cnt.get(c) == top:
            return c
    return cnt.most_common(1)[0][0]
