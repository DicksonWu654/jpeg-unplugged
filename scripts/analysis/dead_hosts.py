"""Stage 5: data/analysis/dead_hosts.csv (feed for the hosts dead-domains study area)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa

POP = 49494


def agg(he, scope, n_sample):
    # collection x host x kind state: dead if >=1 dead target and no alive target on that host
    g = he.groupby(["a", "host", "kind"]).agg(
        n_dead=("verdict", lambda s: int((s == "dead").sum())), n_alive=("verdict", lambda s: int((s == "alive").sum())),
        n_unknown=("verdict", lambda s: int((s == "unknown").sum())), reason=("reason_cat", lambda s: pick_reason(list(s.dropna()))),
        reg=("reg_domain", "first"), gwstates=("gw_state", lambda s: ",".join(sorted({x for x in s.dropna()}))),
        holders=("holders", "first"), name=("name", "first")).reset_index()
    g["state"] = "unknown"
    g.loc[g.n_alive > 0, "state"] = "alive"
    g.loc[(g.n_alive == 0) & (g.n_dead > 0), "state"] = "dead"
    # hardcoded gateways: dead if census canary says the gateway itself is dead
    gwdead = g.gwstates.str.contains("dead:") & g.kind.ne("http-origin")
    g.loc[gwdead, "state"] = "gateway-dead"
    g.loc[g.gwstates.str.contains("bot-walled") & g.kind.ne("http-origin") & ~gwdead & (g.state == "unknown"), "state"] = "bot-walled"
    rows = []
    for (host, kind), x in g.groupby(["host", "kind"]):
        d = x[x.state.isin(["dead", "gateway-dead"])]
        rows.append({
            "scope": scope, "host": host, "reg_domain": next((r for r in x.reg if isinstance(r, str)), None), "kind": kind,
            "collections_using": len(x), "collections_dead": len(d), "collections_alive": int((x.state == "alive").sum()),
            "collections_unknown": int(x.state.isin(["unknown", "bot-walled"]).sum()),
            "holders_affected": int(d.holders.sum()), "holders_using": int(x.holders.sum()),
            "main_reason": ("hardcoded-gateway-dead (%s)" % ",".join(sorted({s_ for v in d.gwstates for s_ in v.split(",") if s_.startswith("dead:")}))) if (d.state == "gateway-dead").any() else pick_reason(list(d.reason.dropna())),
            "gateway_states": ",".join(sorted({s_ for v in x.gwstates for s_ in v.split(",") if s_})),
            "est_universe_collections_dead": round(len(d) * POP / n_sample) if scope == "random" else None,
            "example_collections": "; ".join("%s (%s)" % (n, a) for n, a in zip(d.name.head(3), d.a.head(3))),
        })
    return pd.DataFrame(rows)


def main():
    he = pd.read_parquet(OUT / "host_events.parquet")
    f = pd.read_parquet(OUT / "collections_enriched.parquet")
    he = he[he.stratum.isin(["random", "top"])]
    r = agg(he[he.stratum == "random"], "random-stratum", 3000)
    a = agg(he, "all-census(random+top, not representative)", int(he.a.nunique()))
    out = pd.concat([r, a])
    out = out[out.collections_dead > 0].sort_values(["scope", "holders_affected"], ascending=[False, False])
    out.to_csv(OUT / "dead_hosts.csv", index=False)
    print("dead_hosts.csv", len(out), out.groupby("scope").size().to_dict())
    return out


if __name__ == "__main__":
    main()
