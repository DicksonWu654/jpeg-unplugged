"""Step 4: join token rows + creation info (+ optional Blockscout address enrichment) -> collections.csv/parquet.
Also writes READY_PARTIAL (>=1500 non-spam rows with deploy_year) and READY (complete: enumeration finished and every
row has creation info or an explicit creation_status). Usage: assemble.py [--final]"""
import json, sys, datetime
import pandas as pd
from common import UNI, load_token_rows
from creation import assemble_creation
from flags import spam_flags

PROXY_PREFIXES = ("0x363d3d373d3d3d363d73", "0x3d602d80600a3d3981f3", "0x602d3d8160093d39f3", "0x36600080376020",
                  "0x3d3d3d3d363d3d37363d73")  # EIP-1167 style minimal-proxy (clone) creation/runtime heads


def main():
    finished = (UNI / "tokens_raw_rows.jsonl").exists()
    tokens = load_token_rows()
    assemble_creation()
    cre = {}
    for line in open(UNI / "creation.jsonl"):
        r = json.loads(line)
        cre[r["contractAddress"].lower()] = r
    adr = {}
    if (UNI / "addresses.jsonl").exists():
        for line in open(UNI / "addresses.jsonl"):
            r = json.loads(line)
            adr[r["hash"].lower()] = r
    rows = []
    for t in tokens:
        a = t["address_hash"].lower()
        c, ad = cre.get(a), adr.get(a)
        head = (c or {}).get("creationBytecodeHead", "")
        ts = int(c["timestamp"]) if c and c.get("timestamp") else None
        rows.append(dict(
            address=t["address_hash"], standard=t["type"], name=t["name"], symbol=t["symbol"],
            holders_count=int(t["holders_count"]), total_supply=t["total_supply"],
            reputation=t.get("reputation"), icon_url=t.get("icon_url"), exchange_rate=t.get("exchange_rate"),
            circulating_market_cap=t.get("circulating_market_cap"), volume_24h=t.get("volume_24h"),
            creator=c["contractCreator"] if c else None, creation_tx_hash=c["txHash"] if c else None,
            deploy_block=int(c["blockNumber"]) if c else None, deploy_timestamp=ts,
            deploy_time_utc=datetime.datetime.fromtimestamp(ts, datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if ts else None,
            deploy_year=datetime.datetime.fromtimestamp(ts, datetime.UTC).year if ts else None,
            contract_factory=(c.get("contractFactory") or None) if c else None,
            creation_bytecode_len=c["creationBytecodeLen"] if c else None,
            is_minimal_proxy_clone=head.startswith(PROXY_PREFIXES) if c else None,
            creation_raw=c["raw"] if c else None,
            is_scam=ad["is_scam"] if ad else None, is_verified=ad["is_verified"] if ad else None,
            proxy_type=ad["proxy_type"] if ad else None,
            implementations=";".join(i.get("address_hash", "") for i in (ad["implementations"] or [])) if ad else None,
            is_proxy=bool(ad and (ad["proxy_type"] or ad["implementations"])) if ad else None,
        ))
    spam_flags(rows)
    df = pd.DataFrame(rows).sort_values(["holders_count", "address"], ascending=[False, True]).reset_index(drop=True)
    df["holder_bucket"] = pd.cut(df.holders_count, [99, 999, 9999, 10**12], labels=["100-999", "1k-9.9k", "10k+"])
    df["holder_bucket"] = df["holder_bucket"].astype(str)
    df.to_csv(UNI / "collections.csv", index=False)
    df.to_parquet(UNI / "collections.parquet", index=False)
    ok = df[(~df.spam_suspect) & df.deploy_year.notna()]
    print(f"rows={len(df)} with_creation={df.deploy_year.notna().sum()} nonspam_with_year={len(ok)} finished_enum={finished}")
    if len(ok) >= 1500:
        (UNI / "READY_PARTIAL").touch()
    if finished and df.deploy_year.notna().all() or ("--final" in sys.argv and finished):
        (UNI / "READY").touch()
        print("READY written; missing creation:", df.deploy_year.isna().sum())


if __name__ == "__main__":
    main()
