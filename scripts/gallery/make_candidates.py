"""Write data/gallery/candidates.csv: every candidate considered (rendered or excluded) with the on-chain evidence for the decision."""
import csv, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; GAL = ROOT / "data/gallery"
rows = []
for md in sorted(GAL.glob("*/meta.json")):
    m = json.loads(md.read_text()); d = md.parent
    std = "ERC-1155" if "[ERC-1155]" in m["collection"] else "ERC-721"
    cat = "art-blocks" if d.name.startswith("ab-") else "other"
    rows.append(dict(name=m["collection"], address=m.get("contract"), standard=std, category=cat, status="rendered" if (d / "result.json").exists() else "built-not-rendered",
                     slug=d.name, token=m.get("token_id"), how_verified=m.get("chain_call"), reason=""))
EXCL = [  # name, address, standard, reason (all checked with eth_call on 2026-10-21; raw in data/gallery/_probe/chain)
 ("EtherRocks", "0x41f28833Be34e6EDe3c58D1f597bef429861c4E2", "not ERC-721", "contract has no name()/tokenURI(); the rock image is not stored on chain"),
 ("CryptoPunks (original market contract)", "0xb47e3cd837dDF8e4c57F05d70Ab865de6e193BBB", "custom", "no tokenURI/image on the original contract; the art is in CryptopunksData (rendered as cryptopunks-data)"),
 ("Watchfaces PFP", "0x1B57E04c02f9328bdD417fDe6698b236b543C47f", "ERC-721", "tokenURI = https://watchfaces.world/api/pfp/{id} (HTTP API); the on-chain sibling Watchfaces World is rendered"),
 ("Lil Nouns (ipfs-metadata contract)", "0xeD11C3A182cc7A26e7Bdb766b3DAdeF15b7b50B9", "ERC-721", "tokenURI = ipfs://.../{id}.json (an unrelated collection with the same name); the real Lil Nouns 0x4b10... is rendered"),
 ("Ethereum Phunks", "0x7EBd1c2D780cECa58dA30D0a4e8655E55aB0cBFc", "ERC-721", "tokenURI = ipfs://Qm.../{id}"),
 ("Mathcastles ART", "0x9092010992533a6B870b9f74772501C3a77D1Ae0", "ERC-721", "tokenURI = ipfs://Qm.../{id}"),
 ("Sproto Gremlins", "0xEeca64ea9fCf99A22806Cd99b3d29cf6e8D54925", "ERC-721", "tokenURI = ipfs://bafy.../{id}"),
 ("Terraforms by Mathcastles Explained", "0x152888F51Beec20975124DA76dfA35Ba539BbC2D", "ERC-721", "JSON is a data URI but image and animation_url are ipfs://"),
 ("Acclimated MoonCats", "0xc3f733ca98E0daD0386979Eb96fb1722A1A05E69", "ERC-721", "tokenURI = https://api.mooncatrescue.com/... (HTTP API)"),
 ("Sam Spratt - LUCI Chapter 5 (Monument Game)", "0xDa6558fA1c2452938168EF79DfD29c45Aba8a32B", "ERC-721", "tokenURI = ipfs://"),
 ("Sam Spratt 1/1", "0x7C4111e3Bb57b636906A7246DB1e70876fd97d97", "ERC-721", "tokenURI = https://arweave.net/..."),
 ("The Monument Game Art", "0x762F83C277388F2cd21f50ff86Aa3bB77Ca998d8", "ERC-721", "tokenURI = https://arweave.net/..."),
 ("Panopticon (teto.io, scripty user per scripty README)", "0x7D2a37B7348d930E347DEd87881a979DDE2cE872", "ERC-721", "tokenURI = https://arweave.net/... on this address; not on-chain"),
 ("Terraform Navigator (scripty user per scripty README)", "0xad41bf1c7f22f0ec988dac4c0ae79119cab9bb7e", "?", "tokenURI(1)/(2) revert 'Incorrect path' (no valid token ids found); unresolved"),
 ("0xmons", "", "?", "Blockscout search finds only an ERC-20, an ERC-20 and a 1155 'x RPTC collab'; no on-chain-art NFT collection found"),
 ("Solvers", "", "?", "no matching NFT collection found by Blockscout name search (only ERC-20 'Solver' tokens)"),
 ("EthFS FileStore v1 / v2", "0xFe1411d6864592549AdE050215482e4385dFa0FB / 0x9746fD0A77829E12F8A9DBe70D7a322412325B91", "infra", "both addresses have code on mainnet (eth_getCode, data/gallery/_probe/chain). No collection using them found among the 256 data-URI collections scanned (verified-source flag scan, data/gallery/discovery/srcflags.jsonl)"),
 ("scripty ScriptyStorageV2 / ScriptyBuilderV2", "0xbD11994aABB55Da86DC246EBB17C1Be0af5b7699 / 0xD7587F110E08F4D120A231bA97d3B577A81Df022", "infra", "ScriptyStorageV2 has code on mainnet; users named in the scripty README (CryptoCoaster, the metro, GOLD, Panopticon) not resolvable to a mainnet token with an on-chain tokenURI in this scan"),
 ("Art Blocks (other 470+ projects)", AB := "see data/gallery/artblocks-survey/generator_survey.json", "ERC-721", "all 494 project ids probed through the on-chain Generator; 23 rendered here"),
]
for n, a, s, r in EXCL:
    rows.append(dict(name=n, address=a, standard=s, category="excluded", status="excluded", slug="", token="", how_verified="eth_call tokenURI/name probes", reason=r))
with open(GAL / "candidates.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(len(rows), "rows;", sum(1 for r in rows if r["status"] == "rendered"), "rendered")
