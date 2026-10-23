"""Print the numbers used in docs/methods/universe.md from data/universe/collections.parquet."""
import pandas as pd
from common import UNI
df = pd.read_parquet(UNI / "collections.parquet")
ns = df[~df.spam_suspect]
def tab(d, by):
    return d.groupby(by, dropna=False).size().rename("n")
print("rows", len(df), "| with deploy year", df.deploy_year.notna().sum(), "| non-spam", len(ns), "| non-spam & non-infra", len(ns[~ns.is_ens_or_infra]))
print("\nby standard (all / non-spam):")
print(pd.concat([tab(df, "standard"), tab(ns, "standard").rename("nonspam")], axis=1))
print("\nby holder bucket x standard (all / non-spam):")
print(pd.concat([tab(df, ["holder_bucket", "standard"]), tab(ns, ["holder_bucket", "standard"]).rename("nonspam")], axis=1))
print("\nby deploy year x standard (all):")
print(pd.crosstab(df.deploy_year, df.standard, dropna=False, margins=True))
print("\nby deploy year (non-spam, non-infra):")
x = ns[~ns.is_ens_or_infra]
print(pd.crosstab(x.deploy_year, x.standard, margins=True))
print("\nspam_suspect by standard:", df.groupby("standard").spam_suspect.agg(["sum", "mean"]).to_dict("index"))
print("\nspam reasons:")
print(df.spam_reasons.str.split(";").explode().str.replace(r"\d+", "N", regex=True).value_counts())
print("\ninfra:", df.is_ens_or_infra.sum()); print(df[df.is_ens_or_infra].infra_reason.value_counts())
print("\nfactory-created:", df.contract_factory.notna().sum(), "minimal proxy clones:", df.is_minimal_proxy_clone.sum())
print("\nreputation:", df.reputation.value_counts().to_dict(), "| with icon_url:", df.icon_url.notna().sum())
print("\nis_scam/proxy enrichment coverage:", df.is_scam.notna().sum(), "is_proxy true:", (df.is_proxy == True).sum(), "is_scam true:", (df.is_scam == True).sum())
print("\nholders sum by bucket:", df.groupby("holder_bucket").holders_count.sum().to_dict())
print("missing creation:", df.deploy_year.isna().sum(), "| total_supply null:", df.total_supply.isna().groupby(df.standard).sum().to_dict())
print(df.head(25)[["address", "name", "standard", "holders_count", "deploy_year", "spam_suspect", "is_ens_or_infra"]].to_string())
