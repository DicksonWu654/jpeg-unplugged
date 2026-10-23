"""Step 2: contract creation info (creator, tx hash, block, unix timestamp, factory, creation bytecode) for every
universe address, in batches of 5 (Etherscan's max; Blockscout silently truncates larger batches to ~9 results).

Providers (same response schema):
  blockscout (default)  https://eth.blockscout.com/api?module=contract&action=getcontractcreation  -> raw source
                        blockscout-creation, key w1_creation_<sha1(batch)>   (~2.5 req/s, own rate limit)
  etherscan             Etherscan v2 chainid=1 -> raw source etherscan, same key scheme (the shared free key is capped at
                        3/s across all workstreams, so it was only ~0.5/s for us in practice; used for the first ~2k
                        batches and for addresses Blockscout did not return: --missing).
Raw files are saved by rawfetch; creationBytecode blobs (~25 KB/contract) are then truncated to head + len + sha256 to save
disk (a MANIFEST line records the original sha256/size). The first ~570 MB of Etherscan batches were kept verbatim.
Resumable via data/universe/creation_batches.jsonl. Output: data/universe/creation.jsonl (rebuilt from all raw batches)."""
import glob, hashlib, json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from common import UNI, ROOT, rf, Limiter, fetch_json, etherscan_key, load_token_rows
from creation_order import URLISH

PROVIDER = "blockscout" if "--blockscout" in sys.argv else "etherscan"  # blockscout /api quota is ~10 calls per week: do not use
lim = Limiter(2.6)
SRC = "blockscout-creation" if PROVIDER == "blockscout" else "etherscan"


def ok(j):
    if not isinstance(j, dict):
        return False
    if isinstance(j.get("result"), list):
        return True
    return "No data found" in str(j.get("message", "")) + str(j.get("result", ""))


def trim_raw(source, key):
    rel = rf.raw_path(source, key)
    p = ROOT / rel
    b = p.read_bytes()
    j = json.loads(b)
    if isinstance(j.get("result"), list):
        for r in j["result"]:
            bc = r.get("creationBytecode")
            if bc and len(bc) > 400:
                r["creationBytecode"] = (bc[:160] + f"...[truncated len={(len(bc)-2)//2} sha256="
                                         + hashlib.sha256(bc.encode()).hexdigest() + "]")
    nb = json.dumps(j).encode()
    p.write_bytes(nb)
    with open(rf.MANIFEST, "a") as f:
        f.write(json.dumps({"path": rel, "sha256": hashlib.sha256(nb).hexdigest(), "trimmed": "creationBytecode",
                            "original_sha256": hashlib.sha256(b).hexdigest(), "original_bytes": len(b),
                            "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}) + "\n")


def do_batch(addrs):
    h = hashlib.sha1(",".join(sorted(addrs)).encode()).hexdigest()[:14]
    key = f"w1_creation_{h}"
    if PROVIDER == "blockscout":
        url = ("https://eth.blockscout.com/api?module=contract&action=getcontractcreation"
               f"&contractaddresses={','.join(addrs)}")
    else:
        url = ("https://api.etherscan.io/v2/api?chainid=1&module=contract&action=getcontractcreation"
               f"&contractaddresses={','.join(addrs)}&apikey={etherscan_key()}")
    try:
        j, cached = fetch_json(url, SRC, key, lim, ok, max_attempts=12 if PROVIDER == "blockscout" else 25)
    except RuntimeError as e:
        print("GIVE UP batch", key, e, flush=True)
        return addrs, None
    if not cached:
        trim_raw(SRC, key)
    with open(UNI / "creation_batches.jsonl", "a") as f:
        f.write(json.dumps({"key": key, "provider": PROVIDER, "addrs": addrs}) + "\n")
    return addrs, j


def assemble_creation():
    """Parse all raw creation batches (both providers) into data/universe/creation.jsonl; first provider row wins."""
    seen, n = set(), 0
    files = sorted(glob.glob(str(ROOT / "data/raw/etherscan/w1_creation_*.json")) +
                   glob.glob(str(ROOT / "data/raw/blockscout-creation/w1_creation_*.json")))
    with open(UNI / "creation.jsonl", "w") as f:
        for p in files:
            j = json.load(open(p))
            if not isinstance(j.get("result"), list):
                continue
            for r in j["result"]:
                a = r["contractAddress"].lower()
                if a in seen or not r.get("timestamp"):
                    continue
                seen.add(a)
                r = dict(r)
                bc = r.pop("creationBytecode", "") or ""
                m = re.search(r"\[truncated len=(\d+) ", bc)
                r["creationBytecodeLen"] = int(m.group(1)) if m else (len(bc) - 2) // 2
                r["creationBytecodeHead"] = bc[:80]
                r["raw"] = os.path.relpath(p, ROOT)
                r["provider"] = "blockscout" if "blockscout-creation" in p else "etherscan"
                f.write(json.dumps(r) + "\n")
                n += 1
    return n


def main():
    missing_mode = "--missing" in sys.argv
    tried = set()  # addresses already requested from THIS provider
    bf = UNI / "creation_batches.jsonl"
    if bf.exists():
        for line in bf.read_text().splitlines():
            b = json.loads(line)
            if b.get("provider", "etherscan") == PROVIDER or not missing_mode:
                tried.update(b["addrs"])
    have = set()
    if missing_mode:
        assemble_creation()
        have = {json.loads(l)["contractAddress"].lower() for l in open(UNI / "creation.jsonl")}
    rows = load_token_rows()
    rows.sort(key=lambda r: (bool(URLISH.search((r["name"] or "") + " " + (r["symbol"] or ""))), -int(r["holders_count"])))
    todo = [r["address_hash"].lower() for r in rows]
    todo = [a for a in todo if a not in have and a not in tried]
    chunks = [todo[i:i + 5] for i in range(0, len(todo), 5)]
    print(time.strftime("%H:%M:%S"), PROVIDER, "todo addrs", len(todo), "batches", len(chunks), flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(5) as ex:
        for k, _ in enumerate(ex.map(do_batch, chunks)):
            if k % 100 == 0:
                print(time.strftime("%H:%M:%S"), f"batches {k}/{len(chunks)} elapsed {int(time.time()-t0)}s", flush=True)
    print("assembled rows", assemble_creation(), "elapsed", int(time.time() - t0), "s", flush=True)


if __name__ == "__main__":
    main()
