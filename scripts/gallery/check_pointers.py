"""For items whose tokenURI/animation_url/image points at an HTTP(S) URL although the art is on chain, record whether that pointer answers today.
Output: data/gallery/<slug>/offchain_pointer.json  (url, status, error, content-type, bytes, sha256 of first 64 KB, retrieved_at). Unknown != dead: errors are stored as such."""
import json, hashlib, time, urllib.request, urllib.error, socket
import chain
UA = {"User-Agent": "nft-unplugged-research/0.1"}
T = [  # slug, url
 ("chain-runners", "https://api.chainrunners.xyz/tokens/metadata/1?dna=1030810899823733879"),
 ("blitmap", "https://api.blitmap.com/v1/metadata/1"),
 ("avastars", "https://avastars.io/metadata/1"),
 ("chainfaces", "https://chainfacesrinkeby.azurewebsites.net/api/HttpTrigger?id=1"),
 ("terraforms", "https://tokens.mathcastles.xyz/terraform"),
]
# Art Blocks core tokenURI (HTTP API) for three representative tokens
for pid, core in ((0, "0x059EDD72Cd353dF5106D2B9cC5ab83a52287aC3a"), (78, "0xa7d8d9ef8D8Ce8992Df33D8b8CF4Aebabd5bD270"), (457, "0x99a9B7c1116f9ceEB1652de04d5969CcE509B069")):
    try:
        tu = chain.call(core, "tokenURI(uint256)", [pid * 1000000], ["string"], f"ab-{pid}", "tokenURI")
    except Exception: tu = None
    if tu: T.append((f"ab-{pid}", tu))
for slug, u in T:
    rec = {"url": u, "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    for attempt in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25) as r:
                b = r.read(65536); rec.update(status=r.status, content_type=r.headers.get("content-type"), head_bytes=len(b), sha256_head=hashlib.sha256(b).hexdigest(), head=b[:300].decode("utf-8", "replace")); rec.pop("error", None)
            break
        except urllib.error.HTTPError as e:
            rec.update(status=e.code, error=f"HTTP {e.code}"); break
        except Exception as e:
            rec.update(status=None, error=f"{type(e).__name__}: {str(e)[:120]}"); time.sleep(3)
    (chain.GAL / slug / "offchain_pointer.json").write_text(json.dumps(rec, indent=1))
    print(slug, rec.get("status"), rec.get("error"), (rec.get("head") or "")[:80].replace("\n", " "))
    time.sleep(0.5)
