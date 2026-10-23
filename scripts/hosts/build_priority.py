"""Stage 0b: per-host dependants + priority table (data/hosts/host_priority.parquet): holders affected = sum of holders_count over
DISTINCT dependent collections (an upper bound on distinct holders: wallets can hold several collections)."""
import sys, pathlib
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import *

deps = pd.read_parquet(HOSTS_DIR / "host_deps.parquet")
col = deps.drop_duplicates(["host", "address"])
g = col.groupby("host").agg(n_collections=("address", "nunique"), holders=("holders_count", "sum"),
                            min_deploy_year=("deploy_year", "min"), strata=("sample_stratum", lambda s: ",".join(sorted(set(s)))))
roles = deps.groupby("host").role.agg(lambda s: ",".join(sorted(set(s))))
g["roles"] = roles
top = (col.sort_values("holders_count", ascending=False).groupby("host").head(3)
       .groupby("host").apply(lambda d: "; ".join(f"{(n or '?')} ({a[:10]}.., {int(h)} holders)" for n, a, h in zip(d.name, d.address, d.holders_count)), include_groups=False))
g["top_collections"] = top
def pick(d):
    out = []
    for role in ("metadata", "image", "animation_url", "animation", "external_ref"):
        x = d[d.role == role].uri
        if len(x):
            out.append(x.iloc[0])
    for u in d.uri:
        if u not in out:
            out.append(u)
    return out[:3]
urls = deps.sort_values("holders_count", ascending=False).groupby("host").apply(pick, include_groups=False)
g["urls"] = urls
g = g.reset_index().sort_values(["holders", "n_collections"], ascending=False).reset_index(drop=True)
g["priority_rank"] = g.index + 1
g.to_parquet(HOSTS_DIR / "host_priority.parquet", index=False)
print(len(g), "hosts;", (~g.host.map(is_ip)).sum(), "non-IP")
print(g.head(15)[["host", "n_collections", "holders"]])
