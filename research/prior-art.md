# Prior art: JPEG Unplugged

Prepared 2026-10-21. All sources were accessed on **2026-10-21** unless a row says otherwise. Every source cited below has an ID
(`[A1]`, `[T3]`, ...) that resolves to a full citation, URL and access date in the Bibliography (section 9). Where we could save the page, the
raw copy is under `data/raw/prior-art/<key>.<ext>` (indexed in `data/raw/MANIFEST.jsonl`, source `prior-art`); the key is given in the
bibliography. Companion table: `research/prior-art-sources.csv`.

**How to read confidence labels.** "Read in full/part" means we opened the saved paper or page and extracted the number ourselves.
"Search-snippet only" means we only saw a search-engine summary and have NOT verified it; those items are flagged and must not reach the paper
without a first-hand read. Numbers marked "(derived)" are our own arithmetic on the cited figures.

Search limits: the web-search tool is US-only and returns summaries; we had no Google Scholar/Semantic Scholar/DBLP. The "nobody has done X"
statements in section 7 are therefore "not found in a diligent but not exhaustive search" and need a second pass (Scholar forward-citations
of A1, A2, A3) before the paper says "to our knowledge".

---

## 1. Bottom line for positioning

**Closest prior work (read it before drafting the related-work section):**

1. **Wang, Gao, Wei, "Do NFTs' Owners Really Possess their Assets?" (WWW '23, arXiv 2212.11181) [A2]**: 12,353 Ethereum NFT contracts, 6,234,141 NFTs,
   tokenURI via archive node, multi-gateway IPFS retrieval over ~6 months. Reports 25.24% of contracts with inaccessible assets, 10 centralized hosts =
   79.04% of off-chain assets, 33.77% of decentralized assets fully retrievable. Closest in spirit and scale; but 2022 data, no rendering, no
   explicit on-chain (data-URI) class, no per-year breakdown that we saw, no domain-registrability analysis.
2. **Das et al., "Understanding Security Issues in the NFT Ecosystem" (CCS '22, arXiv 2111.08893) [A1]**: 12,215,650 OpenSea assets as of 2021-06-15; IPFS vs
   non-IPFS and liveness (3-attempt HEAD/GET). 88.71% of image URLs and 80.69% of metadata URLs off IPFS; 3.91% (images) / 9.04% (metadata) of IPFS
   items gone June to December 2021; 52.7% of non-IPFS image URLs inaccessible (derived).
3. **Balduf, Florian, Scheuermann, "Dude, where's my NFT?" (DICG '22, arXiv 2210.11166) [A3]**: the only academic paper we found that manually inspects contracts
   to find on-chain storage. 786 digital-art NFTs (top-1000 OpenSea by last sale, 2022-08-01): 412 (52.4%, derived) on-chain/on-chain. Crucially it counts generative
   art whose *source* is on-chain as on-chain "since reconstruction is possible", and explicitly punts on the runtime environment, which is our gap.
4. **OpenSea's own "Metadata" label (help article dated 2026-02-02) [T1]**: five programmatic labels (Fully onchain / Onchain metadata / Decentralized /
   Centralized / Unknown) plus a collection filter. This is the closest *deployed* on-chain checker. It labels Art Blocks as "Onchain metadata" (media may be
   external). It does not publish counts, method, or per-year numbers, and does not say whether it renders.
5. **ClubNFT / YourNFTs analysis (Right Click Save, 2022-06-20) [T2]**: 12,359,778 NFTs through Dec 2021; 9.06% on-chain / 40.70% HTTP / 49.55% IPFS / 0.69% Arweave;
   shows how sensitive shares are to rules (66.44% HTTP if IPFS-via-gateway is HTTP). String-matching classifier, no rendering.

**Clearest novelty gaps (details in section 7):** (a) rendering-based test of whether "on-chain" art actually draws with the network off, including CDN
scripts/fonts; (b) a 2026 census (every published count is from 2021 to 2022 data, or has no stated n); (c) by-mint-year trends; (d) registrability/expiry of the
domains NFT media points at; (e) systematic "marketed as on-chain" vs measured; (f) gateway-hostname baking right after the 2024 to 2026 gateway/pinning shutdowns.

**Do NOT claim:** "first measurement of NFT link rot" (Das, Wang, alwaysNFT predate us); "first to classify NFT storage"; "first on-chain checker"
(OpenSea ships one; Onchaininator and NFT Scanner existed); "first to notice Art Blocks relies on CDN p5.js" (Right Click Save 2023 and Art Blocks' own 2024 post say so);
"most NFTs are off-chain" as a discovery (known since at least 2021). Section 8 has a claim-safety table.

---

## 2. On-chain checker tools and sites

| # | Tool / site | URL | What it checks | Method | Coverage | Detects external deps (CDN p5.js, fonts)? | Online on 2026-10-21? | Ref |
|---|---|---|---|---|---|---|---|---|
| 1 | OpenSea "Metadata" field + stats-page "metadata storage type" filter | https://support.opensea.io/en/articles/13355231-what-is-the-metadata-field-on-nft-pages ; https://support.opensea.io/en/articles/10549939-how-do-i-use-the-stats-pages-on-opensea | Where metadata is stored; 5 labels: Fully onchain ("all metadata and media stored directly on a blockchain"; examples CryptoPunks, Nouns, Loot, Autoglyphs), Onchain metadata ("media may be served externally"; examples Art Blocks, ENS), Decentralized (IPFS/Arweave), Centralized, Unknown | "Determined programmatically", "may not be entirely accurate"; method otherwise undisclosed. Appears to be static classification, not rendering (inference; not stated) | All OpenSea-indexed collections, all chains (help article is chain-agnostic) | Partially: it treats Art Blocks as not fully onchain, but does not say why or how deps are judged | Yes (help pages dated 2026-02-02) | [T1], [T1b] |
| 2 | OpenSea developer docs, "Metadata storage" | https://docs.opensea.io/docs/metadata-storage | Documents the options (hosted JSON, ipfs://, ar://, data: URI, ERC-4804) and recommends data URI for small/generative collections | Documentation only | n/a | No | Yes | [T1c] |
| 3 | Onchaininator | https://onchaininator-test.149-28-255-65.sslip.io/docs | Labels each NFT Unread / Hosted / Hashed / Part onchain / Fully onchain; "Fully onchain" = all files *the check identifies* are on the NFT's chain; shows original image link and viewer-loading separately; offers to save a copy on-chain | Static analysis of file locations (per search-engine summary of the docs; page itself not retrievable) | Unknown | Docs say only "files identified by the check"; cannot tell | **Unreachable**: two fetch attempts timed out on 2026-10-21 (host is a `-test` sslip.io address; looks like a pre-release deployment). Unknown, not dead. Not archived | [T3] (search-snippet only) |
| 4 | NFT Scanner (Indorse) browser extension | https://addons.mozilla.org/firefox/addon/nft-scanner/ | OpenSea listing overlay: "on-chain spectrum", decentralization score, media and metadata location | Reads OpenSea, Etherscan, Airtable APIs; prototype | OpenSea pages only | No evidence | Listing exists; v0.0.7, last updated June 2021 per listing; almost certainly unmaintained (not tested) | [T4] |
| 5 | ClubNFT "X-ray" / wallet insights | https://www.rightclicksave.com/article/the-nft-apocalypse (describes it) | Buckets each wallet NFT as on-chain / IPFS / private web server; backup of IPFS items | String-match on attribute URLs (pseudocode published in [T2]); worst attribute wins | Per-wallet; also used on the 12.36M-token YourNFTs dataset | Partly: [T5] says projects "marketed as on chain" show up as web/IPFS because of off-chain elements, e.g. CyberBrokers; Art Blocks "also stores data via HTTP" [T2] | Product status not verified (we only have 2022 to 2023 descriptions) | [T2], [T5], [T6] |
| 6 | JPG "On-Chain Canon" (curated list, TCR) | https://www.jpg.space/canons/onchain | Community-curated list of canonical on-chain collections; proposed by Chainleft, launched April 2023 | Human curation / token-curated registry, not automated | Curated, small | Debated explicitly (p5.js edge case) | **Unreachable**: HTTP 522 on 2026-10-21 (twice). Unknown. Entries never seen | [T6] (article), Bankless pointer |
| 7 | Art Blocks "True On-Chain Artwork" page + on-chain generator | https://artblocks.io/onchain ; https://docs.artblocks.io/protocol/on-chain-generator.md | Not a checker for others; self-attestation that ~90% of Art Blocks projects (Curated, Studio, Engine on Ethereum) can be rebuilt from chain data | Vendor claim | Art Blocks only | Yes by construction: their own docs say ~10% still reference "widely-distributed CDN packages" | Yes | [T7], [T8] |
| 8 | "Is it on-chain?" how-to guidance (Bankless; web3.university) | https://www.bankless.com/onchain-nfts | Manual test: call tokenURI(); `http:`/`ipfs:` means not on-chain; `data:` means on-chain metadata | Manual | n/a | No | Yes | [T9] |
| 9 | Etherscan NFT pages, OpenSea per-NFT badges (pre-2026) | n/a | We found **no** Etherscan on-chain badge in our searches and no OpenSea badge before the 2026 Metadata field | n/a | n/a | n/a | Not verified (negative search result only) | none |
| 10 | EthFS / scripty.sol / Art Blocks Dependency Registry | https://github.com/holic/ethfs ; https://unpkg.com/scripty.sol@2.1.1/README.md | Infrastructure to *make* art self-contained (SSTORE2 chunked files at deterministic addresses; HTML builder), not checkers | n/a | n/a | n/a (they solve the CDN problem) | Yes (READMEs fetched) | [T10], [T11] |
| 11 | Zora metadata renderers | https://docs.zora.co/contracts/DropMetadataRenderer ; /EditionMetadataRenderer | Edition renderer encodes name/description on-chain with media URIs off-chain (updatable); Drop renderer forwards a base URI that "may point to IPFS" | Docs | n/a | n/a | Search-snippet only | [T12] (search-snippet only) |

**Things we looked for and did not find:** a Dune dashboard of storage type by collection; any public "fully on-chain NFT" index with automated verification
(the Flow NFT Catalog is a different thing: a developer registry, says nothing about storage); `onchainchecker`-style sites under that name; any
Etherscan "on-chain" badge. The OpenSea Metadata field is therefore the only large-scale deployed classifier we found, and it is a label, not a measurement.

**Take-away:** checkers classify *where the pointer goes* (static). None we found loads the artwork with the network disabled, and none reports
which hostnames a "fully on-chain" artwork still fetches at render time.

---

## 3. Quantitative studies of NFT storage, liveness and link rot

All rows below were read from the saved source unless flagged. "Dead" definitions differ; do not average across rows.

| ID | Study | Date of data | Sample | Method | Headline numbers | Limitations (ours and theirs) |
|---|---|---|---|---|---|---|
| [A1] | Das, Bose, Ruaro, Kruegel, Vigna, *Understanding Security Issues in the NFT Ecosystem*, CCS '22, pp. 667-681, doi:10.1145/3548606.3559342 | OpenSea dataset as of **2021-06-15**; re-crawled June to Dec 2021 | 12,215,650 OpenSea assets; 3,175,644 with valid `metadata_url`; 8,363,550 with non-empty `image_url`; 3,860,607 with no `image_url` (hosted by OpenSea) | HEAD, then GET if non-200; URL "inaccessible" only if 3 attempts over 15 days agree; IPFS identified by URL pattern | IPFS images 944,420 (11.29%, derived) of image URLs, of which 36,929 (3.91%) gone; IPFS metadata 613,341 (19.31%, derived), 55,454 (9.04%) gone. Non-IPFS: 88.71% of image URLs, 80.69% of metadata URLs. Total image URLs inaccessible: 3,945,231 = 32.30% *of all 12.2M assets* (= 47.2% of the 8.36M with an image URL, derived). Non-IPFS image URLs: 3,908,302 of 7,419,130 inaccessible (52.7%, derived). OpenSea still served cached copies of 2,691,030 (68.21%) of the inaccessible ones. "Lost" NFTs had $160,761,805 in sales over 118,294 transactions. Metadata_url changes: 89,089 (2.89%) and 35,446 (about 1.15%) between crawls | OpenSea-listed only (selection bias); 2021 snapshot; no on-chain/data-URI class; the headline 32.30% uses a denominator that includes assets with no image URL, so quote it carefully. The per-bar existent/non-existent assignment for non-IPFS *metadata* (2,082,874 / 479,429) is inferred from figure order, consistent with the text for images; re-check against the CCS PDF before quoting |
| [A2] | Wang, Gao, Wei, *Do NFTs' Owners Really Possess their Assets?*, WWW '23, doi:10.1145/3543507.3583281, arXiv 2212.11181 (v1 2022-12-21) | Collection ran over a six-month window in 2022 (exact dates not stated in what we read) | 12,353 Etherscan-tagged NFT contracts; 3,123 (25.28%) empty supply; 6,234,141 NFTs; tokenURI from own full archive node (88.37% of contracts), rest from OpenSea | Multi-gateway + local IPFS node; repeated rounds over 6 months to handle IPFS flakiness; assets only 45.75% as many as NFTs at end of path | 3,118 (25.24%) contracts have inaccessible assets; 2,653 (21.48%) contracts include duplicated assets; 10 centralized platforms host 79.04% of off-chain assets; 4,801,699 (77.02%) centralized-storage NFTs sit on 1,184 sites; tokenURI-stage: 5,862 contracts / 4,802,766 NFTs centralized vs 2,385 contracts / 510,154 NFTs decentralized; only 33.77% of decentralized assets fully retrievable; of 6,619 measurable contracts 30.73% decentralized / 6.71% semi / 62.56% centralized; 48 collections have decentralized metadata but centralized assets | Contract-level percentages mix tiny and huge contracts; no data-URI/on-chain class beyond a small "Other" (17,096 NFTs, 110 contracts, "can be regarded as on-chain to a certain extent"); no rendering; no domain-expiry analysis; 2022 |
| [A3] | Balduf, Florian, Scheuermann, *Dude, where's my NFT?*, DICG '22, doi:10.1145/3565383.3566106, arXiv 2210.11166 | 2022-08-01 (ranking, URI resolution); IPFS DHT crawl every 6 h for one week | 786 digital-art NFTs / 51 contracts drawn from OpenSea top-1000 by last sale price | Manual inspection of contracts for on-chain storage; resolves cloud/IPFS URIs; scans transactions for URI-setter calls; DHT provider search | Metadata/asset: on-chain/on-chain 412; ipfs/ipfs 254; cloud/cloud 79; cloud/ipfs 17; on-chain/cloud 11; ipfs-dead 7; arweave 3; cloud/on-chain 2; cloud-dead 1. **19 of 51 contracts changed token metadata URI at least once**. 254 IPFS NFTs: 50% of CIDs provided by <10 nodes over the week; 33 CIDs with no DHT provider found (but all but 7 resolved in Sec. 2). All 254 used text CIDs (>50 bytes on-chain); many hard-code a public gateway URL | Top-sale art only, so heavily biased toward on-chain generative work; small n; classifies on-chain *source + off-chain pre-render* as on-chain "since reconstruction from on-chain data is possible" and says a runtime environment may also need preserving, but does not test it. Authors themselves note the contrast with [A1] stems from sample differences |
| [A4] | Barrington & Merrill, *The 'Fungibility' of Non-Fungible Tokens*, arXiv 2209.14517 (Sept 2022 preprint, UC Berkeley) | Moonstream ERC-721 transfers, 2021-04-01 to 2021-09-25 | 9,292 contracts, 7,020,950 tokens | tokenURI called for **one token per contract**, host root extracted, assumed to apply to the whole collection; 72.43% of contracts had readable ABI | Non-permanent (private domain 37.92% + cloud, derived 7.14%) 45.07%; not readable 14.75%; "permanent" 40.18% = IPFS 21.59% + Pinata 7.97% + base64 JSON 10.63% (746,671 tokens) | Treats IPFS as permanent; classifies `data:application/json;base64` as on-chain without checking the nested image field; one-URI-per-contract assumption (they validated on a 188-contract sample); unreadable-ABI contracts are 14.75% of tokens; non-peer-reviewed preprint |
| [A5] | Salem, *Hidden Risks: The Centralization of NFT Metadata*, arXiv 2408.13281 (2024-08-22) | Not stated | "Top-selling" OpenSea collections; **n not reported** | tokenURI via Etherscan/web3.py, host classified | IPFS 38.84%, centralized 31.68%, on-chain 25.62%, uncertain 3.86% | No sample size, no dates, no link-rot, references appear loosely matched, mentions a survey that is not in the paper. Treat as weak; cite only as "recent preprint" |
| [T2] | Hladek (ClubNFT) on YourNFTs.org dataset, Right Click Save, 2022-06-20 | Dataset through Dec 2021 | 12,359,778 unique NFTs (YourNFTs claimed "all"; ClubNFT found CryptoKitties, ENS, MarbleCards missing) | String-match on each attribute (`ipfs`, `ipns:`, `arweave.net`, `http(s):`, else "On-chain"); NFT takes its worst attribute | On-chain 1,119,396 (9.06%); HTTP 5,030,843 (40.70%); IPFS 6,124,261 (49.55%); Arweave 85,277 (0.69%); IPNS 1. Alternative rule (IPFS gateway URL = HTTP): HTTP 66.44%, IPFS 23.81%. YourNFTs original: 9% / 55% / 36% | Anything with no matching substring, including empty or garbage values, is labeled "On-chain" by their pseudocode (our reading); no check that data URIs decode or that image is also on-chain; no liveness test; author is employed by a backup-product vendor |
| [T13] | alwaysNFT (G. Harrison), "When good NFTs go bad", Medium, 2022-05-13 (archived copy via Wayback) | Spring 2022 | "about half a million" NFTs (title: "almost 500,000"), examples include Polygon collections | Vendor's pinning-service testing; classes: tokenURI broken, tokenURI IPFS "aged out", gateway URL issues | "about 20%" had bad or expired links | Vendor blog, sample/selection not described, chains mixed, method unreproducible. A Hedera blog [T14] repeats "more than 400,000 NFTs ... almost 20%" without dating or sourcing it |
| [A6] | Shi, Cheng, Han, Cheng, Chen, *A Closer Look into IPFS*, POMACS/SIGMETRICS 2024, doi:10.1145/3656015 | 2024 | >4M files with CIDs from public IPFS datasets | Passive CID collection + retrieval tests | About 50% of stored files are NFT-related; top-50 peers (mostly cloud) serve 95% of files; NFT files often need multiple retrieval attempts | IPFS-generic; not an NFT census. Useful for "IPFS is more centralized than advertised" |
| [A7] | Mandiant/Google, Eitzman, "NFT Storage and Availability: A Risk Worth Considering", 2022-06-02 | 2022 | Case examples (Mintable on CloudFront, SuperRare on IPFS, Valuables privately hosted) | Qualitative | None quantified | Qualitative |
| [T14b] | dappGambl, "95% of NFTs worthless" (via The Register and PetaPixel, 2023-09-20/21) | Sept 2023 | 73,257 collections (CoinMarketCap + NFTScan) | 69,795 (about 95%) with market cap 0 ETH | This is a *value* statistic, not a storage or liveness statistic; do not use as link-rot evidence. The "23 million people" figure is an extrapolation; the publisher is a gambling site | n/a |

**Cross-study comparison on "share fully on-chain" (do not put these on one axis without caveats):**
Barrington 10.63% of tokens (base64 JSON, Apr to Sep 2021, one URI per contract) [A4]; ClubNFT/YourNFTs 9.06% of tokens (through Dec 2021, substring rule) [T2];
Salem 25.62% (top-selling collections, n unstated) [A5]; Balduf 52.4% (derived; top-sale digital art only) [A3]. The range reflects population choice (all tokens vs
top collections vs art), unit (token vs contract), and definition. Our unit (collections with >=100 holders) and our two-level rule (metadata and media both on-chain AND renders offline)
are not what any of these use, so there is no like-for-like comparison to make; say so explicitly.

**Related infrastructure measurement:** Balduf et al. (ICDCS 2022) monitor IPFS data requests for 15 months [A8, search-snippet only]; Sokoto et al. (USENIX Security 2024)
analyze moderation/denylists on 368,762 files [A9, search-snippet only]. Neither is an NFT census. Cite only as IPFS context.

**Other NFT security literature (context, not storage studies):** SoK on NFT security reviewing 142 incidents [A10]; EIP-based NFT standards study repeating "about 45% of tokens link to
mutable or off-chain resources" from prior work [A11]; SemNFT (CUHK-Shenzhen, 2024) proposing embeddings stored on-chain [A12], a design paper, not a measurement.
The "45%" in [A11] traces to Barrington [A4] (45.07%); do not count it as an independent replication.

---

## 4. Commentary and primary essays

- **Moxie Marlinspike, "My first impressions of web3", 2022-01-07 [T15].** NFT stores a URL; whoever controls the server/domain can change the image, and he built an NFT that served
  different content depending on the viewer; OpenSea removed it "after a few days, without warning or explanation". It also notes wallets built on Firebase rather than chain state.
  Anecdote, not measurement, but the standard citation for "token is not the art".
- **David Rosenthal (DSHR blog), "NFTs and Web Archiving", 2021-04-15 [T16].** Frames NFTs as link rot; reports Nifty Gateway did not seed the IPFS files it sold "a few weeks later" (his words). Early, primary-ish.
- **Jason Bailey, "The NFT Apocalypse", Right Click Save, 2022-06-20 [T5].** Repeats ~10% / ~40% / ~50%; claims over 98% of OpenSea NFTs remain "unfrozen"/editable (his claim, no method given); says many projects marketed as on-chain "really only store a portion"; CryptoPunks and CyberBrokers cited.
- **William Peaster, "What Does 'On-Chain' Really Mean?", Right Click Save, 2023-06-23 [T6].** Panel around JPG's On-Chain Canon. Chainleft: on-chain means the art cannot be lost; a minimum is art elements stored on the same chain; metadata on-chain but art or generator off-chain is not on-chain; cross-contract cases (CryptoPunks image contract, CrypToadz) are edge cases; **Art Blocks "sometimes includes references to some off-chain libraries, such as p5.js"**; thumbnails served from IPFS because of HTML constraints; Chris King: nearly every "on-chain" project has some data (traits, rarity, names) that is off-chain and not reproducible. This is the strongest evidence that the community already treats runtime dependencies as the definitional edge case, and also that nobody measured it.
- **Bankless, "Understanding Onchain NFTs", 2023-10-26 [T9]:** off-chain to on-chain spectrum explainer.
- **DappRadar, "Why CyberBrokers Paid $250,000 To Make NFTs Completely On-chain", 2022-03-14 [T17].** Moved from IPFS-only to on-chain: 91.04 ETH (about $250,000); SVG art still has an IPFS backup. Illustrates cost and the marketing framing. Compare with ClubNFT's note that CyberBrokers still has off-chain elements [T5].
- **OpenSea blog, Michael Hirsch, "How Chain Runners Sparked 300+ Onchain NFT Collections", 2025-07-30 [T18].** Author's (Facet / Indelible Labs co-founder) claim that Chain Runners (Nov 2021) seeded "300+" on-chain collections; a vendor-adjacent count, not a census. Useful as an upper-level estimate to compare against our own count of on-chain collections.
- **Hladek/Right Click Save "How many NFTs are actually on the blockchain?" [T2]:** see section 3.
- **Geoffrey Huntley's "NFT Bay" (Cointelegraph, 2021-11-18/19) [T19]:** claimed "majority of images ... hosted on Web 2.0 storage, which is likely to end up as 404"; ClubNFT found the torrent files empty [T2]. Cite as a stunt, not data.
- **Hedera blog [T14]:** vendor, 400,000 NFTs scanned, ~20% missing, Hedera NFTs ~7.6%; undated, unsourced.

---

## 5. Specific context we will cite (with primary sources and our own spot checks)

All "our eth_call" results come from public RPCs on 2026-10-21 (`eth.drpc.org`) and are saved raw as `data/raw/prior-art/tokenURI_*.json`.

### 5.1 Art Blocks
- Core-contract `tokenURI` returns an **HTTP API URL**, not on-chain data. Our eth_call: Chromie Squiggle core `0x059EDD72...aC3a` token 0 returns `https://api.artblocks.io/token/0` (32 chars); flagship `0xa7d8d9ef8D8Ce8992Df33D8b8CF4Aebabd5bD270` token 78000000 and V3 flagship `0x99a9B7c1116f9ceEB1652de04d5969CcE509B069` token 385000000 return `https://api.artblocks.io/token/<id>`. On 2026-10-21 `https://api.artblocks.io/token/0` answered **HTTP 302 to `https://token.artblocks.io/0`** (the legacy host redirects; the documented production pattern is `token.artblocks.io/{chainID}/{contract}/{tokenID}`) and the chain-qualified URL returned 200 [T8b]. So every marketplace render of an Art Blocks token depends on a company-run API whose pointer is baked on-chain and survives only through a redirect. Saved: `spot_api_artblocks_token_0.json`, `spot_token_artblocks_squiggle0.json`.
- The scripts **are** on-chain and the **on-chain generator** (`getTokenHtml`) assembles a self-contained HTML page from chain data, "no servers required" [T7]. Docs: "approximately 90%" of flagship projects are fully on-chain; "remaining ~10% referencing widely-distributed CDN packages" [T7].
- **Dependency Registry:** Art Blocks "uploaded their first dependency, p5js v1.0.0, to the registry in January 2024" [T8]. Before that, p5.js came from a CDN (generator HTML had a cdnjs script tag; docs list "CDN script tag for the project's chosen library" in the generated HTML structure [T7]). Docs state their own definition permits "a single dependency to be housed on a software registry" [T8].
- **Erick Calderon, "True On-Chain Artwork: A Four-Year Journey", 2024-11-27 [T20]:** at launch (2020) "only the core artwork code was on-chain while artists still relied on off-chain tools and libraries"; as of the post, "90% of all projects ... can now be constructed entirely from the blockchain". This is a primary admission that pre-2024 "on-chain" Art Blocks needed a CDN.
- Hence for rendering tests: Art Blocks tokens are the canonical case where "static on-chain" and "renders offline" differ, and the answer depends on the *date and library version*.

### 5.2 EthFS, SSTORE2, scripty.sol, on-chain p5.js
- EthFS: public on-chain file store; SSTORE2 writes data as contract bytecode; files split into 24 kB chunks at deterministic addresses; FileStore registry of names; same FileStore address on Ethereum, Base, Optimism, Zora [T10]. scripty.sol: gas-efficient HTML builder referencing already-deployed storage, examples load p5.js from EthFS FileStore V2 and three.js from compressed base64 [T11]. Art Blocks docs note SSTORE2 deployment cost (~200 gas/byte) makes it practical for small files (~24 KB per file, 256 KB per project) [T8-search-snippet].
- Implication: after 2022 to 2023 the *tooling* exists to make p5.js/three.js self-contained, so by-year breakdown of CDN dependence is expected to show a shift; nobody has measured it.

### 5.3 Autoglyphs, Loot, Chain Runners, Blitmap, Nouns, BAYC (our eth_call spot checks)
| Collection | Primary claim | Our `tokenURI` result (2026-10-21) | Reading |
|---|---|---|---|
| Autoglyphs `0xd4e4078ca3495de5b1d4db434bebc5a986197782` (2019) | Larva Labs: "first art project that was both generated and stored entirely on-chain"; generator run by the EVM at mint; output in event data [T21] | token 1: `data:text/plain;charset=utf-8,...` (4,318 chars; ASCII glyph drawing instructions) | Truly on-chain; note the "image" is a text drawing recipe, so any renderer must interpret it |
| Loot `0xFF9C1b15B16263C61d017ee9F65C50e4AE0113D7` (Aug 2021) | Fully on-chain text gear per CoinDesk [T22] | token 1: `data:application/json;base64,...` (1,681 chars) | On-chain metadata; media is a base64 SVG inside (not decoded here) |
| Chain Runners `0x97597002980134beA46250Aa0510C9B90d87A587` (Nov 2021) | "Art and metadata stored in the Ethereum contract" [T18] | token 1: `https://api.chainrunners.xyz/tokens/metadata/1?dna=...` (129 chars); API answered 200 and calls itself "100% generated on chain" | **Counter-example for a tokenURI-only classifier:** data lives on-chain but the contract's tokenURI points at an API. A census that classifies by tokenURI scheme would call this `http`. Needs a rule (call alternative render functions, or flag as "claimed on-chain, tokenURI http") |
| Blitmap `0x8d04a8c79cEB0889Bdd12acdF3Fa9D207eD3Ff63` (Mar 2021) | On-chain pixel data (Dom Hofmann project) [T22] | token 1: `https://api.blitmap.com/v1/metadata/1`; API returned HTTP 500 on 3 attempts on 2026-10-21 | Same pattern. 500 on one day is "unknown", not dead |
| Nouns `0x9C8fF314C9bc7F6e59A9d9225Fb22946427eDC03` | On-chain descriptor builds SVG; token holds a descriptor address [T23, contract source `NounsToken.sol`] | `ownerOf(100)` works but `tokenURI` for ids 0, 100, 1000 **reverts** on both `eth.drpc.org` and `eth.rpc.blxrbdn.com` (also with explicit gas 30M and 100M on drpc) | Cause not diagnosed (RPC gas cap, a descriptor change, or a real fault). **Warning for census:** heavy on-chain renderers can revert on free RPCs; never label such contracts `broken` without retry on another endpoint / own node. Saved: `nouns_tokenURI_revert_attempts.json`, `nouns_ownerOf_100.json` |
| BAYC `0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D` | n/a | token 1: `ipfs://QmeSjSinHpPnmXmspMjwiXyN6zS4E9zccariGR3jxcaWtq/1` | Standard IPFS control |
| CryptoPunks | Original contract stores only an image-sprite SHA-256; image reconstruction contract deployed Aug 2021, 73M gas, about 4.05 ETH, ~$12,205 at the time, not linked from the original contract [A3] | wrapped-punks contract returned `URI query for nonexistent token` for id 1 (not informative) | The "two-contract" edge case [T6] |

### 5.4 Nouns / descriptor pattern
`NounsToken.sol` (fetched) holds `INounsDescriptorMinimal public descriptor` with a lock flag and `tokenURI` delegating to the descriptor [T23]; descriptor swappability is a mutability point worth checking in claims (a "locked" flag exists).

---

## 6. Incidents where art disappeared, was at risk, or was swapped

Chronological. "Primary" means the project/vendor statement; otherwise press.

| Date | Event | What is established | Source (all accessed 2026-10-21) |
|---|---|---|---|
| 2018 to 2021 | Ascribe/early cryptoart platform graveyard | John Karel's *Skull Still Life* (2018) content disappeared; Ascribe-era editions lost (Death Wannabe: 3 of 10 remain accessible; Disaster Suit lost metadata) per HASH'D essay (secondary, 2026) | [T2] (Karel), [T24] |
| 2021-04-15 | Nifty Gateway IPFS files not seeded | Rosenthal's claim | [T16] |
| 2021-11 | Hic et Nunc (Tezos) goes offline | Front end vanished; contracts persisted and works were relisted on objkt.com (e.g. Whitworth relisted 44 NFTs). This source does not discuss where media lived; other reports say IPFS (not verified), so treat as a front-end failure, not a documented media-loss event | [T25] (Art Newspaper 2021-11-16) |
| 2022-01 | Moxie's viewer-dependent NFT | OpenSea delisted it | [T15] |
| 2022-12-08 | FTX US NFTs (Solana, incl. Coachella pass) | Metadata served from FTX US web2 API; domain redirected to restructuring page; images blank in wallets and marketplaces | [T26] (Cointelegraph), [T26b] (Bitcoin.com) |
| 2024-06-30 | NFT.Storage Classic stops accepting uploads/pins | Notice: existing data retrievable via gateway and Filecoin but "latency and availability may degrade" | [T27] (nft.storage js-client README) |
| 2024-07-17 | KnownOrigin (eBay) winds down on-chain marketplace/minter | "We will continue to cover pinning costs for the next 2 years" (so to about mid-2026); what happened after is not verified | [T28] |
| 2024-08-14 | Cloudflare's public IPFS gateway hostnames stop connecting to IPFS | Primary Cloudflare blog; redirect period 2024-05-14 to 08-14; users must switch to ipfs.io/dweb.link. Any metadata with `cloudflare-ipfs.com` baked in broke unless repointed | [T29] |
| 2025-04-24 | RTFKT/Nike CloneX and Animus images blanked | Images "stored off-chain" on Cloudflare; contract tier change; text "This content has been restricted". Fix: move to Arweave (AR Drive) | [T30] (Decrypt) |
| 2026-01-27 | Nifty Gateway closure (withdrawal-only; official shutdown 2026-02-23, later extended to 2026-04-23; plan to migrate metadata/media to Arweave) | Omnibus contract, no per-artist contracts | [T31] (Bankless) |
| 2026-04-27 | Foundation shuts down after a failed acquisition | Tokens unaffected; zkm.de timeline: platform offline 27 April 2026, Foundation-operated IPFS gateway/pinning support ends 27 April 2027; other outlets differ by days on the shutdown date | [T32] (zkm.de, The Defiant, Bankless) |
| 2026-08-15 | Infura IPFS service ends (uploads/pinning off 2026-08-03) | API and dedicated gateways off; content not moved no longer served via Infura; `*.infura-ipfs.io` and `ipfs.infura.io` URLs baked into metadata break | [T33] (Filebase notice, 2026-07-29; first-party Infura notice not retrieved) |
| 2026-08-24/25 | Interplanetary Shipyard to wind down 2026-09-30 | Protocol Labs declined to renew funding; Shipyard to stop operating public infrastructure incl. `ipfs.io`, `dweb.link`, `delegated-ipfs.dev`, bootstrap nodes; Protocol Labs owns domains and will decide their future; IPFS itself not shutting down | [T34] (Cointelegraph, Cryptobriefing, RuntimeWire); Shipyard's own post not retrieved |

**Not found despite targeted searches:** a documented case where an *expired domain was bought by a third party and used to swap NFT art*. What exists: (i) a
GitHub gist describing the KungFungus project whose creators rugged and let the domain lapse, listing what a squatter *could* do [T35] (risk, not incident);
(ii) FTX.US redirecting to a bankruptcy page (the domain stayed under the estate's control). Section 7 treats expiry/registrability as unmeasured, not as
"known exploited". A secondary mention of Nifty Gateway/"$11 million NFT album went missing" appears in Decrypt's CloneX piece [T30] and a search snippet attributed to
@CheckMyNFT; it relates to 3LAU's album and we could not verify it, so it is **not** to be used.

Also noted but unverified: a "2021 Stanford study" with "32.7% broken links" appears in a secondary blog snippet; probably a garbled version of [A1] (32.30%). Do not cite.

---

## 7. Gaps: what nobody (that we found) has measured

| # | Gap | What exists | Why our design fills it |
|---|---|---|---|
| G1 | **Rendering-based dependence of on-chain art on the network** (CDN scripts, fonts, images, `import` maps) | Qualitative (Right Click Save 2023 p5.js edge case [T6]); vendor self-report (Art Blocks ~10% CDN [T7]; first on-chain p5.js Jan 2024 [T8]); Balduf explicitly leaves runtime out [A3]; OpenSea has an "Onchain metadata, media may be external" bucket without counts [T1]. No measurement of how many "on-chain" artworks fetch anything over the network when drawn | gallery's 3-condition harness (normal / network blocked / blocked + local archive of declared deps) with request logs |
| G2 | **A current census** | Newest datasets are 2021 to 2022 ([A1] 2021, [A2] 2022, [T2] Dec 2021, [A4] 2021). [A5] (2024) has no n. [T13] 2022 | 2026 snapshot of every ERC-721/1155 collection with >=100 holders, with saved raw eth_call evidence |
| G3 | **By-mint-year trends** (storage and liveness) | None found. [A1] gives one snapshot and a 6-month change | Deploy-date join from universe; shows when on-chain share and gateway-baking changed |
| G4 | **Domain expiry / registrability of NFT media hosts** | [A2] counts hosting concentration (1,184 sites) but not registrability; general dangling-DNS work (CCS '16, Palo Alto Unit 42) and ENS expiry [A13] exist; HowToGeek-style commentary asserts the risk; no NFT-host measurement | Dead-domain deep dive (Phase 2): NXDOMAIN + RDAP status. Need an ethics note: observe, never register |
| G5 | **"Marketed as 100% on-chain" vs measured** at scale | Anecdotes (ClubNFT: CyberBrokers, Art Blocks [T5]; Peaster [T6]); no systematic comparison | claims's quoted claims joined to census/gallery results |
| G6 | **Mutability of "on-chain" collections** (setBaseURI, proxies, descriptor swaps) | [A3]: 19 of 51 contracts (top-sale art) changed URI; OpenZeppelin forum and a Substack note BAYC's owner could still change baseURI (search-snippet only) | Count mutability among the on-chain set |
| G7 | **Gateway-hostname baking** and its relation to 2024 to 2026 shutdowns | [A3] notes many contracts hard-code a gateway; [T2] shows sensitivity (66.44% vs 49.55%); Cloudflare 2024, Infura 2026, Shipyard Sept 2026 are fresh | Count tokenURIs/images containing dead gateway hostnames; measure what loads now |
| G8 | **Chain-qualified "on-chain but tokenURI is http"** | Observed by us (Chain Runners, Blitmap, Art Blocks all return API URLs) but unreported | Methodology contribution: classify at the "reconstructable from chain" level, not only tokenURI scheme |
| G9 | **Liveness after pinning lapses with date-stamped evidence** | Vendor claims (~20% [T13]); academic ones in 2021 to 2022 | Fresh liveness, timeouts recorded as unknown |
| G10 | **Per-render-function RPC fragility** | Not discussed anywhere we saw | Nouns example suggests a data-quality caveat worth stating |

---

## 8. Claim-safety table for the paper

| Claim | Status | Fix |
|---|---|---|
| "We are the first to measure NFT link rot / persistence" | **Unsafe** | Cite [A1], [A2], [T13] and position as an update with new methods |
| "First classification of NFT storage location" | **Unsafe** | Cite [A1], [A2], [A3], [A4], [T2], [T1] |
| "First tool that tells whether an NFT is on-chain" | **Unsafe** | OpenSea [T1], Onchaininator [T3], NFT Scanner [T4], ClubNFT [T2] |
| "First to test whether on-chain NFTs render without the network" | **Plausibly safe** | Say "we found no prior measurement"; second-pass literature search first |
| "First to show Art Blocks depended on CDN p5.js" | **Unsafe** | Attribute to [T6], [T20]; ours is the *measured extent across collections* |
| "Only X% of NFTs are fully on-chain" | **Unsafe without scope** | State unit, date, definition; compare to 9.06% [T2], 10.63% [A4] with caveats |
| "N% of on-chain claims are false" | **Safe if claims sampling is documented** | Quote claims verbatim with archive links |
| "Expired domains make NFT art hijackable" | **Risk statement is safe; "has happened" is unsafe** | Say "we found no documented NFT art swap via expired domain"; our contribution is measuring registrable hosts |
| "Dead NFTs generated $X" | Only [A1]'s $160.8M for 2021 | Cite it, with its date and scope |

---

## 9. Implications for the other workstreams (flags)

- **census (classifier):** (1) Chain Runners, Blitmap and Art Blocks return `https://` tokenURIs while the art is on-chain, so a tokenURI-scheme classifier undercounts on-chain; plan a second tier that calls known render functions or a curated allow-list (and mark the rest "claimed on-chain, tokenURI http"). (2) Nouns-style heavy renderers revert on free RPCs; retry on a second endpoint with a gas override and record `unknown`, not `broken`. (3) ClubNFT's rule "no match = on-chain" is a trap: empty, garbage and non-URL strings must be `broken`/`other`, not on-chain. (4) Publish the gateway-as-HTTP vs gateway-as-IPFS sensitivity like [T2] did (our number should be reported both ways). (5) Decode `data:application/json` and check the nested `image`/`animation_url`/`external_url` fields; [A4] and [A5] do not.
- **gallery (gallery):** use Art Blocks' `getTokenHtml`/Dependency Registry state as a positive control; expect pre-2024 projects to fetch cdnjs p5.js until the registry/EthFS is used; check `tokenData.externalAssetDependencies` for Flex projects (IPFS/Arweave deps).
- **claims (claims):** Art Blocks docs define "fully on-chain" as allowing "a single dependency housed on a software registry" [T8]; quote the precise definition each project used, because it differs from OpenSea's [T1] and from Chainleft's [T6].
- **Phase 2:** domain-expiry work should use RDAP/DNS observation only; do not register or contact any squattable domain.

---

## 10. Bibliography

Format: `ID. Authors/org, "Title", venue/site, date. URL. Accessed 2026-10-21. Raw: data/raw/prior-art/<key>.<ext>` ("not archived" where a fetch failed or only a search snippet was seen).

### Academic
- **A1.** Dipanjan Das, Priyanka Bose, Nicola Ruaro, Christopher Kruegel, Giovanni Vigna, "Understanding Security Issues in the NFT Ecosystem", Proc. ACM CCS 2022, pp. 667-681, 2022-11-07, doi:10.1145/3548606.3559342. https://arxiv.org/pdf/2111.08893 . Code/data: https://github.com/ucsb-seclab/nft-security-study . Raw: `das_ccs22.pdf`. 
- **A2.** Ziwei Wang, Jiashi Gao, Xuetao Wei, "Do NFTs' Owners Really Possess their Assets? A First Look at the NFT-to-Asset Connection Fragility", WWW '23 (doi:10.1145/3543507.3583281), arXiv:2212.11181, 2022-12-21. https://arxiv.org/pdf/2212.11181 . Raw: `fragility_2212_11181.pdf`. (ACM full-text page returned 403; venue/DOI taken from the ACM URL found by search.)
- **A3.** Leonhard Balduf, Martin Florian, Björn Scheuermann, "Dude, where's my NFT? Distributed Infrastructures for Digital Art", DICG '22 (3rd Int. Workshop on Distributed Infrastructure for the Common Good), pp. 1-6, 2022-11-07, doi:10.1145/3565383.3566106, arXiv:2210.11166. https://arxiv.org/pdf/2210.11166 . Raw: `dude_2210_11166.pdf`.
- **A4.** Sarah Barrington, Nick Merrill, "The 'Fungibility' of Non-Fungible Tokens: A Quantitative Analysis of ERC-721 Metadata", arXiv:2209.14517 (preprint), Sept 2022. https://arxiv.org/pdf/2209.14517 . Raw: `fungibility_2209_14517.pdf`.
- **A5.** Hamza Salem, "Hidden Risks: The Centralization of NFT Metadata and What It Means for the Market", arXiv:2408.13281v1, 2024-08-22. https://arxiv.org/pdf/2408.13281 . Raw: `salem_2408_13281.pdf`.
- **A6.** Ruizhe Shi, Ruizhi Cheng, Bo Han, Yue Cheng, Songqing Chen, "A Closer Look into IPFS: Accessibility, Content, and Performance", Proc. ACM Meas. Anal. Comput. Syst. 8(2), 2024-05-21, doi:10.1145/3656015. https://par.nsf.gov/biblio/10547038/media/xml . Raw: `nsf_10547038.html` (abstract metadata only).
- **A7.** Mandiant (Randi Eitzman), "NFT Storage and Availability: A Risk Worth Considering", Google Cloud Blog, 2022-06-02. https://cloud.google.com/blog/topics/threat-intelligence/nft-storage-and-availability-risk-worth-considering . Raw: `google_mandiant_nft_storage.html`.
- **A8.** Leonhard Balduf, Sebastian Henningsen, Martin Florian, Sebastian Rust, Björn Scheuermann, "Monitoring Data Requests in Decentralized Data Storage Systems: A Case Study of IPFS", ICDCS 2022, doi:10.1109/ICDCS54860.2022.00069, arXiv:2104.09202. https://arxiv.org/abs/2104.09202 . Not archived (search-snippet only).
- **A9.** Sokoto et al., "Guardians of the Galaxy: Content Moderation in the InterPlanetary File System", USENIX Security 2024. https://usenix.org/system/files/usenixsecurity24-sokoto.pdf . Not archived (search-snippet only).
- **A10.** "SoK: On the Security of Non-Fungible Tokens", arXiv:2312.08000, 2023. https://arxiv.org/pdf/2312.08000 . Raw: `sok_nft_security.pdf`.
- **A11.** Minfeng Qi, Qin Wang, Guangsheng Yu, Ruiqiang Li, Victor Zhou, Shiping Chen, "Understanding NFTs from EIP Standards", arXiv:2508.07190, 2025. https://arxiv.org/pdf/2508.07190 . Raw: `understanding_nfts_eip.pdf`.
- **A12.** Lehao Lin, Hong Kang, Xinyao Sun, Wei Cai, "SemNFT: A Semantically Enhanced Decentralized Middleware for Digital Asset Immortality", 2024. https://faculty.washington.edu/weicaics/paper/papers/LehaoLKSC2024.pdf . Raw: `lehao2024.pdf` (design paper; peripheral).
- **A13.** "Software Supply Chain Security of Web3", arXiv:2511.12274, 2025. https://arxiv.org/pdf/2511.12274 . Raw: `arxiv_web3_supplychain.pdf` (DNS hijack of dApp frontends). And the ENS expiration study, IMC 2024. https://www.securitee.org/files/ens_domains_imc2024.pdf . Raw: `ens_imc2024.pdf`. Background for G4 only; neither studies NFT media hosts.
- **A14.** Liu, Hao, Wang et al., "All Your DNS Records Point to Us: Understanding the Security Threats of Dangling DNS Records", CCS 2016. https://www.eecis.udel.edu/~hnw/paper/ccs16a.pdf . Not archived (search-snippet only). Background for G4.

### Tools, platforms, commentary, incidents (T = non-academic)
- **T1.** OpenSea Help Center, "What is the metadata field on NFT pages?", 2026-02-02. https://support.opensea.io/en/articles/13355231-what-is-the-metadata-field-on-nft-pages . Raw: `opensea_metadata_field_help.html`.
  **T1b.** OpenSea Help Center, "How do I use the Stats pages on OpenSea?", 2026-02-02. https://support.opensea.io/en/articles/10549939-how-do-i-use-the-stats-pages-on-opensea . Raw: `opensea_stats_help.html`.
  **T1c.** OpenSea Docs, "Metadata storage". https://docs.opensea.io/docs/metadata-storage . Raw: `opensea_docs_metadata_storage.html`.
- **T2.** Nick Hladek, "How many NFTs are actually on the blockchain?", Right Click Save, 2022-06-20. https://www.rightclicksave.com/article/how-many-nfts-are-actually-on-the-blockchain . Raw: `rcs_how_many_onchain.html`.
- **T3.** Onchaininator docs (test deployment). https://onchaininator-test.149-28-255-65.sslip.io/docs . Not archived (timeouts on 2026-10-21); content known only from a search-engine summary.
- **T4.** NFT Scanner (Indorse), Firefox add-on listing. https://addons.mozilla.org/firefox/addon/nft-scanner/ . Raw: `nftscanner_firefox.html`.
- **T5.** Jason Bailey, "The NFT Apocalypse", Right Click Save, 2022-06-20. https://www.rightclicksave.com/article/the-nft-apocalypse . Raw: `rcs_nft_apocalypse.html`.
- **T6.** William M. Peaster, "What Does 'On-Chain' Really Mean?", Right Click Save, 2023-06-23. https://www.rightclicksave.com/article/what-does-on-chain-really-mean . Raw: `rcs_what_onchain_really_mean.html`. JPG On-Chain Canon: https://www.jpg.space/canons/onchain (HTTP 522, not archived).
- **T7.** Art Blocks Docs, "The Art Blocks Generator". https://docs.artblocks.io/protocol/on-chain-generator.md . Raw: `ab_generator.html`.
- **T8.** Art Blocks Docs, "NFT Metadata Storage at Art Blocks". https://docs.artblocks.io/protocol/on-chain-storage.md . Raw: `ab_onchain_storage.html` (identical duplicate `ab_ondemand_storage.html`). **T8b.** Art Blocks Docs, "Token & Generator APIs". https://docs.artblocks.io/developer/token-and-generator-apis/ . Raw: `ab_token_api.html`.
- **T9.** William M. Peaster, "Understanding Onchain NFTs", Bankless, 2023-10-26. https://www.bankless.com/onchain-nfts . Raw: `bankless_onchain_nfts.html`.
- **T10.** EthFS README (holic/ethfs). https://raw.githubusercontent.com/holic/ethfs/main/README.md . Raw: `ethfs_readme.html`.
- **T11.** scripty.sol v2.1.1 README. https://unpkg.com/scripty.sol@2.1.1/README.md . Raw: `scripty_readme.html`.
- **T12.** Zora Docs, Drop/Edition Metadata Renderer. https://docs.zora.co/contracts/DropMetadataRenderer . Not archived (search-snippet only).
- **T13.** Guy Harrison, "When good NFTs go bad. We sampled almost 500,000 NFTs and...", alwaysNFT on Medium, 2022-05-13. https://medium.com/alwaysnft/when-good-nfts-go-bad-bd4ab48b0a9f (live page 403) ; archived copy https://web.archive.org/web/20221207235558/https://medium.com/alwaysnft/when-good-nfts-go-bad-bd4ab48b0a9f . Raw: `alwaysnft_goodnftsgobad_wayback.html`.
- **T14.** Hedera, "NFT storage: How NFT artwork can literally disappear if you're not careful". https://hedera.com/blog/nft-storage-why-it-matters . Raw: `hedera_nft_storage.html` (undated). dappGambl via The Register, 2023-09-21: https://www.theregister.com/2023/09/21/95_percent_nfts_worthless/ (Raw: `register_95pct.html`) and PetaPixel, 2023-09-20: https://petapixel.com/2023/09/20/95-of-nfts-are-worthless-report/ (Raw: `petapixel_95pct.html`).
- **T15.** Moxie Marlinspike, "My first impressions of web3", 2022-01-07. https://moxie.org/2022/01/07/web3-first-impressions.html . Raw: `moxie_web3.html`.
- **T16.** David Rosenthal, "NFTs and Web Archiving", DSHR's Blog, 2021-04-15. https://blog.dshr.org/2021/04/nfts-and-web-archiving.html . Raw: `dshr_nfts_webarchiving.html`.
- **T17.** Hristina Yordanova, "Why CyberBrokers Paid $250,000 To Make NFTs Completely On-chain", DappRadar, 2022-03-14 (updated 2026-04-08). https://dappradar.com/blog/why-cyberbrokers-paid-250000-to-make-nfts-completely-on-chain . Raw: `dappradar_cyberbrokers.html`.
- **T18.** Michael Hirsch, "How Chain Runners Sparked 300+ Onchain NFT Collections", OpenSea Blog, 2025-07-30. https://opensea.io/blog/articles/how-chain-runners-sparked-300-onchain-nft-collections . Raw: `opensea_chainrunners.html`.
- **T19.** Cointelegraph, "1.2m users flock to NFT Pirate Bay for artwork archive", 2021-11. https://cointelegraph.com/news/1-2m-users-flock-to-nft-pirate-bay-for-artwork-archive . Raw: `cointelegraph_nftbay.html`.
- **T20.** Erick Calderon, "True On-Chain Artwork: A Four-Year Journey", Art Blocks, 2024-11-27. https://artblocks.io/onchain . Raw: `artblocks_onchain_page.html`.
- **T21.** Larva Labs, "Autoglyphs". https://www.larvalabs.com/autoglyphs . Raw: `larvalabs_autoglyphs.html`.
- **T22.** CoinDesk, "The Latest NFT Fad Is a Text-Based Fantasy Game Building Block", 2021-09-01. https://www.coindesk.com/tech/2021/09/01/the-latest-nft-fad-is-a-text-based-fantasy-game-building-block/ . Raw: `coindesk_loot.html`. (Blitmap provenance is from search-snippets only.)
- **T23.** Nouns DAO, `NounsToken.sol`. https://raw.githubusercontent.com/nounsDAO/nouns-monorepo/master/packages/nouns-contracts/contracts/NounsToken.sol . Raw: `nouns_token_sol.html`.
- **T24.** Kenny Lienhard, "The Future of Digital Art Storage, Ethereum or IPFS?", HASH'D, 2026-08-25. https://hashd.art/article/the-future-of-digital-art-storage . Raw: `hashd_storage.html`. Secondary/vendor essay (ETCH'D publisher); used only for Ascribe-loss anecdotes and the Shipyard date, both corroborated or flagged elsewhere.
- **T25.** The Art Newspaper, "Founder of Hic et Nunc pulls the plug...", 2021-11-16. https://theartnewspaper.com/2021/11/16/founder-of-hic-et-nunc-pulls-the-plug-on-the-leading-digital-art-marketplacebut-its-half-a-million-nfts-live-on . Raw: `hen_artnewspaper.html`.
- **T26.** Cointelegraph, "NFTs minted on FTX break, highlighting Web2 hosting flaws", 2022-12-08. https://cointelegraph.com/news/nfts-minted-on-ftx-break-highlighting-web2-hosting-flaws . Raw: `ftx_cointelegraph.html`. **T26b.** Bitcoin.com News, FTX-hosted NFTs point to broken metadata. https://news.bitcoin.com/ftx-hosted-nfts-point-to-broken-metadata-issue-illuminates-flaws-with-nfts-tied-to-centralized-clouds/ . Raw: `bitcoin_ftx.html`.
- **T27.** NFT.Storage, "Decommission Notice" (js-client README). https://github.com/nftstorage/js-client . Raw: `nftstorage_jsclient_readme.html`. Pinata migration guide: https://docs.pinata.cloud/frameworks/migrating-from-nft-storage (Raw: `pinata_migrating_nftstorage.html`).
- **T28.** Hackernoon, "KnownOrigin Will Disappear Soon - Now What?". https://hackernoon.com/knownorigin-will-disappear-soon-now-what . Raw: `hackernoon_knownorigin.html`; Value Added Resource: https://valueaddedresource.net/ebay-knownorigin-winds-down-nft-marketplace . Raw: `vaf_knownorigin.html`.
- **T29.** Cloudflare Blog, "Cloudflare's public IPFS gateways and supporting Interplanetary Shipyard", 2024. https://blog.cloudflare.com/cloudflares-public-ipfs-gateways-and-supporting-interplanetary-shipyard . Raw: `cloudflare_ipfs_gateway.html`.
- **T30.** Logan Hitchcock, "Why RTFKT and Nike's Ethereum NFT Artwork Disappeared", Decrypt, 2025-04-24. https://decrypt.co/316165/why-rtfkt-nike-ethereum-nft-artwork-disappeared . Raw: `clonex_decrypt.html`.
- **T31.** William M. Peaster, "Nifty Gateway's Original Shutdown Plans Threatened Droves of NFTs", Bankless, 2026-01-27. https://www.bankless.com/read/nifty-gateways-shutdown-threatens-nfts . Raw: `bankless_nifty_shutdown.html`.
- **T32.** ZKM, "Platform Shutdown: Foundation". https://extinction.zkm.de/events/foundation-app-shutdown (Raw: `zkm_foundation.html`); The Defiant: https://thedefiant.io/news/nfts-and-web3/foundation-nft-marketplace-shuts-down-permanently-after-failed-sale (Raw: `defiant_foundation.html`); Bankless: https://www.bankless.com/read/the-cryptoart-community-is-salvaging-foundations-art (Raw: `bankless_foundation.html`).
- **T33.** Filebase, "Infura IPFS Is Shutting Down: How to Migrate", 2026-07-29 (relays Infura customer notice). https://filebase.com/blog/infura-ipfs-is-shutting-down-how-to-migrate/ . Raw: `filebase_infura_migrate.html`. The Filecoin Foundation post URL found by search returned 404.
- **T34.** Cointelegraph, "Shipyard winds down IPFS work after Protocol Labs ends funding", 2026-08-25. https://cointelegraph.com/news/shipyard-winds-down-ipfs-protocol-labs-funding . Raw: `cointelegraph_shipyard.html`; Cryptobriefing: https://cryptobriefing.com/shipyard-ipfs-protocol-labs-funding-ends/ (Raw: `cryptobriefing_shipyard.html`); RuntimeWire: https://runtimewire.com/article/ipfs-maintainer-shipyard-winds-down-protocol-labs-funding (Raw: `runtimewire_shipyard.html`). Shipyard's own blog post was not retrieved.
- **T35.** thekillertoaster, KungFungus expired-domain risk note (GitHub gist). https://gist.github.com/thekillertoaster/e167fba641806319ddff09257a33adcc . Raw: `kungfungus_gist.html`.
- Others fetched and archived but not central: `brave_nft_pinning.html` (Brave Wallet NFT pinning), `lighthouse_tokenuri_break.html`, `ethorg_nft_issue_19255.html` (ethereum.org /nft/ page accuracy issue), `ipfs_swgateway_gatos_1212.html` (defunct Gatos collection failing in wallets), `decrypt_are_nfts_safe.html`, `bankless_backup.html`, `ipfs_blog_opensea.html` (OpenSea metadata "freeze" via IPFS/Filecoin, 2021-06-17), `sacra_gen.html`.

### Our own primary observations (2026-10-21)
- `tokenURI_loot.json`, `tokenURI_autoglyphs.json`, `tokenURI_chainrunners.json`, `tokenURI_squiggle_artblocks.json`, `tokenURI_artblocks_v1_flagship.json`, `tokenURI_artblocks_v3_flagship.json`, `tokenURI_blitmap.json`, `tokenURI_bayc.json`: `eth_call tokenURI(id)` at `latest` via `eth.drpc.org`.
- `nouns_ownerOf_100.json`, `nouns_tokenURI_revert_attempts.json`: Nouns reverts.
- `spot_api_artblocks_token_0.json`, `spot_token_artblocks_squiggle0.json`, `spot_api_chainrunners_1.json`, `spot_api_blitmap_1.json`: single no-redirect GETs (Blitmap: 3 attempts, HTTP 500; unknown, not dead).
