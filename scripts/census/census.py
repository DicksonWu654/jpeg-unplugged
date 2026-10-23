#!/usr/bin/env python3
"""JPEG Unplugged census pipeline (census).

Per collection: sample 3 token ids -> eth_call tokenURI/uri -> classify metadata location -> fetch metadata ->
classify image / image_data / animation_url -> liveness fetches -> evidence dir + result.json.

CLI (run with the project venv, from anywhere):
  census.py gateways                      canary-test IPFS/Arweave gateways -> data/census/gateways.json
  census.py run --list seed|universe [--spam skip|only|all] [--limit N] [--concurrency N]
  census.py retry [--min-age SEC]         second pass over unresolved fetches (timeouts, dead-candidates)
  census.py aggregate                     result.json files -> data/census/census_{tokens,collections}.parquet
"""
import argparse
import aiohttp
import asyncio
import gzip
import hashlib
import json
import os
import pathlib
import random
import re
import sys
import time
import traceback
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classify import (classify_media_value, classify_uri, ext_domains, extract_media, looks_bot_wall, looks_parked,  # noqa: E402
                      parse_data_uri, parse_json_lenient, reg_domain, scan_external, sniff, substitute_id)
from net import Evidence, Net, now_iso  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "census"
OUT = ROOT / "data" / "census"
UNIVERSE = ROOT / "data" / "universe" / "collections.parquet"

RPC_ENDPOINTS = ["https://eth.drpc.org", "https://eth.rpc.blxrbdn.com"]
# Used only to re-try eth_call reverts: the two primaries (and publicnode) cap eth_call gas (~50M), so heavy on-chain
# renderers (e.g. Nouns) "revert" there but succeed on nodes with a higher cap. Verified 2026-10-21 for Nouns tokenURI(1013).
RPC_FALLBACK = ["https://rpc.mevblocker.io", "https://eth-mainnet.public.blastapi.io"]
BLOCKSCOUT = "https://eth.blockscout.com/api/v2"
MULTICALL3 = "0xcA11bde05977b3631167028862bE2a173976CA11"
SEL_TOKENURI, SEL_URI = "c87b56dd", "0e89341c"
SEL_TOTALSUPPLY, SEL_TBI, SEL_OWNEROF = "18160ddd", "4f6ccce7", "6352211e"
SEL_AGG3 = "82ad56cb"
EIP1967_IMPL = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"

# Gateways tried (in this order of preference, rotated) when a CID must be checked. The canary (`gateways` cmd)
# decides which are actually usable today; `BOT_WALLED` hosts are never hit by the pipeline (see notes).
IPFS_CANDIDATES = ["gateway.pinata.cloud", "ipfs.4everland.io", "ipfs.filebase.io", "ipfs.hypha.coop",
                   "ipfs.raribleuserdata.com", "magic.decentralized-content.com", "ipfs.blockfrost.dev", "4everland.io",
                   "ipfs.io", "dweb.link", "w3s.link", "nftstorage.link", "gateway.ipfs.io", "trustless-gateway.link",
                   "cloudflare-ipfs.com", "cf-ipfs.com", "ipfs.fleek.co", "infura-ipfs.io", "ipfs.infura.io",
                   "ipfs.eth.aragon.network", "ipfs.runfission.com", "hub.textile.io", "ipfs.decentralized-content.com",
                   "gateway.lighthouse.storage", "storry.tv", "ipfs.eternum.io", "flk-ipfs.xyz", "ipfs.litnet.work",
                   "ipfs.crustwebsites.net", "dget.top", "ipfs.nftscan.com", "ipfs.thirdwebcdn.com", "ipfs.sphn.link"]
AR_CANDIDATES = ["arweave.net", "gateway.irys.xyz", "turbo-gateway.com", "ardrive.net", "ar-io.net", "g8way.io",
                 "arweave.dev", "ario.permagate.io", "ar-io.dev", "arweave.developerdao.com"]
BAYC_META = "QmeSjSinHpPnmXmspMjwiXyN6zS4E9zccariGR3jxcaWtq/1"
GW_STATE = {"ipfs_ok": [], "ar_ok": [], "status": {}}  # filled from data/census/gateways.json


# ----------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------
def jdump(p, obj):
    pathlib.Path(p).parent.mkdir(parents=True, exist_ok=True)
    tmp = str(p) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
    os.replace(tmp, p)


def save_result(d, res):
    d = pathlib.Path(d)
    tmp = d / "result.json.gz.tmp"
    with gzip.open(tmp, "wt", compresslevel=6) as f:
        json.dump(res, f, ensure_ascii=False, separators=(",", ":"), default=str)
    os.replace(tmp, d / "result.json.gz")
    old = d / "result.json"
    if old.exists():
        old.unlink()


def load_result(d):
    d = pathlib.Path(d)
    if (d / "result.json.gz").exists():
        with gzip.open(d / "result.json.gz", "rt") as f:
            return json.load(f)
    return json.load(open(d / "result.json"))


def has_result(d):
    d = pathlib.Path(d)
    return (d / "result.json.gz").exists() or (d / "result.json").exists()


def log(msg, path=None):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        with open(path or OUT / "progress.log", "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


# Gateways that pass the canary but that we do not use for the sweep: pinata's public gateway answers 429 to a research client
# after a handful of requests; bare 4everland.io only redirects to the ipfs.4everland.io subdomain gateway (kept).
GW_EXCLUDE = {"gateway.pinata.cloud", "4everland.io"}


def load_gateways():
    p = OUT / "gateways.json"
    if p.exists():
        d = json.load(open(p))
        GW_STATE.update(ipfs_ok=[g for g in d["ipfs_ok"] if g not in GW_EXCLUDE], ar_ok=d["ar_ok"], status=d["status"])
        order = ["ipfs.filebase.io", "ipfs.raribleuserdata.com", "magic.decentralized-content.com", "ipfs.blockfrost.dev", "ipfs.hypha.coop", "ipfs.4everland.io"]
        GW_STATE["ipfs_ok"].sort(key=lambda g: order.index(g) if g in order else 99)
    else:
        GW_STATE.update(ipfs_ok=["gateway.pinata.cloud", "ipfs.4everland.io", "ipfs.filebase.io", "ipfs.hypha.coop"],
                        ar_ok=["arweave.net"], status={})


def u256(n):
    return int(n).to_bytes(32, "big").hex()


# ----------------------------------------------------------------------------------------------
# RPC + Blockscout
# ----------------------------------------------------------------------------------------------
class Rpc:
    def __init__(self, net):
        self.net = net
        self.rr = random.randrange(len(RPC_ENDPOINTS))
        for ep in RPC_ENDPOINTS + RPC_FALLBACK:
            net.throttle.configure(ep, interval=0.08, conc=6)
        net.throttle.configure("blockscout", interval=0.4, conc=10)

    async def call(self, ev, role, method, params, token_id=None, store_body=True, attempts=5, endpoints=None):
        """JSON-RPC with endpoint round-robin + retries. Returns dict(ok, result, error, revert, endpoint, http_status)."""
        last = None
        for i in range(attempts):
            eps = endpoints or RPC_ENDPOINTS
            ep = eps[(self.rr + i) % len(eps)]
            payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
            body, status, err, kind = b"", None, None, None
            t0 = time.time()
            try:
                async with self.net.throttle.acquire(ep):
                    async with self.net.rpc_session.post(ep, json=payload) as r:
                        status = r.status
                        body = await r.read()
            except Exception as e:  # noqa: BLE001
                err, kind = f"{type(e).__name__}: {e}"[:200], "net"
            data = None
            if body:
                try:
                    data = json.loads(body)
                except ValueError:
                    kind = kind or "bad-json"
            res = {"endpoint": ep, "http_status": status, "ok": False, "result": None, "error": err, "revert": False}
            if data is not None:
                if "result" in data and data.get("error") is None:
                    res.update(ok=True, result=data["result"])
                else:
                    e = data.get("error") or {}
                    msg = str(e.get("message", ""))
                    res["error"] = f"{e.get('code')}: {msg}"[:300]
                    res["error_data"] = str(e.get("data", ""))[:300]
                    low = msg.lower()
                    # real EVM failure vs infra rate-limit / node trouble
                    if e.get("code") == 3 or "revert" in low or "invalid opcode" in low or "out of gas" in low or \
                            "stack" in low and "underflow" in low or "invalid jump" in low or "execution error" in low:
                        res["revert"] = True
                    else:
                        kind = "rpc-error"
            elif status and status != 200:
                kind = f"http-{status}"
            ev.record(kind="rpc", role=role, url=ep, method=f"POST {method}", status=status, error=res["error"], error_kind=kind,
                      body=body if (store_body and (res["ok"] or res["revert"])) else None, store_cap=600_000, body_ext="json",
                      token_id=token_id, extra={"params": json.dumps(params)[:160], "elapsed": round(time.time() - t0, 2), "rpc_attempt": i + 1})
            if res["ok"] or res["revert"]:
                self.rr += 1
                return res
            last = res
            await asyncio.sleep(min(0.5 * (2 ** i), 6) + random.random() * 0.3)
        return last or {"ok": False, "result": None, "error": "no-attempts", "revert": False}

    async def eth_call(self, ev, role, to, data_hex, token_id=None, endpoints=None, attempts=5):
        return await self.call(ev, role, "eth_call", [{"to": to, "data": "0x" + data_hex}, "latest"], token_id=token_id,
                               endpoints=endpoints, attempts=attempts)

    async def multicall(self, ev, role, calls):
        """calls: list of (target, data_hex). Returns list[(ok, bytes)] or None if the multicall itself failed."""
        from eth_abi import decode, encode
        enc = encode(["(address,bool,bytes)[]"], [[(t, True, bytes.fromhex(d)) for t, d in calls]])
        r = await self.eth_call(ev, role, MULTICALL3, SEL_AGG3 + enc.hex())
        if not r["ok"]:
            return None
        try:
            (out,) = decode(["(bool,bytes)[]"], bytes.fromhex(r["result"][2:]))
            return [(bool(ok), bytes(b)) for ok, b in out]
        except Exception:  # noqa: BLE001
            return None

    async def blockscout(self, ev, role, path, token_id=None):
        url = BLOCKSCOUT + path
        for i in range(2):
            body, status, err = b"", None, None
            try:
                async with self.net.throttle.acquire("blockscout"):
                    async with self.net.rpc_session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
                        status = r.status
                        body = await r.read()
                        if status == 429:
                            self.net.throttle.backoff("blockscout", 3.0 * (i + 1))
            except Exception as e:  # noqa: BLE001
                err = f"{type(e).__name__}: {e}"[:200]
            ev.record(kind="blockscout", role=role, url=url, method="GET", status=status, error=err,
                      body=body if status == 200 else None, store_cap=1_500_000, body_ext="json", token_id=token_id)
            if status == 200:
                try:
                    return json.loads(body)
                except ValueError:
                    return None
            if status in (404,):
                return None
            await asyncio.sleep(1.0 * (i + 1))
        return None


def decode_abi_string(hexres):
    """Decode an eth_call return value as an ABI-encoded string. -> (str|None, note)."""
    if hexres in (None, "0x", ""):
        return None, "empty-return"
    b = bytes.fromhex(hexres[2:] if hexres.startswith("0x") else hexres)
    try:
        if len(b) >= 64 and int.from_bytes(b[:32], "big") == 32:
            ln = int.from_bytes(b[32:64], "big")
            if ln > len(b) - 64:
                return None, "abi-length-overrun"
            raw = b[64:64 + ln]
            try:
                return raw.decode("utf-8"), None
            except UnicodeDecodeError:
                return raw.decode("utf-8", "replace"), "utf8-replaced"
        if len(b) == 32:
            return b.rstrip(b"\0").decode("utf-8", "replace"), "bytes32-string"
    except Exception:  # noqa: BLE001
        pass
    return None, "undecodable-abi"


# ----------------------------------------------------------------------------------------------
# Token sampling
# ----------------------------------------------------------------------------------------------
def _ids_from_items(items):
    out = []
    for it in items or []:
        try:
            out.append((int(it["id"]), it))
        except (KeyError, TypeError, ValueError):
            pass
    return out


def _transfer_ids(items):
    out = []
    for it in items or []:
        tot = it.get("total")
        tots = tot if isinstance(tot, list) else [tot]
        for t in tots:
            try:
                out.append(int(t["token_id"]))
            except (KeyError, TypeError, ValueError):
                pass
    return out


async def validate_721(rpc, ev, addr, tid, step):
    """Return (token_id, note): tid if ownerOf succeeds, else the nearest id (stepping by `step`, up to 16) that has an owner."""
    mv = await rpc.multicall(ev, "sample_validate", [(addr, SEL_OWNEROF + u256(tid))])
    if mv is None or (mv[0][0] and len(mv[0][1]) == 32):
        return tid, None
    cands = [tid + step * j for j in range(1, 17) if tid + step * j >= 0]
    mp = await rpc.multicall(ev, "sample_validate_probe", [(addr, SEL_OWNEROF + u256(c)) for c in cands])
    for c, r in zip(cands, mp or []):
        if r[0] and len(r[1]) == 32:
            return c, f"ownerOf({tid}) reverted (burned/stale); moved to {c}"
    return tid, f"ownerOf({tid}) reverted; no valid neighbour found"


_GRID = sorted(set([2 ** k for k in range(5, 41)] + [10 ** k for k in range(2, 13)] + [k * 10 ** 6 for k in range(1, 21)]))


async def probe_721(rpc, ev, addr, total, owner_ok, want):
    """RPC-only sampling for non-enumerable ERC-721 (Blockscout/Etherscan are shared and rate-limited, so avoid them).
    low = first id in 0..15 with an owner; recent = highest id found via ownerOf probes around totalSupply or on a geometric
    grid + refinement; mid = an existing id near the midpoint. Returns a list of {token_id, how} (possibly empty)."""
    def ok(r):
        return r[0] and len(r[1]) == 32
    low = owner_ok[0] if owner_ok else None
    high, how_high = None, None
    if total and 0 < total < 2 ** 64:
        ids = [i for i in (total - 1, total, total + 1, total + 2) if i >= 0]
        mc = await rpc.multicall(ev, "sample_probe_high", [(addr, SEL_OWNEROF + u256(i)) for i in ids])
        hits = [i for i, r in zip(ids, mc or []) if ok(r)]
        if hits:
            high, how_high = max(hits), f"ownerOf-probe(totalSupply={total}) [recent]"
    if high is None:
        mc = await rpc.multicall(ev, "sample_probe_grid", [(addr, SEL_OWNEROF + u256(i)) for i in _GRID])
        X = [i for i, r in zip(_GRID, mc or []) if ok(r)]
        if X:
            m = max(X)
            nxt = [g for g in _GRID if g > m]
            n = nxt[0] if nxt else m * 2
            for _ in range(3):
                step = max((n - m) // 16, 1)
                pts = [m + step * k for k in range(1, 16) if m + step * k < n]
                if not pts:
                    break
                mc = await rpc.multicall(ev, "sample_probe_refine", [(addr, SEL_OWNEROF + u256(i)) for i in pts])
                hits = [i for i, r in zip(pts, mc or []) if ok(r)]
                if hits:
                    m = max(hits)
                    above = [p for p in pts if p > m]
                    n = above[0] if above else n
                else:
                    n = pts[0]
            high, how_high = m, "ownerOf-geometric-probe [recent]"
            if low is None:
                low = min(X)
    toks = []
    if low is not None:
        toks.append({"token_id": low, "how": "ownerOf-probe(0..15)/grid-min [low]"})
    if want == 3 and low is not None and high is not None and high - low > 2:
        base = (low + high) // 2
        mc = await rpc.multicall(ev, "sample_probe_mid", [(addr, SEL_OWNEROF + u256(base + i)) for i in range(16)])
        for i, r in enumerate(mc or []):
            if ok(r) and base + i not in (low, high):
                toks.append({"token_id": base + i, "how": f"ownerOf-probe({base}..+15) [mid]"})
                break
    if high is not None and high != low:
        toks.append({"token_id": high, "how": how_high})
    return toks


TOPIC_TSINGLE = "0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62"
TOPIC_TBATCH = "0x4a39dc06d4c0dbc64b70af90fd698a233a518aa5d07e595d983b8c0526c8f7fb"


def _ids_from_1155_logs(logs):
    """-> list of (block, logIndex, token_id) from TransferSingle / TransferBatch logs."""
    from eth_abi import decode
    out = []
    for lg in logs or []:
        try:
            blk, li = int(lg["blockNumber"], 16), int(lg["logIndex"], 16)
            data = bytes.fromhex(lg["data"][2:])
            if lg["topics"][0] == TOPIC_TSINGLE:
                out.append((blk, li, int.from_bytes(data[:32], "big")))
            elif lg["topics"][0] == TOPIC_TBATCH:
                ids, _vals = decode(["uint256[]", "uint256[]"], data)
                out += [(blk, li, int(i)) for i in ids[:50]]
        except Exception:  # noqa: BLE001
            continue
    return out


async def sample_1155_logs(rpc, ev, addr, deploy_block, want):
    """RPC-only sampling for ERC-1155 (drpc free plan: eth_getLogs limited to 10,000 blocks): earliest ids from the first
    10k blocks after deployment (low), most recent ids from the last 10k blocks (recent) or the end of the early window."""
    if not deploy_block or deploy_block != deploy_block:
        return []
    head = await rpc.call(ev, "blockNumber", "eth_blockNumber", [], store_body=False)
    if not head["ok"]:
        return []
    latest = int(head["result"], 16)
    d0 = int(deploy_block)
    async def window(lo, hi, role):
        r = await rpc.call(ev, role, "eth_getLogs", [{"address": addr, "fromBlock": hex(lo), "toBlock": hex(hi), "topics": [[TOPIC_TSINGLE, TOPIC_TBATCH]]}],
                           endpoints=["https://eth.drpc.org"], attempts=3)
        return _ids_from_1155_logs(r["result"]) if r["ok"] else None
    early = await window(d0, min(d0 + 8000, latest), "sample_logs_early")
    late = await window(max(latest - 8000, 0), latest, "sample_logs_late") if latest - 8000 > d0 + 8000 else None
    toks = []
    if early:
        early.sort()
        toks.append({"token_id": early[0][2], "how": f"TransferSingle/Batch logs, first 8k blocks after deploy block {d0} [low]"})
        if want == 3:
            ids = sorted({i for _, _, i in early})
            if len(ids) > 2:
                toks.append({"token_id": ids[len(ids) // 2], "how": "median id among early-window transfer logs [mid]"})
    if late:
        late.sort()
        toks.append({"token_id": late[-1][2], "how": f"most recent transfer log in last 8k blocks (block {late[-1][0]}) [recent]"})
    elif early and len(early) > 1:
        toks.append({"token_id": early[-1][2], "how": "last transfer log of the early window (no recent activity found) [recent]"})
    return toks


async def sample_tokens(rpc, ev, addr, std, want=3, deploy_block=None):
    """-> (list of {token_id, how, bs_metadata?}), notes). Up to 3 tokens: lowest, middle, recent."""
    toks, notes = [], {}
    is1155 = "1155" in std
    if not is1155:
        calls = [(addr, SEL_TOTALSUPPLY), (addr, SEL_TBI + u256(0))] + [(addr, SEL_OWNEROF + u256(i)) for i in range(16)]
        mc = await rpc.multicall(ev, "sample_probe_low", calls)
        total, tbi0, owner_ok = None, None, []
        if mc:
            if mc[0][0] and len(mc[0][1]) == 32:
                total = int.from_bytes(mc[0][1], "big")
            if mc[1][0] and len(mc[1][1]) == 32:
                tbi0 = int.from_bytes(mc[1][1], "big")
            owner_ok = [i for i in range(16) if mc[2 + i][0] and len(mc[2 + i][1]) == 32]
        notes.update(total_supply=total, enumerable=tbi0 is not None, owner_probe_hits=owner_ok[:3])
        if total and total < 2 ** 64 and tbi0 is not None:
            idxs = sorted({0, total - 1} if want == 2 else {0, total // 2, total - 1})
            mc2 = await rpc.multicall(ev, "sample_enum", [(addr, SEL_TBI + u256(i)) for i in idxs])
            if mc2 and all(ok and len(b) == 32 for ok, b in mc2):
                cand = [(i, int.from_bytes(b, "big")) for i, (ok, b) in zip(idxs, mc2)]
                # tokenByIndex is not trustworthy on every contract (e.g. Autoglyphs returns the index itself): confirm with ownerOf
                mv = await rpc.multicall(ev, "sample_validate", [(addr, SEL_OWNEROF + u256(tid)) for _, tid in cand])
                for k, (i, tid) in enumerate(cand):
                    label = "low" if i == 0 else ("recent" if i == total - 1 else "mid")
                    how = f"tokenByIndex({i}) [{label}; totalSupply={total}]"
                    if mv and not (mv[k][0] and len(mv[k][1]) == 32):
                        mp = await rpc.multicall(ev, "sample_validate_probe", [(addr, SEL_OWNEROF + u256(tid + j)) for j in range(1, 17)])
                        hit = next((j + 1 for j in range(16) if mp and mp[j][0] and len(mp[j][1]) == 32), None)
                        if hit is None:
                            how += " (ownerOf failed; kept unvalidated)"
                        else:
                            tid, how = tid + hit, how + f" (ownerOf reverted; moved +{hit})"
                    toks.append({"token_id": tid, "how": how})
        if not toks:
            toks = await probe_721(rpc, ev, addr, total, owner_ok, want)
            if toks:
                notes["method"] = "rpc-probe"
        if not toks:
            bs = await rpc.blockscout(ev, "sample_instances", f"/tokens/{addr}/instances")
            items = _ids_from_items((bs or {}).get("items"))
            meta_by_id = {i: it.get("metadata") for i, it in items}
            ids = [i for i, _ in items]
            if not ids:
                tr = await rpc.blockscout(ev, "sample_transfers", f"/tokens/{addr}/transfers")
                ids = sorted(set(_transfer_ids((tr or {}).get("items"))))
                src = "blockscout-transfers"
            else:
                src = "blockscout-instances"
            high = max(ids) if ids else None
            low = owner_ok[0] if owner_ok else (min(ids) if ids else None)
            low_how = "ownerOf-probe(0..15)" if owner_ok else f"{src}-min"
            if high is not None:
                toks.append({"token_id": high, "how": f"{src}-max [recent]"})
            if low is not None and low != high:
                toks.append({"token_id": low, "how": f"{low_how} [low]"})
            if want == 3 and low is not None and high is not None and high - low > 2:
                base = (low + high) // 2
                mc3 = await rpc.multicall(ev, "sample_probe_mid", [(addr, SEL_OWNEROF + u256(base + i)) for i in range(16)])
                mid, how = None, None
                if mc3:
                    for i in range(16):
                        if mc3[i][0] and len(mc3[i][1]) == 32:
                            mid, how = base + i, f"ownerOf-probe({base}..+15) [mid]"
                            break
                if mid is None and len(ids) >= 3:
                    mid, how = sorted(ids)[len(ids) // 2], f"{src}-median [mid]"
                if mid is not None and mid not in (low, high):
                    toks.append({"token_id": mid, "how": how})
            notes["pool"] = sorted(set(ids))[:60]
            for t in toks:
                step = -1 if "[recent]" in t["how"] else 1
                if t["how"].startswith("ownerOf-probe"):
                    continue
                tid2, note = await validate_721(rpc, ev, addr, t["token_id"], step)
                if note:
                    t["how"] += f" ({note})"
                    t["token_id"] = tid2
                if meta_by_id.get(t["token_id"]):
                    t["bs_metadata"] = meta_by_id[t["token_id"]]
    else:
        toks = await sample_1155_logs(rpc, ev, addr, deploy_block, want)
        if toks:
            notes["method"] = "rpc-getLogs"
    if is1155 and not toks:
        bs = await rpc.blockscout(ev, "sample_instances", f"/tokens/{addr}/instances")
        items = _ids_from_items((bs or {}).get("items"))
        tids = []
        if not items:  # only spend a second Blockscout request when the instances index is empty
            tr = await rpc.blockscout(ev, "sample_transfers", f"/tokens/{addr}/transfers")
            tids = _transfer_ids((tr or {}).get("items"))
        meta_by_id = {i: it.get("metadata") for i, it in items}
        ids = sorted(set([i for i, _ in items] + tids))
        notes.update(sample_pool=len(ids), pool=ids[:60])
        if ids:
            picks = [(ids[0], "pool-min [low]")]
            if want == 3 and len(ids) > 2:
                picks.append((ids[len(ids) // 2], "pool-median [mid]"))
            picks.append((tids[0] if tids else ids[-1], "latest-transfer [recent]" if tids else "pool-max [recent]"))
            for tid, how in picks:
                if all(tid != t["token_id"] for t in toks):
                    toks.append({"token_id": tid, "how": how + (" (blockscout transfers page 1)" if tids else " (blockscout instances page 1)")})
            for t in toks:
                if meta_by_id.get(t["token_id"]):
                    t["bs_metadata"] = meta_by_id[t["token_id"]]
        else:
            # no index data: probe small ids via uri()
            mc = await rpc.multicall(ev, "sample_probe_uri", [(addr, SEL_URI + u256(i)) for i in range(0, 33)])
            if mc:
                hit = [i for i in range(33) if mc[i][0] and len(mc[i][1]) >= 64]
                if hit:
                    toks.append({"token_id": hit[0], "how": "uri-probe(0..32; no token index available) [low]"})
                    if len(hit) > 1:
                        toks.append({"token_id": hit[-1], "how": "uri-probe(0..32; no token index available) [recent?]"})
    # dedupe preserving order
    seen, out = set(), []
    for t in toks:
        if t["token_id"] not in seen:
            seen.add(t["token_id"])
            out.append(t)
    return out[:3], notes


# ----------------------------------------------------------------------------------------------
# renderer hint (best effort)
# ----------------------------------------------------------------------------------------------
B64_TABLE = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def _opcodes(code):
    i, ops = 0, set()
    n = len(code)
    while i < n:
        op = code[i]
        ops.add(op)
        i += 1 + (op - 0x5F if 0x60 <= op <= 0x7F else 0)
    return ops


async def renderer_hint(rpc, ev, addr, ontok=None):
    out = {"hint": "unknown", "tags": [], "code_size": None, "impl": None}
    r = await rpc.call(ev, "getCode", "eth_getCode", [addr, "latest"])
    if not r["ok"] or not r["result"]:
        return out
    code = bytes.fromhex(r["result"][2:])
    out["code_size"] = len(code)
    impl = None
    if len(code) <= 60 and code.startswith(bytes.fromhex("363d3d373d3d3d363d73")):
        impl = "0x" + code[10:30].hex()
        out["proxy"] = "eip1167"
    elif len(code) < 400 or b"\x36\x08\x94\xa1\x3b\xa1\xa3\x21" in code:
        s = await rpc.call(ev, "getStorageAt", "eth_getStorageAt", [addr, EIP1967_IMPL, "latest"])
        if s["ok"] and s["result"] and int(s["result"], 16) != 0:
            impl = "0x" + s["result"][-40:]
            out["proxy"] = "eip1967"
    if impl:
        out["impl"] = impl
        r2 = await rpc.call(ev, "getCode_impl", "eth_getCode", [impl, "latest"])
        if r2["ok"] and r2["result"]:
            code = bytes.fromhex(r2["result"][2:])
            out["impl_code_size"] = len(code)
    tags = []
    if B64_TABLE in code:
        tags.append("base64-encoder")
    for lit, tag in ((b"data:application/json", "json-datauri-literal"), (b"data:image/svg", "svg-datauri-literal"),
                     (b"<svg", "svg-literal"), (b"<html", "html-literal"), (b"<script", "script-literal"),
                     (b"<rect", "svg-shape-literal"), (b"<path", "svg-shape-literal"), (b"<text", "svg-text-literal")):
        if lit in code and tag not in tags:
            tags.append(tag)
    ops = _opcodes(code)
    if 0x3C in ops:
        tags.append("extcodecopy(sstore2/ethfs-style data read)")
    if 0x3B in ops and 0x3C not in ops:
        tags.append("extcodesize")
    out["tags"] = tags
    # gas cost of tokenURI relative to its output size: assembling SVG/JSON costs far more per byte than reading a stored string
    if ontok is not None:
        g = await rpc.call(ev, "estimateGas_tokenURI", "eth_estimateGas",
                           [{"to": addr, "data": "0x" + (SEL_URI if ontok.get("called_fn") == "uri" else SEL_TOKENURI) + u256(int(ontok["token_id"]))}, "latest"],
                           token_id=ontok["token_id"], attempts=2)
        if g["ok"] and g["result"]:
            gas = int(g["result"], 16)
            out["tokenuri_gas"] = gas
            ln = max(ontok.get("meta_payload_len") or 1, 1)
            out["gas_per_output_byte"] = round(gas / ln, 1)
        src = await rpc.blockscout(ev, "contract_source", f"/smart-contracts/{out.get('impl') or addr}")
        if src:
            files = [src.get("source_code") or ""] + [f.get("source_code") or "" for f in (src.get("additional_sources") or [])]
            text = "\n".join(files)
            out["source_verified"] = True
            out["source_len"] = len(text)
            for kw, tag in (("sstore2", "src:sstore2"), ("ethfs", "src:ethfs"), ("filestore", "src:ethfs"), ("scripty", "src:scripty"),
                            ("base64.encode", "src:base64"), ("<svg", "src:svg"), ("<html", "src:html"), ("irenderer", "src:renderer-iface"),
                            ("descriptor", "src:descriptor"), ("itokenuri", "src:renderer-iface")):
                if kw in text.lower() and tag not in tags:
                    tags.append(tag)
            out["tags"] = tags
        else:
            out["source_verified"] = False
    strong_src = any(t in tags for t in ("src:sstore2", "src:ethfs", "src:scripty", "src:base64", "src:svg", "src:html", "src:renderer-iface", "src:descriptor"))
    generator = any(t in tags for t in ("svg-literal", "html-literal", "script-literal", "svg-shape-literal", "svg-text-literal")) \
        or any(t.startswith("extcodecopy") for t in tags)
    if "base64-encoder" in tags and (generator or "json-datauri-literal" in tags or "svg-datauri-literal" in tags):
        out["hint"] = "renderer"
    elif generator or "json-datauri-literal" in tags:
        out["hint"] = "renderer-likely"
    elif strong_src:
        out["hint"] = "renderer-likely"
    elif out.get("tokenuri_gas", 0) >= 400_000 and out.get("gas_per_output_byte", 0) >= 120:
        out["hint"] = "renderer-by-gas"
    elif ontok is not None and "tokenuri_gas" not in out:
        out["tags"].append("estimategas-failed(likely above node gas cap)")
        out["hint"] = "renderer-by-gascap"
    else:
        out["hint"] = "no-generator-found"
    return out


# ----------------------------------------------------------------------------------------------
# Network target checking
# ----------------------------------------------------------------------------------------------
IMG_TYPES = {"png", "jpeg", "gif", "webp", "avif", "svg", "bmp", "tiff", "mp4", "webm", "glb", "mp3", "ogg", "wav"}


def judge_attempt(res, role, expect):
    """Turn one fetch result into (verdict, reason, note). verdict: alive | dead | unknown."""
    ek = res.get("error_kind")
    if ek and res.get("status") and 200 <= res["status"] < 300 and expect == "media":
        ct = (res["headers"].get("content-type") or "").lower()
        if ct.startswith(("image/", "video/", "audio/", "model/")) and ek in ("timeout", "payload-error", "conn-reset"):
            return "alive", "ok-headers-only(body-" + ek + ")"
    if ek:
        if ek in ("timeout", "dns-temp"):
            return "unknown", ek
        if ek in ("payload-error",):
            return "unknown", ek
        if ek.startswith("dns-") or ek.startswith("tls:") or ek in ("conn-refused", "unreachable", "conn-reset", "blocked-private-ip", "bad-url", "redirect-loop"):
            return "dead", ek
        return "unknown", ek
    st = res["status"]
    body = res["body"]
    text = None
    if st == 429 or st in (408, 425):
        return "unknown", f"http-{st}-rate-limited"
    if 200 <= st < 300:
        head = body[:65536]
        sn = sniff(head)
        ct = (res["headers"].get("content-type") or "").lower()
        if expect == "json":
            obj, _ = parse_json_lenient(body)
            if obj is not None and isinstance(obj, (dict, list)):
                return "alive", "ok"
            text = head.decode("utf-8", "replace")
            if sn == "svg":
                return "alive", "svg-instead-of-json"
            if sn in IMG_TYPES:  # tokenURI points straight at the media file (e.g. original Zora media contract)
                return "alive", "tokenuri-is-media:" + sn
            pk = looks_parked(text)
            if pk:
                return "dead", f"parked:{pk}"
            bw = looks_bot_wall(text)
            if bw:
                return "unknown", f"bot-wall:{bw}"
            if len(body) == 0:
                return "dead", "empty-body"
            return "dead", "not-json" + (":html" if sn == "html" else "")
        # media
        if len(body) == 0 and (res.get("content_length") or 0) == 0:
            return "dead", "empty-body"
        if sn in IMG_TYPES or ct.startswith(("image/", "video/", "audio/", "model/")):
            return "alive", "ok"
        text = head.decode("utf-8", "replace")
        if sn == "html" or ct.startswith("text/html"):
            pk = looks_parked(text)
            if pk:
                return "dead", f"parked:{pk}"
            bw = looks_bot_wall(text)
            if bw:
                return "unknown", f"bot-wall:{bw}"
            if role == "animation_url":
                return "alive", "ok-html"
            return "dead", "html-instead-of-media"
        if sn == "json?" or ct.startswith("application/json"):
            return ("alive", "ok-json") if role == "animation_url" else ("dead", "json-instead-of-media")
        return "alive", "ok-unverified-type"
    if st in (401, 403) or st == 503:
        text = body[:65536].decode("utf-8", "replace")
        bw = looks_bot_wall(text)
        if bw or (res["headers"].get("server", "").lower() == "cloudflare" and st in (403, 503) and "ray" in str(res["headers"])):
            return "unknown", f"bot-wall:http-{st}"
    if 400 <= st < 500:
        return "dead", f"http-{st}"
    if st >= 500:
        return "dead", f"http-{st}"
    return "dead", f"http-{st}"


def gw_url(gw, cid, path, ipns=False):
    return f"https://{gw}/{'ipns' if ipns else 'ipfs'}/{cid}{path or ''}"


def plan_urls(target, pass_no):
    """Ordered list of (gateway_label, url) to try for this target in this pass."""
    c = target["cls"]
    urls = []
    if c == "http":
        return [(target.get("host"), target["uri"])]
    if c == "ipfs":
        hard = target.get("gateway")
        walled = set(g for g, s in GW_STATE["status"].items() if s.get("state") == "bot-walled")
        if hard and target.get("scheme") in ("https", "http") and hard not in GW_STATE["status"] and hard not in GW_STATE["ipfs_ok"]:
            urls.append((hard, target["uri"]))
        gws = list(GW_STATE["ipfs_ok"][:4] if pass_no == 1 else GW_STATE["ipfs_ok"])  # pass 1: the 4 fast gateways; pass 2: all
        if gws:
            k = int(hashlib.md5(target["cid"].encode()).hexdigest(), 16) % len(gws)
            gws = gws[k:] + gws[:k]
        if hard in gws and hard not in [u[0] for u in urls] and target.get("scheme") in ("https", "http"):
            gws.remove(hard)
            gws.insert(0, hard)
        if pass_no == 1:
            gws = gws[:2]
        else:  # pass 2: gateways not yet tried for this target first, at most 4
            tried = {a.get("gateway") for a in target.get("attempts", [])}
            gws = sorted(gws, key=lambda g: g in tried)[:4]
        urls += [(g, gw_url(g, target["cid"], target.get("path"))) for g in gws if g not in walled]
        seen, out = set(), []
        for g, u in urls:
            if u not in seen:
                seen.add(u)
                out.append((g, u))
        return out
    if c == "arweave":
        hard = target.get("gateway")
        gws = list(GW_STATE["ar_ok"])
        if hard and hard not in GW_STATE["status"]:
            urls.append((hard, target["uri"]))  # an unknown/dedicated gateway: try the URL as written
        if target.get("ar_id"):
            if hard in gws:
                gws.remove(hard)
                gws.insert(0, hard)
            urls += [(g, f"https://{g}/{target['ar_id']}{target.get('path') or ''}") for g in gws]
        return urls[: (3 if pass_no == 1 else 5)]
    return urls


def target_verdict(t):
    """Compute (verdict, reason, needs_retry) from t['attempts']."""
    att = [a for a in t["attempts"] if not a.get("skipped")]
    alive = [a for a in att if a["v"] == "alive"]
    if alive:
        return "alive", alive[-1]["reason"], False
    passes = {a["pass"] for a in att}
    neg = [a for a in att if a["v"] == "dead"]
    done2 = 2 in passes
    if not att:
        return "unknown", "no-usable-gateway", not done2
    if t["cls"] in ("ipfs", "arweave"):
        gws_neg = {a["gateway"] for a in neg}
        reasons = Counter(a["reason"] for a in neg)
        if len(gws_neg) >= 2 and done2:
            return "dead", "gateway-not-found:" + reasons.most_common(1)[0][0], False
        if neg:
            return "unknown", "dead-candidate:" + reasons.most_common(1)[0][0], not done2
        return "unknown", Counter(a["reason"] for a in att).most_common(1)[0][0], not done2
    negp = {a["pass"] for a in neg}
    if len(negp) >= 2:
        return "dead", neg[-1]["reason"], False
    if neg and not done2:
        return "unknown", "dead-candidate:" + neg[-1]["reason"], True
    if neg and done2:  # failed in one pass, unknown in the other
        return "unknown", "mixed:" + neg[-1]["reason"], False
    return "unknown", att[-1]["reason"], not done2


def exact_url_verdict(t):
    """Verdict for the URL exactly as written in the token data. Differs from t['verdict'] (content-level: any gateway)
    only when the URL names a specific IPFS/Arweave gateway. -> (verdict, reason)"""
    hard = t.get("gateway")
    if t["cls"] not in ("ipfs", "arweave") or not hard or t.get("scheme") not in ("https", "http"):
        return t["verdict"], t["reason"]
    st = GW_STATE["status"].get(hard, {}).get("state")
    if hard in GW_EXCLUDE:
        return "unknown", "gateway-excluded-rate-limits-bots"
    if st == "bot-walled":
        return "unknown", "gateway-bot-walled"
    if st and st.startswith("dead"):
        return "dead", "gateway-" + st
    if st == "wrong-content":
        return "dead", "gateway-wrong-content"
    att = [a for a in t["attempts"] if a.get("gateway") == hard]
    if any(a["v"] == "alive" for a in att):
        return "alive", "ok"
    if not att:
        return "unknown", "exact-url-not-attempted"
    neg = {a["pass"] for a in att if a["v"] == "dead"}
    if len(neg) >= 2:
        return "dead", att[-1]["reason"]
    return "unknown", att[-1]["reason"]


FETCH_CACHE = {}  # url -> (response dict incl. body for json / sans body for media, "addr/seq" reference). Pass-1 only.
CACHE_MAX = 30000


async def cached_fetch(net, ev, url, expect, timeout, pass_no):
    """net.fetch with an in-process cache (many collections share a CID root / host path). Cache hits are still logged in
    the collection's evidence with `cached_from` pointing at the evidence line (dir/seq) that holds the raw body."""
    key = (url, expect)
    if pass_no == 1 and key in FETCH_CACHE:
        res, ref = FETCH_CACHE[key]
        return dict(res), ref
    res = await net.fetch(url, max_bytes=65_536 if expect == "media" else 1_000_000, timeout=timeout,
                          accept="application/json,*/*" if expect == "json" else None)
    return res, None


def cache_put(url, expect, res, ref):
    if res.get("error_kind") in ("timeout", "dns-temp") or res.get("status") in (429, 408, 425) or len(FETCH_CACHE) >= CACHE_MAX:
        return
    r2 = dict(res)
    if expect == "json" and len(r2["body"]) > 262144:
        return
    if expect == "media":
        r2["body"] = r2["body"][:2048]  # enough to re-judge (magic bytes / html sniff)
    FETCH_CACHE[(url, expect)] = (r2, ref)


async def check_target(net, ev, t, tid, pass_no, expect):
    """Fetch a network target; append attempts; set verdict. Returns body bytes of a successful attempt else None."""
    t.setdefault("attempts", [])
    plan = plan_urls(t, pass_no)
    if t["cls"] == "ipfs" and t.get("gateway") and GW_STATE["status"].get(t["gateway"], {}).get("state") == "bot-walled":
        t["hardcoded_gateway_state"] = "bot-walled"
    elif t["cls"] in ("ipfs", "arweave") and t.get("gateway"):
        t["hardcoded_gateway_state"] = GW_STATE["status"].get(t["gateway"], {}).get("state", "untested")
    body_ok = None
    timeout = 15.0 if pass_no == 1 else 30.0
    for gw, url in plan:
        res, cref = await cached_fetch(net, ev, url, expect, timeout, pass_no)
        v, reason = judge_attempt(res, t["role"], expect)
        rec = ev.record(kind="fetch", role=t["role"], url=url, method="GET", status=res["status"], error=res["error"],
                        error_kind=res["error_kind"], body=(res["body"] if res["status"] and cref is None else (b"" if res["status"] else None)),
                        store_cap=1_000_000 if expect == "json" else 4096, token_id=tid, sha256=res["sha256"],
                        size=res["bytes_read"], retrieved_at=res["retrieved_at"],
                        extra={"cached_from": cref, "final_url": res["final_url"], "redirects": res["redirects"], "content_type": res["headers"].get("content-type"),
                               "content_length": res["content_length"], "truncated": res["truncated"], "verdict": v, "reason": reason,
                               "gateway": gw, "pass": pass_no, "elapsed": res["elapsed"], "reg_domain_dns": res.get("reg_domain_dns")})
        if cref is None and pass_no == 1:
            cache_put(url, expect, res, f"{ev.dir.name}#{rec['seq']}")
        t["attempts"].append({"pass": pass_no, "gateway": gw, "url": url[:300], "status": res["status"], "error_kind": res["error_kind"],
                              "v": v, "reason": reason, "seq": rec["seq"], "final_url": res["final_url"][:300],
                              "content_type": res["headers"].get("content-type"), "size": res["bytes_read"],
                              "content_length": res["content_length"], "sha256": res["sha256"], "t": res["retrieved_at"],
                              "reg_domain_dns": res.get("reg_domain_dns"), "redirected": bool(res["redirects"])})
        if v == "alive":
            body_ok = res["body"]
            t["sha256"], t["size"] = res["sha256"], res["bytes_read"]
            t["content_type"] = res["headers"].get("content-type")
            t["content_length"] = res["content_length"]
            t["sniff"] = sniff(res["body"][:2048])
            break
    t["verdict"], t["reason"], t["needs_retry"] = target_verdict(t)
    t["exact_verdict"], t["exact_reason"] = exact_url_verdict(t)
    return body_ok


# ----------------------------------------------------------------------------------------------
# Token processing
# ----------------------------------------------------------------------------------------------
def new_target(role, uri, c):
    t = {"role": role, "uri": (c.get("fetch_uri") or uri).strip()[:2000], "orig_uri": uri[:2000], "quirk": c.get("quirk"), "cls": c["cls"], "scheme": c.get("scheme"), "host": c.get("host"),
         "reg_domain": c.get("reg_domain"), "gateway": c.get("gateway"), "cid": c.get("cid"), "path": c.get("path"),
         "ar_id": c.get("ar_id"), "attempts": [], "verdict": "unknown", "reason": "not-attempted", "needs_retry": True}
    return t


def analyse_onchain(payload, mime_hint=None):
    """Inspect decoded on-chain bytes. -> dict(kind, obj?, refs, mentions)."""
    sn = sniff(payload[:2048])
    out = {"sniff": sn, "kind": None, "refs": [], "mentions": []}
    mh = (mime_hint or "")
    if "json" in mh or sn in ("json?", None):
        obj, note = parse_json_lenient(payload)
        if obj is not None:
            out["kind"], out["obj"] = "json", obj
            return out
    if sn == "svg" or "svg" in mh:
        out["kind"] = "svg"
    elif sn == "html" or "html" in mh:
        out["kind"] = "html"
    elif sn in IMG_TYPES:
        out["kind"] = sn
    else:
        out["kind"] = "other"
    if out["kind"] in ("svg", "html"):
        text = payload.decode("utf-8", "replace")
        out["refs"], out["mentions"] = scan_external(text)
    return out


def media_entry(field, key, value, tid):
    """Classify one media field; for on-chain values decode + scan. Returns (entry, target_or_None)."""
    c = classify_media_value(field, value)
    e = {"field": field, "key": key, "cls": c["cls"], "reason": c.get("reason"), "scheme": c.get("scheme"),
         "host": c.get("host"), "reg_domain": c.get("reg_domain"), "gateway": c.get("gateway"), "cid": c.get("cid"),
         "mime": c.get("mime"), "encoding": c.get("encoding"), "size": c.get("size"), "external_refs": [], "external_mentions": []}
    tgt = None
    if c["cls"] == "data-uri":
        try:
            if c.get("scheme") == "raw":
                payload = (value if isinstance(value, str) else "").strip().encode("utf-8", "replace")
            else:
                payload = parse_data_uri(value.strip())["payload"]
            a = analyse_onchain(payload, c.get("mime"))
            e["onchain_kind"] = a["kind"]
            e["external_refs"], e["external_mentions"] = a["refs"], a["mentions"]
            e["payload_sha256"] = hashlib.sha256(payload).hexdigest()
            if a["kind"] == "json":
                e["onchain_kind"] = "json-not-media"
        except ValueError as ex:
            e["cls"], e["reason"] = "broken", f"data-undecodable:{ex}"
    elif c["cls"] in ("ipfs", "arweave", "http"):
        tgt = new_target(field, value.strip(), c)
    return e, tgt


async def resolve_token(net, ev, t, pass_no):
    """Phase B: fetch metadata (if network) and media; fill t['meta_target'], t['media'] etc. Idempotent for retry."""
    tid = t["token_id"]
    mt = t.get("meta_target")
    if mt and (pass_no == 1 and not mt["attempts"] or pass_no >= 2 and mt["verdict"] != "alive"):
        body = await check_target(net, ev, mt, tid, pass_no, "json")
        if body is not None:
            obj, note = parse_json_lenient(body)
            t["meta_obj_ok"] = obj is not None
            if obj is None:
                t["meta_fields"] = []
                t["meta_note"] = "tokenURI target is not JSON (media served directly)"
            if isinstance(obj, dict):
                t["meta_fields"] = media_fields_from(obj)
                t["meta_name"] = str(obj.get("name"))[:120] if obj.get("name") is not None else None
            elif obj is not None:
                t["meta_fields"] = []
    # media from metadata
    if "media" not in t and t.get("meta_fields") is not None:
        t["media"] = []
        for field, key, value in t["meta_fields"]:
            e, tgt = media_entry(field, key, value, tid)
            if tgt:
                e["target"] = tgt
            t["media"].append(e)
    for e in t.get("media", []):
        tg = e.get("target")
        if tg and ((pass_no == 1 and not tg["attempts"]) or (pass_no >= 2 and tg["verdict"] != "alive")):
            await check_target(net, ev, tg, tid, pass_no, "media")


def media_fields_from(obj):
    return [(f, k, v) for f, k, v in extract_media(obj)]


async def process_token(rpc, net, ev, addr, std, samp, renderer):
    tid = samp["token_id"]
    t = {"token_id": str(tid), "how_found": samp["how"], "rpc": None, "uri": None, "meta_class": "broken", "meta_reason": None}
    is1155 = "1155" in std
    order = [("uri", SEL_URI), ("tokenURI", SEL_TOKENURI)] if is1155 else [("tokenURI", SEL_TOKENURI), ("uri", SEL_URI)]
    tried = []
    uri_raw = None
    for name, sel in order:
        r = await rpc.eth_call(ev, f"eth_call_{name}", addr, sel + u256(tid), token_id=str(tid))
        entry = {"fn": name, "calldata": "0x" + sel + u256(tid), "endpoint": r.get("endpoint"), "ok": r["ok"], "revert": r["revert"],
                 "error": r["error"], "raw_result_len": len(r["result"]) if r["result"] else 0}
        if r["revert"]:
            # a revert on the capped public nodes may be a gas-cap artifact: retry on high-gas-cap nodes
            for fb in RPC_FALLBACK:
                r2 = await rpc.eth_call(ev, f"eth_call_{name}_fallback", addr, sel + u256(tid), token_id=str(tid), endpoints=[fb], attempts=2)
                entry.setdefault("fallback", []).append({"endpoint": fb, "ok": r2["ok"], "revert": r2["revert"], "error": r2["error"]})
                if r2["ok"]:
                    s2, _ = decode_abi_string(r2["result"])
                    if s2 is not None and s2.strip():
                        entry["revert_gas_cap_suspected"] = True
                        t["revert_gas_cap_suspected"] = True
                        r = r2
                        entry.update(endpoint=fb, ok=True, revert=False, error=None,
                                     raw_result_len=len(r2["result"]), primary_revert_error=entry["error"])
                        break
                if not r2["revert"] and not r2["ok"]:
                    continue
            if not entry.get("revert_gas_cap_suspected"):
                entry["revert_confirmed_on_fallback"] = any(f["revert"] for f in entry.get("fallback", []))
        if r["ok"]:
            s, note = decode_abi_string(r["result"])
            entry.update(decoded_ok=s is not None, note=note)
            if s is not None and s.strip():
                tried.append(entry)
                uri_raw, t["called_fn"] = s, name
                break
            entry["empty_or_bad"] = True
        tried.append(entry)
        if not r["ok"] and not r["revert"]:  # infra problem: do not fall through to the other selector as if it were a revert
            break
    t["rpc"] = tried
    if uri_raw is None:
        infra = tried and not tried[-1]["ok"] and not tried[-1]["revert"]
        t["meta_class"] = "broken"
        t["meta_reason"] = "rpc-error" if infra else ("revert" if any(x["revert"] for x in tried) else "empty-or-undecodable")
        t["rpc_infra_failure"] = bool(infra)
        return t
    t["uri_raw"] = uri_raw[:1000]
    t["uri_raw_len"] = len(uri_raw)
    uri = (substitute_id(uri_raw, tid) if "{id}" in uri_raw else uri_raw).strip()
    t["id_substituted"] = uri != uri_raw
    c = classify_uri(uri)
    t.update(meta_class=c["cls"], meta_reason=c.get("reason"), meta_scheme=c.get("scheme"), meta_host=c.get("host"),
             meta_reg_domain=c.get("reg_domain"), meta_gateway=c.get("gateway"), meta_cid=c.get("cid"),
             meta_encoding=c.get("encoding"), meta_mime=c.get("mime"))
    if c["cls"] == "data-uri":
        try:
            payload = uri.strip().encode("utf-8", "replace") if c.get("scheme") == "raw" else parse_data_uri(uri.strip())["payload"]
        except ValueError as ex:
            t["meta_class"], t["meta_reason"] = "broken", f"data-undecodable:{ex}"
            return t
        a = analyse_onchain(payload, c.get("mime"))
        t["meta_payload_kind"] = a["kind"]
        t["meta_payload_sha256"] = hashlib.sha256(payload).hexdigest()
        t["meta_payload_len"] = len(payload)
        if renderer and renderer.get("hint") in ("renderer", "renderer-likely"):
            t["meta_class"] = "onchain-renderer"
        if a["kind"] == "json":
            obj = a["obj"]
            t["meta_obj_ok"] = True
            t["meta_name"] = str(obj.get("name"))[:120] if isinstance(obj, dict) and obj.get("name") is not None else None
            t["meta_fields"] = media_fields_from(obj) if isinstance(obj, dict) else []
            t["meta_json_keys"] = sorted(obj.keys())[:30] if isinstance(obj, dict) else None
        elif a["kind"] != "json":
            # tokenURI returns the artwork itself (svg / html / plain-text art / image bytes)
            t["meta_reason"] = f"tokenuri-is-artwork({a['kind']})"
            t["media"] = [{"field": "image", "key": "(tokenURI itself)", "cls": "data-uri", "onchain_kind": a["kind"],
                           "external_refs": a["refs"], "external_mentions": a["mentions"], "mime": c.get("mime"),
                           "encoding": c.get("encoding"), "size": len(payload)}]
            t["meta_fields"] = []
    elif c["cls"] in ("ipfs", "arweave", "http"):
        t["meta_target"] = new_target("metadata", uri, c)
    if "bs_metadata" in samp and samp["bs_metadata"]:
        t["bs_cache_fields"] = [(f, k, v) for f, k, v in extract_media(samp["bs_metadata"])] if isinstance(samp["bs_metadata"], dict) else []
    await resolve_token(net, ev, t, 1)
    return t


# ----------------------------------------------------------------------------------------------
# Derivations
# ----------------------------------------------------------------------------------------------
ONCHAIN = ("data-uri", "onchain-renderer")


def derive_token(t):
    """Fill t['derived'] from stored raw judgements (recomputed after retry). Content-level liveness (any gateway
    serving the CID counts) plus `*_exact` fields judged on the URL exactly as written in the token data."""
    d = _derive(t, False)
    e = _derive(t, True)
    d["liveness_exact"], d["liveness_exact_reason"] = e["liveness"], e["liveness_reason"]
    d["meta_verdict_exact"], d["image_verdict_exact"] = e["meta_verdict"], e["image_verdict"]
    d["anim_verdict_exact"] = e["anim_verdict"]
    d["meta_verdict_exact_reason"] = e["meta_verdict_reason"]
    t["derived"] = d
    return d


def _derive(t, exact):
    def V(tg):
        return tg.get("exact_verdict", tg["verdict"]) if exact else tg["verdict"]

    def R(tg):
        return tg.get("exact_reason", tg["reason"]) if exact else tg["reason"]
    d = {}
    mc = t["meta_class"]
    mt = t.get("meta_target")
    if mc in ONCHAIN:
        mv, mr = "n/a-onchain", None
    elif mt:
        mv, mr = V(mt), R(mt)
    elif mc == "broken":
        mv, mr = ("unknown", "rpc-error") if t.get("rpc_infra_failure") else ("dead", f"tokenuri-{t.get('meta_reason')}")
    else:  # other schemes (ipns, bzz...) we cannot fetch
        mv, mr = "unknown", f"unfetchable-scheme:{t.get('meta_scheme')}"
    d["meta_verdict"], d["meta_verdict_reason"] = mv, mr
    media = t.get("media")
    if media is None:
        # metadata unreachable or not JSON: fall back to Blockscout's cached copy for CLASS only
        fb = t.get("bs_cache_fields")
        if fb and t.get("meta_target") and mv not in ("alive", "n/a-onchain"):
            ents = [media_entry(f, k, v, t["token_id"])[0] for f, k, v in fb]
            d["media_class_source"] = "blockscout-cache"
            media = ents
        else:
            media = []
    else:
        d["media_class_source"] = "live-metadata"
    img = next((m for m in media if m["field"] == "image"), None) or next((m for m in media if m["field"] == "image_data"), None)
    anim = next((m for m in media if m["field"] == "animation_url"), None)
    d["image_class"] = img["cls"] if img else None
    d["anim_class"] = anim["cls"] if anim else None

    def mver(m):
        if m is None:
            return None
        if m["cls"] in ONCHAIN:
            return "n/a-onchain"
        if m["cls"] == "broken":
            return "dead"
        tg = m.get("target")
        return V(tg) if tg else "unknown"
    d["image_verdict"], d["anim_verdict"] = mver(img), mver(anim)
    all_refs = []
    for m in media:
        all_refs += m.get("external_refs") or []
    if mc in ONCHAIN and t.get("media") and not t.get("meta_fields"):
        pass
    d["external_refs"] = sorted(set(all_refs))
    d["n_external_mentions"] = sum(len(m.get("external_mentions") or []) for m in media)
    d["media_field_classes"] = {m["field"]: m["cls"] for m in media}
    # truly-on-chain candidate: metadata on-chain and every media field on-chain, none external
    media_all_on = bool(media) and all(m["cls"] in ONCHAIN for m in media)
    d["onchain_candidate"] = bool(mc in ONCHAIN and media_all_on)
    d["onchain_candidate_clean"] = bool(d["onchain_candidate"] and not d["external_refs"])
    # liveness
    iv = d["image_verdict"]
    if mv == "dead":
        lv, lr = "dead", mr
    elif mv == "unknown":
        lv, lr = "unknown", mr
    else:  # metadata fine or on-chain
        if img is None and not media:
            lv, lr = ("alive", "no-media-field") if mv in ("alive", "n/a-onchain") else ("unknown", mr)
        elif iv in ("alive", "n/a-onchain"):
            lv, lr = "alive", None
        elif iv == "dead":
            lv, lr = "degraded", f"media-dead:{R(img['target']) if img.get('target') else img.get('reason')}"
        else:
            lv, lr = "unknown", f"media-unknown:{R(img['target']) if img and img.get('target') else None}"
    d["liveness"], d["liveness_reason"] = lv, lr
    return d


def needs_retry_any(t):
    mt = t.get("meta_target")
    if mt and mt["verdict"] != "alive" and mt.get("needs_retry"):
        return True
    for m in t.get("media", []) or []:
        tg = m.get("target")
        if tg and tg["verdict"] != "alive" and tg.get("needs_retry"):
            return True
    return False


# ----------------------------------------------------------------------------------------------
# Collection driver
# ----------------------------------------------------------------------------------------------
async def run_collection(rpc, net, row, force=False):
    addr = row["address"].lower()
    d = RAW / addr
    if has_result(d) and not force:
        return None
    if d.exists() and force:
        for p in d.iterdir():
            p.unlink()
    ev = Evidence(RAW, addr)
    res = {"address": addr, "name": row.get("name"), "standard": row.get("standard"), "holders_count": row.get("holders_count"),
           "deploy_year": row.get("deploy_year"), "spam_suspect": row.get("spam_suspect"), "started_at": now_iso(), "pass": 1}
    try:
        std = str(row.get("standard") or "")
        try:
            hc = float(row.get("holders_count") or 0)
        except (TypeError, ValueError):
            hc = 0
        want = 2 if hc < 1000 else 3  # collections with <1,000 holders: 2 tokens (low + recent)
        res["sample_stratum"] = row.get("sample_stratum")
        samples, notes = await sample_tokens(rpc, ev, addr, std, want=want, deploy_block=row.get("deploy_block"))
        res["sampling"] = notes
        res["n_sampled"] = len(samples)
        toks = []
        if samples:
            toks = await asyncio.gather(*[process_token_wrapper(rpc, net, ev, addr, std, s) for s in samples])
        res["tokens"] = list(toks)
        await resample_reverted(rpc, net, ev, addr, std, res, notes.get("pool") or [])
        # renderer hint only if some token has on-chain metadata
        if any(t["meta_class"] == "data-uri" for t in res["tokens"]):
            ontok = next(t for t in res["tokens"] if t["meta_class"] == "data-uri")
            res["renderer"] = await renderer_hint(rpc, ev, addr, ontok)
            if res["renderer"]["hint"] in ("renderer", "renderer-likely", "renderer-by-gas", "renderer-by-gascap"):
                for t in res["tokens"]:
                    if t["meta_class"] == "data-uri":
                        t["meta_class"] = "onchain-renderer"
        for t in res["tokens"]:
            derive_token(t)
        res["finished_at"] = now_iso()
    except Exception:  # noqa: BLE001
        res["crash"] = traceback.format_exc()[-3000:]
    ev.flush()
    save_result(d, res)
    return res


async def resample_reverted(rpc, net, ev, addr, std, res, pool):
    """If some sampled tokens returned a URI but others reverted (burned / never-minted ids from stale indexer data),
    replace each reverted token by up to 2 other ids so a few dead ids do not condemn a working collection. Reverted
    originals are kept in res['discarded_tokens']. If ALL sampled tokens revert the collection is genuinely broken."""
    toks = res["tokens"]
    bad = [i for i, t in enumerate(toks) if t["meta_class"] == "broken" and t.get("meta_reason") == "revert"]
    if not bad or len(bad) == len(toks) or not pool:
        return
    used = {int(t["token_id"]) for t in toks}
    res["discarded_tokens"] = []
    for i in bad:
        orig = toks[i]
        hi = "[recent]" in orig["how_found"]
        want = int(orig["token_id"])
        cands = sorted((p for p in pool if p not in used), key=lambda p: abs(p - want))[:2]
        for c in cands:
            used.add(c)
            if "1155" not in std:
                c, _ = await validate_721(rpc, ev, addr, c, -1 if hi else 1)
            t2 = await process_token_wrapper(rpc, net, ev, addr, std, {"token_id": c, "how": f"resample (replaces reverted id {want}) [{orig['how_found'][:40]}]"})
            if not (t2["meta_class"] == "broken" and t2.get("meta_reason") == "revert"):
                res["discarded_tokens"].append({"token_id": orig["token_id"], "how_found": orig["how_found"], "meta_reason": "revert"})
                toks[i] = t2
                break
            res["discarded_tokens"].append({"token_id": t2["token_id"], "how_found": t2["how_found"], "meta_reason": "revert"})


async def process_token_wrapper(rpc, net, ev, addr, std, s):
    # renderer is resolved after tokens exist; class upgraded afterwards in run_collection
    try:
        return await process_token(rpc, net, ev, addr, std, s, None)
    except Exception:  # noqa: BLE001
        return {"token_id": str(s["token_id"]), "how_found": s["how"], "meta_class": "broken", "meta_reason": "pipeline-crash",
                "crash": traceback.format_exc()[-1500:], "rpc": None}


async def retry_collection(net, addr, min_age):
    d = RAW / addr
    res = load_result(d)
    if res.get("crash") or res.get("pass", 1) >= 2:
        return False
    ev = Evidence(RAW, addr)
    todo = [t for t in res["tokens"] if needs_retry_any(t)]
    if todo:
        await asyncio.gather(*[retry_token(net, ev, t) for t in todo])
    for t in res["tokens"]:
        derive_token(t)
    res["pass"] = 2
    res["retried_at"] = now_iso()
    ev.flush()
    save_result(d, res)
    return True


def unknown_any(t):
    mt = t.get("meta_target")
    if mt and mt["verdict"] == "unknown":
        return True
    return any((m.get("target") or {}).get("verdict") == "unknown" for m in t.get("media", []) or [])


async def retry3_collection(net, addr):
    """Third pass (follow-up measurement): re-fetch the targets that are still `unknown` after pass 2 (timeouts etc.)."""
    d = RAW / addr
    res = load_result(d)
    if res.get("crash") or res.get("pass", 1) != 2:
        return False
    todo = [t for t in res["tokens"] if unknown_any(t)]
    if not todo:
        return False
    ev = Evidence(RAW, addr)
    await asyncio.gather(*[retry_token(net, ev, t, 3) for t in todo])
    for t in res["tokens"]:
        derive_token(t)
    res["pass"] = 3
    res["retried3_at"] = now_iso()
    ev.flush()
    save_result(d, res)
    return True


async def retry_token(net, ev, t, pass_no=2):
    try:
        await resolve_token(net, ev, t, pass_no)
    except Exception:  # noqa: BLE001
        t["retry_crash"] = traceback.format_exc()[-800:]


# ----------------------------------------------------------------------------------------------
# Gateway canary
# ----------------------------------------------------------------------------------------------
async def cmd_gateways(args):
    net = Net()
    await net.start()
    ev = Evidence(RAW, "_gateways")
    net.throttle.default_interval = 0.05
    status = {}
    # a 2nd, less popular CID: ENS-style dag-pb object (go-ipfs README directory) to separate real gateways from cache-only proxies
    async def one(gw, kind):
        if kind == "ipfs":
            url = f"https://{gw}/ipfs/{BAYC_META}"
        else:
            url = f"https://{gw}/info"
        res = await net.fetch(url, max_bytes=20000, timeout=25.0)
        st = {"url": url, "status": res["status"], "error_kind": res["error_kind"], "elapsed": res["elapsed"], "final_url": res["final_url"]}
        body = res["body"]
        txt = body[:3000].decode("utf-8", "replace")
        if res["error_kind"]:
            st["state"] = "dead:" + res["error_kind"]
        elif res["status"] == 200 and (('"image"' in txt and "ipfs://" in txt) if kind == "ipfs" else '"network"' in txt):
            st["state"] = "ok"
        elif res["status"] in (403, 429) or looks_bot_wall(txt) or "blocked" in txt.lower()[:200] or "service worker" in txt.lower():
            st["state"] = "bot-walled"
        elif res["status"] == 200:
            st["state"] = "wrong-content"
        else:
            st["state"] = f"dead:http-{res['status']}"
        if "ipfs.io" in (res["final_url"] or "") and gw != "ipfs.io" and st["state"] == "bot-walled":
            st["note"] = "redirects to bot-walled ipfs.io"
        ev.record(kind="canary", role=f"gateway_{kind}", url=url, method="GET", status=res["status"], error=res["error"],
                  error_kind=res["error_kind"], body=body, store_cap=4096, sha256=res["sha256"], extra={"state": st["state"]})
        status[gw] = st

    await asyncio.gather(*([one(g, "ipfs") for g in IPFS_CANDIDATES] + [one(g, "ar") for g in AR_CANDIDATES]))
    ipfs_ok = [g for g in IPFS_CANDIDATES if status[g]["state"] == "ok"]
    ar_ok = [g for g in AR_CANDIDATES if status[g]["state"] == "ok"]
    out = {"tested_at": now_iso(), "ipfs_ok": ipfs_ok, "ar_ok": ar_ok, "status": status}
    jdump(OUT / "gateways.json", out)
    for g, s in status.items():
        print(g.ljust(32), s["state"], s["status"], s["error_kind"] or "", s.get("note", ""))
    await net.close()


# ----------------------------------------------------------------------------------------------
# run / retry / aggregate
# ----------------------------------------------------------------------------------------------
SAMPLE_SEED = 20261021
N_RANDOM, N_SPAM = 3000, 500


def _draw(addrs, n, name, universe_rows, ready):
    """Fixed-seed uniform sample over sorted addresses; persisted so the sample is reproducible and survives restarts.
    Re-drawn only when the universe grew AND READY appeared after a partial draw."""
    p = OUT / f"sample_{name}.json"
    if p.exists():
        d = json.load(open(p))
        if not (ready and d.get("ready_marker") != "READY"):
            return d["addresses"]
        p.rename(OUT / f"sample_{name}.partial-universe-{d.get('universe_rows')}.json")
    addrs = sorted(addrs)
    pick = random.Random(SAMPLE_SEED).sample(addrs, min(n, len(addrs)))
    jdump(p, {"seed": SAMPLE_SEED, "n": len(pick), "universe_rows": universe_rows, "stratum_population": len(addrs),
              "ready_marker": "READY" if ready else "READY_PARTIAL", "drawn_at": now_iso(), "addresses": pick})
    return pick


def plan_universe(spam_mode):
    """Work order: (a) uniform random sample of 3,000 non-spam [stratum random]; (b) every other non-spam by holders desc
    [top]; (c) a random 500 of the spam-suspect rows [spam-random]. spam_mode: 'skip' = (a)+(b), 'only' = (c), 'all' = a,b,c."""
    import duckdb
    df = duckdb.connect().execute(f"select * from read_parquet('{UNIVERSE}')").df()
    df["address"] = df["address"].str.lower()
    sp = df["spam_suspect"].fillna(False).astype(bool)
    ready = (UNIVERSE.parent / "READY").exists()
    non, spam = df[~sp], df[sp]
    rnd = _draw(non["address"].tolist(), N_RANDOM, "random", len(df), ready)
    spm = _draw(spam["address"].tolist(), N_SPAM, "spam", len(df), ready)
    by = non.set_index("address")
    rows = []
    if spam_mode in ("skip", "all"):
        for a in rnd:
            if a in by.index:
                r = by.loc[a].to_dict()
                r.update(address=a, sample_stratum="random")
                rows.append(r)
        rs = set(rnd)
        rest = non[~non["address"].isin(rs)].sort_values("holders_count", ascending=False)
        for r in rest.to_dict("records"):
            r["sample_stratum"] = "top"
            rows.append(r)
    if spam_mode in ("only", "all"):
        sidx = spam.set_index("address")
        for a in spm:
            if a in sidx.index:
                r = sidx.loc[a].to_dict()
                r.update(address=a, sample_stratum="spam-random")
                rows.append(r)
    return rows


def stratum_of(addr, res=None):
    """Stratum is defined by the *current* persisted sample files only (results processed under an older, superseded draw
    keep valid data but are 'top' unless they are also members of the current sample)."""
    for name, label in (("random", "random"), ("spam", "spam-random")):
        p = OUT / f"sample_{name}.json"
        if p.exists():
            if not hasattr(stratum_of, name):
                setattr(stratum_of, name, set(json.load(open(p))["addresses"]))
            if addr in getattr(stratum_of, name):
                return label
    return "spam-other" if (res or {}).get("spam_suspect") in (True, "True") else "top"


def load_rows(which, spam, limit, seedfile=None):
    import duckdb
    if which == "seed":
        import csv
        rows = list(csv.DictReader(open(seedfile or OUT / "seed.csv")))
        for r in rows:
            r.setdefault("spam_suspect", "False")
        return rows[:limit] if limit else rows
    rows = plan_universe(spam)
    return rows[:limit] if limit else rows


async def cmd_run(args):
    load_gateways()
    rows = load_rows(args.list, args.spam, args.limit, args.seedfile)
    if args.addresses:
        keep = {l.strip().lower() for l in open(args.addresses) if l.strip()}
        rows = [r for r in rows if r["address"].lower() in keep]
    def need(r):
        d = RAW / r["address"].lower()
        if not has_result(d):
            return True
        if args.redo_crashed:
            try:
                return bool(load_result(d).get("crash"))
            except Exception:  # noqa: BLE001
                return True
        return False
    todo = [r for r in rows if args.force or need(r)]
    redo = args.redo_crashed
    log(f"run start: list={args.list} spam={args.spam} rows={len(rows)} todo={len(todo)} conc={args.concurrency} pid={os.getpid()}")
    net = Net()
    await net.start()
    for g in GW_STATE["ipfs_ok"] + GW_STATE["ar_ok"]:
        net.throttle.configure(g, interval=0.4, conc=10)  # <= 2.5 req/s per public gateway
    rpc = Rpc(net)
    sem = asyncio.Semaphore(args.concurrency)
    stats = Counter()
    t0 = time.time()
    done = 0

    async def worker(r):
        nonlocal done
        async with sem:
            try:
                res = await asyncio.wait_for(run_collection(rpc, net, r, force=args.force or redo), 1500)
            except asyncio.TimeoutError:
                # a few collections hung for >1 h in an earlier run (cause not found); never let that pin a worker slot
                res = {"address": r["address"].lower(), "name": r.get("name"), "standard": r.get("standard"),
                       "holders_count": r.get("holders_count"), "deploy_year": r.get("deploy_year"),
                       "spam_suspect": r.get("spam_suspect"), "sample_stratum": r.get("sample_stratum"), "tokens": [],
                       "crash": "collection-timeout-1500s (re-run with --force --addresses)"}
                save_result(RAW / r["address"].lower(), res)
                log(f"collection timeout {r['address']}")
        done += 1
        if res is None:
            return
        if res.get("crash"):
            stats["crash"] += 1
        else:
            toks = res.get("tokens", [])
            stats["n_tokens"] += len(toks)
            if not toks:
                stats["no_tokens"] += 1
            for t in toks:
                stats["meta:" + t["meta_class"]] += 1
                stats["live:" + t.get("derived", {}).get("liveness", "?")] += 1
        if done % 20 == 0 or done == len(todo):
            el = time.time() - t0
            log(f"progress {done}/{len(todo)} ({done / max(el, 1):.2f} coll/s, {el / 60:.1f} min) " +
                " ".join(f"{k}={v}" for k, v in sorted(stats.items())))

    await asyncio.gather(*[worker(r) for r in todo])
    log(f"run finished: {done} collections in {(time.time() - t0) / 60:.1f} min")
    await net.close()


async def cmd_retry(args):
    load_gateways()
    if args.pass3:
        a3 = [x.strip().lower() for x in open(args.pass3) if x.strip()]
        log(f"retry pass 3 start: {len(a3)} candidate collections")
        net = Net()
        await net.start()
        for g in GW_STATE["ipfs_ok"] + GW_STATE["ar_ok"]:
            net.throttle.configure(g, interval=0.5, conc=60)
        sem = asyncio.Semaphore(args.concurrency)
        done = 0

        async def w3(a):
            nonlocal done
            async with sem:
                try:
                    if await retry3_collection(net, a):
                        done += 1
                except Exception:  # noqa: BLE001
                    log(f"retry3 crash {a}: {traceback.format_exc()[-300:]}")
        await asyncio.gather(*[w3(a) for a in a3])
        log(f"retry pass 3 finished: {done} collections re-fetched")
        await net.close()
        return
    addrs = []
    for p in sorted(RAW.iterdir()):
        if p.name.startswith("_") or not has_result(p):
            continue
        rf = p / ("result.json.gz" if (p / "result.json.gz").exists() else "result.json")
        try:
            res = load_result(p)
        except (ValueError, OSError, EOFError):
            continue
        if res.get("crash") or res.get("pass", 1) >= 2:
            continue
        if time.time() - rf.stat().st_mtime < args.min_age:
            continue
        if any(needs_retry_any(t) for t in res.get("tokens", [])):
            addrs.append(p.name)
    log(f"retry start: {len(addrs)} collections with unresolved fetches (min_age={args.min_age}s)")
    net = Net()
    await net.start()
    for g in GW_STATE["ipfs_ok"] + GW_STATE["ar_ok"]:
        net.throttle.configure(g, interval=0.6, conc=60)  # the main run uses <=2.5 req/s per gateway; keep the sum under ~3.7
    sem = asyncio.Semaphore(args.concurrency)
    n = 0

    async def w(a):
        nonlocal n
        async with sem:
            try:
                await retry_collection(net, a, args.min_age)
            except Exception:  # noqa: BLE001
                log(f"retry crash {a}: {traceback.format_exc()[-300:]}")
        n += 1
        if n % 20 == 0:
            log(f"retry progress {n}/{len(addrs)}")

    await asyncio.gather(*[w(a) for a in addrs])
    # collections that never needed a retry are final as-is
    log(f"retry finished: {n} collections")
    await net.close()


def collection_row(res):
    toks = res.get("tokens", [])
    ds = [t.get("derived", {}) for t in toks]
    row = {k: res.get(k) for k in ("address", "name", "standard", "holders_count", "deploy_year", "spam_suspect")}
    def num(v):
        try:
            f = float(v)
            return None if f != f else f
        except (TypeError, ValueError):
            return None
    row["holders_count"] = num(row["holders_count"])
    row["deploy_year"] = num(row["deploy_year"])
    row["spam_suspect"] = str(row["spam_suspect"]).lower() == "true"
    row["sample_stratum"] = res.get("sample_stratum")
    row["n_sampled"] = len(toks)
    row["crash"] = bool(res.get("crash"))

    def mode(vals):
        vals = [v for v in vals if v is not None]
        return Counter(vals).most_common(1)[0][0] if vals else None
    meta_classes = [t["meta_class"] for t in toks]
    row["meta_class"] = mode(meta_classes) if meta_classes else "no-token-found"
    row["meta_classes_all"] = ",".join(sorted(set(meta_classes)))
    row["meta_mixed"] = len(set(meta_classes)) > 1
    row["meta_broken_reasons"] = ",".join(sorted({str(t.get("meta_reason")) for t in toks if t["meta_class"] == "broken"})) or None
    imgc = [d.get("image_class") for d in ds]
    row["media_class"] = mode([c for c in imgc if c]) or ("none" if toks else None)
    row["media_classes_all"] = ",".join(sorted({c for c in imgc if c}))
    row["anim_class"] = mode([d.get("anim_class") for d in ds])
    row["media_class_source"] = mode([d.get("media_class_source") for d in ds])
    row["renderer_hint"] = (res.get("renderer") or {}).get("hint")
    row["renderer_tags"] = ",".join((res.get("renderer") or {}).get("tags", [])) or None
    hosts = sorted({t.get("meta_reg_domain") for t in toks if t.get("meta_reg_domain")})
    mhosts = set()
    for t in toks:
        for m in t.get("media", []) or []:
            if m.get("reg_domain"):
                mhosts.add(m["reg_domain"])
    row["meta_domains"] = ",".join(hosts) or None
    row["media_domains"] = ",".join(sorted(mhosts)) or None
    gws = {t.get("meta_gateway") for t in toks if t.get("meta_gateway")}
    for t in toks:
        for m in t.get("media", []) or []:
            if m.get("gateway") and m["cls"] in ("ipfs", "arweave"):
                gws.add(m["gateway"])
    row["hardcoded_gateways"] = ",".join(sorted(gws)) or None
    refs = sorted({r for d in ds for r in d.get("external_refs", [])})
    row["external_refs"] = json.dumps(refs[:50]) if refs else None
    row["has_external_refs"] = bool(refs)
    row["onchain_candidate"] = bool(ds) and all(d.get("onchain_candidate") for d in ds)
    row["onchain_candidate_clean"] = bool(ds) and all(d.get("onchain_candidate_clean") for d in ds)
    def collapse(key):
        lv = Counter(d.get(key) for d in ds)
        n = len(ds)
        a, dd, g, u = lv["alive"], lv["dead"], lv["degraded"], lv["unknown"]
        if n == 0:
            L = "unknown"
        elif a == n:
            L = "alive"
        elif dd == n:
            L = "dead"
        elif u == n:
            L = "unknown"
        elif g > 0 or (a > 0 and dd > 0):
            L = "degraded"
        elif a == 0 and g == 0 and dd > 0:
            L = "dead" if dd >= u else "unknown"
        else:
            L = "alive" if a >= 2 else "unknown"
        return L, (a, dd, g, u)
    row["liveness"], (a, dd, g, u) = collapse("liveness")
    row["liveness_exact"], _ = collapse("liveness_exact")
    row["n_alive"], row["n_dead"], row["n_degraded"], row["n_unknown"] = a, dd, g, u
    reasons = Counter(d.get("liveness_reason") for d in ds if d.get("liveness") in ("dead", "degraded", "unknown") and d.get("liveness_reason"))
    row["liveness_reasons"] = "; ".join(f"{k} x{v}" for k, v in reasons.most_common(4)) or None
    reasons = Counter(d.get("liveness_exact_reason") for d in ds if d.get("liveness_exact") in ("dead", "degraded", "unknown") and d.get("liveness_exact_reason"))
    row["liveness_exact_reasons"] = "; ".join(f"{k} x{v}" for k, v in reasons.most_common(4)) or None
    row["n_gas_cap_suspected"] = sum(1 for t in toks if t.get("revert_gas_cap_suspected"))
    row["pass"] = res.get("pass", 1)
    row["any_needs_retry"] = any(needs_retry_any(t) for t in toks)
    row["finished_at"] = res.get("finished_at")
    return row


def token_rows(res):
    out = []
    for t in res.get("tokens", []):
        d = t.get("derived", {})
        mt = t.get("meta_target") or {}
        img = next((m for m in (t.get("media") or []) if m["field"] in ("image", "image_data")), None) or {}
        anim = next((m for m in (t.get("media") or []) if m["field"] == "animation_url"), None) or {}
        imt, amt = img.get("target") or {}, anim.get("target") or {}
        rpc_last = (t.get("rpc") or [{}])[-1]
        out.append({
            "address": res["address"], "token_id": t["token_id"], "how_found": t.get("how_found"),
            "called_fn": t.get("called_fn"), "rpc_error": rpc_last.get("error") if not rpc_last.get("ok", True) else None,
            "rpc_revert": any(x.get("revert") for x in (t.get("rpc") or [])),
            "uri_raw": (t.get("uri_raw") or "")[:300], "uri_raw_len": t.get("uri_raw_len"),
            "meta_class": t["meta_class"], "meta_reason": t.get("meta_reason"), "meta_encoding": t.get("meta_encoding"),
            "meta_host": t.get("meta_host"), "meta_reg_domain": t.get("meta_reg_domain"), "meta_gateway": t.get("meta_gateway"),
            "meta_cid": t.get("meta_cid"), "meta_payload_kind": t.get("meta_payload_kind"),
            "meta_verdict": d.get("meta_verdict"), "meta_verdict_reason": d.get("meta_verdict_reason"),
            "meta_status": (mt.get("attempts") or [{}])[-1].get("status") if mt else None,
            "meta_hardcoded_gateway_state": mt.get("hardcoded_gateway_state"),
            "image_class": d.get("image_class"), "image_field": img.get("field"), "image_encoding": img.get("encoding"),
            "image_host": img.get("host"), "image_reg_domain": img.get("reg_domain"), "image_gateway": img.get("gateway"),
            "image_cid": img.get("cid"), "image_verdict": d.get("image_verdict"), "image_reason": imt.get("reason") or img.get("reason"),
            "image_content_type": imt.get("content_type"), "image_size": imt.get("size"), "image_content_length": imt.get("content_length"),
            "image_sha256": imt.get("sha256") or img.get("payload_sha256"),
            "image_hardcoded_gateway_state": imt.get("hardcoded_gateway_state"),
            "anim_class": d.get("anim_class"), "anim_verdict": d.get("anim_verdict"), "anim_reason": amt.get("reason"),
            "anim_host": anim.get("host"), "anim_gateway": anim.get("gateway"),
            "media_class_source": d.get("media_class_source"),
            "external_refs": json.dumps(d.get("external_refs")) if d.get("external_refs") else None,
            "n_external_mentions": d.get("n_external_mentions"),
            "onchain_candidate": d.get("onchain_candidate"), "onchain_candidate_clean": d.get("onchain_candidate_clean"),
            "liveness": d.get("liveness"), "liveness_reason": d.get("liveness_reason"),
            "liveness_exact": d.get("liveness_exact"), "liveness_exact_reason": d.get("liveness_exact_reason"),
            "meta_verdict_exact": d.get("meta_verdict_exact"), "image_verdict_exact": d.get("image_verdict_exact"),
            "revert_gas_cap_suspected": bool(t.get("revert_gas_cap_suspected")),
            "evidence_dir": f"data/raw/census/{res['address']}",
        })
    return out


def cmd_aggregate(args):
    import pandas as pd
    crow, trow = [], []
    for p in sorted(RAW.iterdir()):
        if p.name.startswith("_") or not has_result(p):
            continue
        try:
            res = load_result(p)
        except (ValueError, OSError, EOFError):
            continue
        res["sample_stratum"] = stratum_of(res["address"], res)
        crow.append(collection_row(res))
        trow.extend(token_rows(res))
    OUT.mkdir(parents=True, exist_ok=True)
    cdf, tdf = pd.DataFrame(crow), pd.DataFrame(trow)
    for df, nm in ((cdf, "census_collections.parquet"), (tdf, "census_tokens.parquet")):  # atomic: tmp + rename
        tmp = OUT / (nm + ".tmp")
        df.to_parquet(tmp, index=False)
        os.replace(tmp, OUT / nm)
    log(f"aggregate: {len(cdf)} collections, {len(tdf)} tokens")
    if len(cdf):
        print(cdf["meta_class"].value_counts().to_string())
        print(cdf["liveness"].value_counts().to_string())


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gateways")
    r = sub.add_parser("run")
    r.add_argument("--list", choices=["seed", "universe"], default="seed")
    r.add_argument("--seedfile")
    r.add_argument("--spam", choices=["skip", "only", "all"], default="all")
    r.add_argument("--limit", type=int)
    r.add_argument("--concurrency", type=int, default=200)
    r.add_argument("--force", action="store_true")
    r.add_argument("--redo-crashed", action="store_true", help="also re-run collections whose stored result is a crash/timeout stub")
    r.add_argument("--addresses", help="file with one address per line: restrict the run to these")
    rt = sub.add_parser("retry")
    rt.add_argument("--min-age", type=int, default=600)
    rt.add_argument("--pass3", help="file of addresses: third pass over targets still unknown after pass 2")
    rt.add_argument("--concurrency", type=int, default=60)
    sub.add_parser("aggregate")
    args = ap.parse_args()
    if args.cmd == "gateways":
        asyncio.run(cmd_gateways(args))
    elif args.cmd == "run":
        asyncio.run(cmd_run(args))
    elif args.cmd == "retry":
        asyncio.run(cmd_retry(args))
    elif args.cmd == "aggregate":
        cmd_aggregate(args)


if __name__ == "__main__":
    main()
