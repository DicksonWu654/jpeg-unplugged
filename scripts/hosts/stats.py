"""Aggregate counts for docs/methods/hosts.md (prints markdown).  Public-safe: no claimable hostnames."""
import sys, pathlib
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import *
d = pd.read_parquet(HOSTS_DIR / "hosts_full.parquet")
deps = pd.read_parquet(HOSTS_DIR / "host_deps.parquet")
tot_cols = deps.address.nunique()
tot_hold = deps.drop_duplicates("address").holders_count.sum()
print(f"hosts total {len(d)}; collections with >=1 http(s) host {tot_cols}; sum holders (upper bound) {int(tot_hold)}")
probed = d[d.http_probed | d.dns_resolves.eq(False) | d.dns_a_rcode.eq("NXDOMAIN")]
print("\n## verdicts (all hosts)")
g = d.groupby("verdict").agg(hosts=("host", "count"), collections=("n_collections", "sum"), holders=("holders_affected", "sum")).sort_values("hosts", ascending=False)
print(g.to_markdown())
# distinct collections / holders per verdict
print("\n## distinct collections and holders per verdict (union, holders = sum of holders_count over distinct collections)")
vm = d.set_index("host").verdict
x = deps.copy(); x["verdict"] = x.host.map(vm)
rows = []
for v, grp in x.groupby("verdict"):
    c = grp.drop_duplicates("address")
    rows.append((v, c.address.nunique(), int(c.holders_count.sum())))
print(pd.DataFrame(rows, columns=["verdict", "distinct_collections", "holders_upper_bound"]).sort_values("distinct_collections", ascending=False).to_markdown(index=False))
print("\n## by stratum (collections with >=1 host in verdict class)")
risky = ["dangling-cloud-claimable", "domain-likely-available", "rereg-after-deploy"]
dead = ["dead-dns", "dead-http", "parked-or-for-sale"] + risky
for name, vs in (("any risky (claimable/available/rereg)", risky), ("any dead/parked/risky", dead)):
    y = x[x.verdict.isin(vs)].drop_duplicates("address")
    for s in ("random", "top"):
        base = deps[deps.sample_stratum == s].address.nunique()
        print(f"- {name}, stratum {s}: {y[y.sample_stratum==s].address.nunique()} / {base} collections with a host")
print("\n## available evidence"); print(d.available_evidence.value_counts(dropna=False).to_string() if "available_evidence" in d else "")
print("\n## cloud platform x verdict (claimable)")
print(d[d.verdict == "dangling-cloud-claimable"].groupby("platform").agg(hosts=("host", "count"), holders=("holders_affected", "sum")).to_markdown())
print("\n## rdap coverage"); print(d.rdap_outcome.value_counts(dropna=False).to_string())
print("\nrereg flag (any verdict):", int(d.rereg_after_deploy_flag.fillna(False).sum()))
print("\n## NXDOMAIN hosts:", int((d.dns_a_rcode == "NXDOMAIN").sum()), " SERVFAIL:", int((d.dns_a_rcode == "SERVFAIL").sum()))
print("\n## unprobed (beyond HTTP cutoff or ip-literal):", int((d.verdict == "unknown").sum()))
print("\n## top dead/parked (public examples, non-redacted ones only)")
print(d[d.verdict.isin(["dead-dns", "dead-http", "parked-or-for-sale"])].head(12)[["host", "holders_affected", "n_collections", "verdict", "verdict_reason"]].to_markdown(index=False))
