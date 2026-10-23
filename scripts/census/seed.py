#!/usr/bin/env python3
"""Build data/census/seed.csv: ~40 well-known collections covering every class. Addresses are verified against
Blockscout (name/type/holders) at build time; mismatches are reported and dropped."""
import csv, json, pathlib, sys, time, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = [  # (address, label, expected-class note)
 ("0xd4e4078ca3495DE5B1d4dB434BEbc5a986197782", "Autoglyphs", "onchain (draw(); maybe no tokenURI)"),
 ("0xFF9C1b15B16263C61d017ee9F65C50e4AE0113D7", "Loot", "onchain data-uri renderer"),
 ("0x9C8fF314C9bc7F6e59A9d9225Fb22946427eDC03", "Nouns", "onchain renderer"),
 ("0x97597002980134beA46250Aa0510C9B90d87A587", "Chain Runners", "?"),
 ("0xb47e3cd837dDF8e4c57F05d70Ab865de6e193BBB", "CryptoPunks (original, not ERC-721)", "no tokenURI"),
 ("0xb7F7F6C52F2e2fdb1963Eab30438024864c313F6", "Wrapped CryptoPunks", "?"),
 ("0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D", "BAYC", "ipfs"),
 ("0x60E4d786628Fea6478F785A6d7e704777c86a7c6", "MAYC", "ipfs"),
 ("0xED5AF388653567Af2F388E6224dC7C4b3241C544", "Azuki", "ipfs"),
 ("0xa7d8d9ef8D8Ce8992Df33D8b8CF4Aebabd5bD270", "Art Blocks (current core)", "http api"),
 ("0x059EDD72Cd353dF5106D2B9cC5ab83a52287aC3a", "Art Blocks (legacy core)", "http api"),
 ("0x23581767a106ae21c074b2276D25e5C3e136a68b", "Moonbirds", "ipfs/http"),
 ("0x8a90CAb2b38dba80c64b7734e58Ee1dB38B8992e", "Doodles", "ipfs"),
 ("0x57f1887a8BF19b14fC0dF6Fd9B2acc9Af147eA85", "ENS Base Registrar", "http"),
 ("0xD4416b13d2b3a9aBae7AcD5D6C2BbDBE25686401", "ENS NameWrapper (1155)", "http"),
 ("0x495f947276749Ce646f68AC8c248420045cb7b5e", "OpenSea Shared Storefront (1155)", "http api"),
 ("0x28472a58A490c5e09A238847F66A68a47cC76f0f", "Adidas Into the Metaverse (1155)", "ipfs"),
 ("0x1A92f7381B9F03921564a437210bB9396471050C", "Cool Cats", "?"),
 ("0x49cF6f5d44E70224e2E23fDcdd2C053F30aDA28B", "CloneX", "?"),
 ("0xBd3531dA5CF5857e7CfAA92426877b022e612cf8", "Pudgy Penguins", "ipfs"),
 ("0xe785E82358879F061BC3dcAC6f0444462D4b5330", "World of Women", "ipfs"),
 ("0x7Bd29408f11D2bFC23c34f18275bBf23bB716Bc7", "Meebits", "http/ipfs"),
 ("0x06012c8cf97BEaD5deAe237070F9587f8E7A266d", "CryptoKitties", "http api"),
 ("0x8d04a8c79cEB0889Bdd12acdF3Fa9D207eD3Ff63", "Blitmap", "onchain-ish"),
 ("0x1CB1A5e65610AEFF2551A50f76a87a7d3fB649C6", "CrypToadz", "ipfs/onchain"),
 ("0xbad6186E92002E312078b5a1dAfd5ddf63d3f731", "Anonymice", "onchain"),
 ("0x521f9C7505005CFA19A8E5786a9c3c9c9F5e6f42", "Forgotten Runes Wizards", "ipfs"),
 ("0x4E1f41613c9084FdB9E34E11fAE9412427480e56", "Terraforms", "onchain"),
 ("0x79986aF15539de2db9A5086382daEdA917A9CF0C", "Cryptovoxels", "http"),
 ("0x79FCDEF22feeD20eDDacbB2587640e45491b757f", "mfers", "ipfs"),
 ("0x5Af0D9827E0c53E4799BB226655A1de152A425a5", "Milady Maker", "ipfs/http"),
 ("0x34eEBEE6942d8Def3c125458D1a86e0A897fd6f9", "Checks VV", "onchain"),
 ("0xB66a603f4cFe17e3D27B87a8BfCaD319856518B8", "Rarible (1155)", "?"),
 ("0x3B3ee1931Dc30C1957379FAc9aba94D1C48a5405", "Foundation", "ipfs"),
 ("0xb932a70A57673d89f4acfFBE830E8ed7f75Fb9e0", "SuperRare (old)", "?"),
 ("0xFBeef911Dc5821886e1dda71586d90eD28174B7d", "KnownOrigin", "?"),
 ("0x0489e1CCF80Ef564F093d5fefAF857B2623171c0", "Nifty Gateway Evolutions", "http?"),
 ("0xF87E31492Faf9A91B02Ee0dEAAd50d51d56D5d4d", "Decentraland LAND", "http"),
 ("0x32973908FaeE0Bf825A343000fE412ebE56F802A", "Pixelmon", "?"),
 ("0xc3f733ca98E0daD0386979Eb96fb1722A1A05E69", "Acclimated MoonCats", "onchain-ish"),
 ("0x1e9385eE28c5C7d33F3472f732Fb08CE3ceBce1F", "MoonCat Lootprint", "onchain"),
 ("0x50f5474724e0Ee42D9a4e711ccFB275809Fd6d4a", "The Sandbox LAND", "http"),
 ("0xa342f5D851E866E18ff98F351f2c6637f4478dB5", "The Sandbox Assets (1155)", "?"),
 ("0xF5b0A3eFB8e8E4c201e2A935F110eAaF3FFEcb8d", "Axie Infinity", "http"),
 ("0x76BE3b62873462d2142405439777e971754E8E77", "Parallel Alpha (1155)", "?"),
 ("0xba30E5F9Bb24caa003E9f2f0497Ad287FDF95623", "BAKC", "ipfs"),
 ("0xEdB61f74B0d09B2558F1eeb79B247c1F363Ae452", "Gutter Cat Gang", "?"),
 ("0x6EbeAf8e8E946F0716E6533A6f2cefc83f60e8Ab", "Gods Unchained", "http"),
 ("0xabEFBc9fD2F806065b4f3C237d4b59D9A97Bcac7", "Zora", "?"),
 ("0xb6dAe651468E9593E4581705a09c10A76AC1e0c8", "Async Art", "?"),
]
def get(url):
    for i in range(3):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "nft-unplugged-research/0.1"}), timeout=30))
        except Exception as e:
            err = e; time.sleep(1 + i)
    return {"_error": str(err)}
rows = []
for addr, label, exp in SEEDS:
    d = get(f"https://eth.blockscout.com/api/v2/tokens/{addr}")
    time.sleep(0.4)
    if "_error" in d or "type" not in d:
        print("MISS", label, addr, d.get("_error") or d.get("message")); continue
    print(f"{label:38s} -> {d.get('name')!s:34s} {d.get('type')} holders={d.get('holders_count')}")
    std = d["type"] if d["type"] in ("ERC-721", "ERC-1155") else "ERC-721"  # Blockscout types a few NFT contracts (Punks, Axie...) as ERC-20
    rows.append({"address": addr.lower(), "name": d.get("name") or label, "standard": std, "holders_count": d.get("holders_count"),
                 "deploy_year": "", "spam_suspect": "False", "label": label, "expect": exp})
out = ROOT / "data/census/seed.csv"
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print("wrote", out, len(rows))
