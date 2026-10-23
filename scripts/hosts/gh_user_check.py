"""For [withheld-host] hosts with the Pages-404 fingerprint: does the GitHub user/org <name> exist? (GET https://github.com/<name>, status only.)
404 => the name is unregistered (username claimable); 200 => owner exists (only they can restore).  Read-only."""
import json, sys, time, urllib.request, urllib.error, pathlib
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import *
d = pd.read_parquet(HOSTS_DIR / "hosts_full.parquet")
out = {}
for h in d[(d.platform == "github-pages") & (d.verdict == "dangling-cloud-claimable")].host:
    name = h.split(".github.io")[0].split(".")[-1]
    try:
        r = urllib.request.urlopen(urllib.request.Request(f"https://github.com/{name}", headers={"User-Agent": "nft-unplugged-research/0.1"}), timeout=15)
        s = r.status
    except urllib.error.HTTPError as e:
        s = e.code
    except Exception as e:  # noqa
        s = str(e)[:80]
    out[h] = {"user": name, "github_status": s, "t": now()}
    time.sleep(1)
(RAW / "_domains" / "github_user_check.json").write_text(json.dumps(out, indent=1))
print(out)
