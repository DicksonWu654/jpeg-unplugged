"""Stage 0: extract every distinct http(s) host from the census census (metadata URI, image/animation URLs, external refs)
and the collections that depend on it.  Reads copies of the census parquet (census rewrites them) and per-collection
result.json.gz under data/raw/census/<address>/.  Writes data/hosts/host_deps.parquet (host x collection) and
data/hosts/host_urls.json (sample URLs per host)."""
import gzip, json, shutil, sys, time, collections
from urllib.parse import urlsplit
import duckdb
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import *

CENSUS = ROOT / "data" / "census"
TMP = SCRATCH / "w8"
TMP.mkdir(parents=True, exist_ok=True)


def snap(name):
    for i in range(8):
        try:
            shutil.copy(CENSUS / f"{name}.parquet", TMP / f"{name}.parquet")
            duckdb.sql(f"select count(*) from '{TMP / (name + '.parquet')}'").fetchall()
            return TMP / f"{name}.parquet"
        except Exception as e:  # noqa
            print("retry", name, e)
            time.sleep(3)
    raise SystemExit("cannot snapshot " + name)


def split(url):
    try:
        u = urlsplit(url.strip())
    except ValueError:
        return None
    if u.scheme.lower() not in ("http", "https") or not u.hostname:
        return None
    h = u.hostname.lower().rstrip(".")
    return u.scheme.lower(), h, u.port


def walk_targets(obj, out):
    """collect (role, uri) from any 'target' dicts and external_refs lists."""
    if isinstance(obj, dict):
        if "uri" in obj and "role" in obj and isinstance(obj.get("uri"), str):
            out.append((obj["role"], obj["uri"]))
        for k, v in obj.items():
            if k == "external_refs" and isinstance(v, list):
                for u in v:
                    if isinstance(u, str):
                        out.append(("external_ref", u))
            else:
                walk_targets(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk_targets(v, out)


def main():
    cp = snap("census_collections")
    snap("census_tokens")
    cols = duckdb.sql(f"select address,name,holders_count,deploy_year,sample_stratum,spam_suspect,standard,hardcoded_gateways,external_refs "
                      f"from '{cp}'").df()
    print("collections", len(cols), cols.sample_stratum.value_counts().to_dict())
    rows = []          # host, address, role, scheme, port, uri
    missing = 0
    for r in cols.itertuples():
        p = CENSUS.parent / "raw" / "census" / r.address / "result.json.gz"
        res = None
        for i in range(3 if p.exists() else 0):
            try:
                res = json.load(gzip.open(p))
                break
            except Exception:
                time.sleep(1)
        if res is None:
            missing += 1
            continue
        tg = []
        walk_targets(res.get("tokens", []), tg)
        # metadata uri_raw fallback
        for t in res.get("tokens", []):
            if t.get("uri_raw"):
                tg.append(("metadata", t["uri_raw"]))
        # collection-level external refs from the parquet
        if r.external_refs:
            try:
                for u in json.loads(r.external_refs):
                    tg.append(("external_ref", u))
            except Exception:
                pass
        seen = set()
        for role, uri in tg:
            s = split(uri)
            if not s:
                continue
            key = (s[1], role, uri)
            if key in seen:
                continue
            seen.add(key)
            rows.append((s[1], r.address, role, s[0], s[2], uri))
    print("missing result files", missing, "url rows", len(rows))
    import pandas as pd
    df = pd.DataFrame(rows, columns=["host", "address", "role", "scheme", "port", "uri"])
    df = df.merge(cols[["address", "name", "holders_count", "deploy_year", "sample_stratum", "spam_suspect", "standard"]], on="address")
    df.to_parquet(HOSTS_DIR / "host_deps.parquet", index=False)
    # hardcoded gateways (collection-level list) as extra dependency rows (role=hardcoded_gateway) in case no URL row exists
    print("distinct hosts", df.host.nunique(), "collections with >=1 host", df.address.nunique())
    print(df.groupby("role").host.nunique().to_dict())


if __name__ == "__main__":
    main()
