# JPEG Unplugged: a 2026 census of where Ethereum NFTs actually live, and what survives when you pull the plug

## Abstract

Only 2.9% of a random sample of Ethereum NFT collections have metadata and all sampled media on-chain, an upper bound for rendering without outside services. In a separate gallery, 71 of 83 tokens draw identically with the network blocked, and a 2.8 MB archive of eight public libraries restores ten of the eleven failures. Of 160 reviewed project-authored storage claimants, 81 have a live pointer-control path held by an EOA or multisig account; storage truth and control are separate measures.

We enumerate Ethereum ERC-721 and ERC-1155 collections with at least 100 holders and sample their metadata and media pointers. The census includes financial position and receipt NFTs, and only the gallery receives a browser rendering test. We distinguish on-chain data behind an off-chain marketplace pointer from a false storage claim, and report liveness and aggregate hosting risks separately. Earlier work measured NFT storage and link rot; our additions are a current census, network-off rendering, and reviewed claims joined to storage evidence and mutation powers. <!-- src: data/analysis/headlines.json:random.onchain; data/gallery/results.csv; data/analysis/claims_summary.json -->

## 1. Introduction

### 1.1 The question

Mint an NFT and the chain records an owner and a number. The image lives in a separate system. The contract holds, at most, a string. That string says where to find the metadata, and the metadata says where to find the image. The chain can prove who owns token 1234; loading the token still depends on the pointer and its destination.

Collectors know this in the abstract. Few know how it plays out across the ecosystem. We ask two questions. **Where do NFTs live?** For each collection, is the metadata on-chain, on IPFS, on Arweave, or on a web server, and is the media in the same place? **What survives?** If the web infrastructure went away, which collections would still show their art, and for the ones that look safe because the art is on-chain, can someone still change it?

The "unplug" in the title is literal in one test. We load on-chain artworks in a browser that blocks every network request and DNS lookup. If the picture still draws, it lives on the chain. If not, something outside the chain was holding it up.

### 1.2 Why now

Many tokens hard-code public IPFS gateway hostnames, and several of those gateways have closed.

* **Cloudflare, 2024.** Cloudflare's public IPFS gateway hostnames stopped connecting to IPFS on 2024-08-14, after a redirect period that began 2024-05-14. Tokens that hard-code `cloudflare-ipfs.com` broke unless someone repointed them. <!-- src: research/prior-art.md:section 6, [T29] --> On 2026-10-21 `cloudflare-ipfs.com` no longer served as a gateway. <!-- src: docs/methods/census.md:section 3 "Dead" -->
* **Infura, 2026.** Infura's IPFS service was reported to end on 2026-08-15 (uploads and pinning off 2026-08-03). We saw only a relay of its notice by Filebase, dated 2026-07-29. <!-- src: research/prior-art.md:section 6, [T33] --> On 2026-10-21 `ipfs.infura.io` and `infura-ipfs.io` reset connections. <!-- src: docs/methods/census.md:section 3 "Dead" -->
* **ipfs.io and dweb.link, announced end of September 2026.** Press reports of 2026-08-24/25 say Interplanetary Shipyard would wind down on 2026-09-30 after Protocol Labs declined to renew its funding, and would stop operating public infrastructure including `ipfs.io` and `dweb.link`. The same reports say Protocol Labs owns the domains and will decide their future, and that IPFS itself is not shutting down. We read these reports, not Shipyard's own post. <!-- src: research/prior-art.md:section 6, [T34] --> On 2026-10-21 `ipfs.io` answered our client with `429` ("This IPFS gateway is switching to a service worker gateway only") and a `Sunset: Mon, 21 Sep 2026` header. <!-- src: docs/methods/census.md:section 3 "Bot-walled" -->

The evidence supports a wind-down announcement for the end of September 2026; on the day we measured, these gateways refused non-browser clients.

Related events: NFT.Storage Classic stopped taking uploads in June 2024, CloneX images went blank in April 2025, Nifty Gateway announced its closure in January 2026, and Foundation shut down in April 2026. <!-- src: research/prior-art.md:section 6, [T27][T30][T31][T32] -->

### 1.3 What we contribute

A 2026 enumeration of 58,617 contracts with deploy dates and a spam flag. A storage census with saved raw evidence for every call and fetch, by deploy year, with intervals. A three-condition rendering test for on-chain art. A join of "on-chain" marketing claims against measured storage and against who holds the keys. An aggregate takeover-risk survey of the hostnames behind off-chain art accompanies the data.

## 2. Prior work and what is new

We searched for prior art on 2026-10-21. The search used the available public sources, without Google Scholar, DBLP or comprehensive forward-citation coverage. "We found no prior measurement" means exactly that. <!-- src: research/prior-art.md:header "Search limits" -->

### 2.1 Measurement studies

* **Das et al. (CCS 2022)**: an OpenSea storage and liveness study using a 2021 snapshot and six-month rechecks. We consulted the saved arXiv version. <!-- src: research/prior-art.md:section 3 [A1] -->
* **Wang, Gao and Wei (WWW 2023)**: 12,353 contracts and 6,234,141 NFTs in 2022; 25.24% of contracts had inaccessible assets; ten centralized platforms hosted 79.04% of off-chain assets. <!-- src: research/prior-art.md:section 3 [A2] -->
* **Balduf, Florian and Scheuermann (DICG 2022)**: hand inspection of 51 contracts of top-selling art; 412 of 786 NFTs on-chain for metadata and asset; 19 of 51 contracts changed their metadata URI at least once. Generative art whose source is on-chain counts as on-chain "since reconstruction is possible", and the runtime environment is left untested. <!-- src: research/prior-art.md:section 3 [A3] -->
* **Barrington and Merrill (2022 preprint)**: one token per contract in 9,292 contracts; 10.63% of tokens were base64 JSON; IPFS treated as permanent. <!-- src: research/prior-art.md:section 3 [A4] -->
* **Hladek / ClubNFT (2022)**: 12,359,778 NFTs through December 2021 by string matching: 9.06% on-chain, 40.70% HTTP, 49.55% IPFS, 0.69% Arweave. Counting gateway URLs as HTTP moves HTTP to 66.44%. <!-- src: research/prior-art.md:section 3 [T2] -->
* **alwaysNFT (2022)**: about 20% bad or expired links in a vendor sample of about half a million NFTs; not reproducible. <!-- src: research/prior-art.md:section 3 [T13] -->

### 2.2 Tools and commentary

OpenSea added a "Metadata" field in 2026 with five labels (Fully onchain, Onchain metadata, Decentralized, Centralized, Unknown). It is "determined programmatically", publishes no counts or method, and labels Art Blocks "Onchain metadata", meaning the media may be external. <!-- src: research/prior-art.md:section 2 row 1, [T1] --> Other checkers we found classify where the pointer goes. None that we found loads the artwork with the network disabled. <!-- src: research/prior-art.md:section 2 take-away -->

Right Click Save raised the p5.js edge case in 2023: on-chain art that loads a JavaScript library from a CDN. <!-- src: research/prior-art.md:section 4 [T6] --> Art Blocks has said the same. Its founder wrote in 2024 that at launch "only the core artwork code was on-chain while artists still relied on off-chain tools and libraries". Its documentation says about 90% of projects can be rebuilt from chain data, and about 10% still reference widely distributed CDN packages. <!-- src: research/prior-art.md:section 5.1 [T7][T20] -->

### 2.3 What is new, and what we do not claim

We do not claim to be the first to measure NFT link rot (Das, Wang and alwaysNFT predate us), the first classification of NFT storage, the first on-chain checker, or the first to notice that Art Blocks used a CDN p5.js. "Most NFTs are off-chain" is not our discovery; it was known by 2021. <!-- src: research/prior-art.md:section 1 "Do NOT claim", section 8 -->

We found no prior measurement of:

* **Rendering with the network off**, which is the gap [A3] names in its own scope.
* **A 2026 census.** The newest datasets with a stated sample are from 2021 and 2022. <!-- src: research/prior-art.md:section 7 G2 -->
* **A split by deploy year.** <!-- src: research/prior-art.md:section 7 G3 -->
* **Registrability of media hosts.** [A2] counts hosting concentration, not whether domains can be re-registered. <!-- src: research/prior-art.md:section 7 G4 -->
* **Marketing claims against measurement, at scale.** <!-- src: research/prior-art.md:section 7 G5 -->
* **Gateway hostnames baked into tokens, measured after the 2024 to 2026 shutdowns.** <!-- src: research/prior-art.md:section 7 G7 -->

Earlier "share on-chain" figures run from 9.06% to 52.4% because population, unit and definition differ, so the figures are not comparable with ours. <!-- src: research/prior-art.md:section 3 cross-study comparison --> We found no documented case of an expired domain bought and used to swap NFT art. The risk is real; the incident, as far as we found, is undocumented. <!-- src: research/prior-art.md:section 6 "Not found" -->

## 3. Data and method

All dates are 2026-10-21 unless stated. Code is in `scripts/`. Raw evidence (RPC responses, HTTP fetches, contract source) is saved with URL, method, status, retrieval time and SHA-256, and indexed in `data/raw/MANIFEST.jsonl`. Its size keeps it outside the commit.

### 3.1 Universe

We enumerated Ethereum mainnet ERC-721 and ERC-1155 contracts with at least 100 holders from the Blockscout token list, sorted by holder count, using 24 parallel cursor segments per standard with overlap at the seams. Deploy date, creator and factory came from Etherscan `getcontractcreation`. <!-- src: docs/methods/universe.md:Method and timing -->

| | Contracts | Not flagged as spam |
|---|---|---|
| ERC-721 | 42,430 | 41,287 |
| ERC-1155 | 16,187 | 8,207 |
| Total | 58,617 | 49,494 |

<!-- src: docs/methods/universe.md:Counts -->

47,300 contracts have 100 to 999 holders, 10,913 have 1,000 to 9,999, and 404 have 10,000 or more. 33,979 were deployed in 2022 (27,324 of them not flagged as spam, 55% of all non-spam rows): the profile-picture launch year plus its long tail of dead small projects. <!-- src: docs/methods/universe.md:Counts, Surprising -->

**Spam flag.** 9,123 rows (15.6%) are flagged `spam_suspect`: 7,980 ERC-1155 (49.3%) and 1,143 ERC-721 (2.7%). Signals include a URL or spam words in the name, templated "Mint Pass" names, imitations of "Uniswap V3 Positions", and, for ERC-1155, forty or more contracts with an identical holder count. The flag is a heuristic lower bound on junk. We never drop flagged rows. 30 further rows are flagged as infrastructure from an explicit list (ENS, Uniswap position managers, POAP and others). <!-- src: docs/methods/universe.md:Flags -->

**Deploy year as a mint-year proxy.** A collection can mint years after it deploys, and a proxy upgrade is invisible in the creation record. We use deploy year as a proxy for mint year and say so wherever we report a by-year number. <!-- src: docs/methods/universe.md:Deploy info -->

### 3.2 Census

**Sampling.** The census runs in a fixed order: a uniform random sample of 3,000 collections from the 49,494 non-spam collections (seed 20261021); then every other non-spam collection by holder count; then a random 500 of the 9,123 spam-flagged collections. <!-- src: data/census/sample_random.json; data/census/sample_spam.json; scripts/census/census.py:plan_universe --> Percentages with intervals come from the random stratum. The random stratum is complete (3,000 of 3,000). The top-by-holders stratum is partial: 11,186 collections had been analysed when the headlines were computed (headlines generated 2026-10-22 04:36:59 UTC; last census result 02:21:24 UTC), out of 46,494 remaining non-spam collections (derived). Only 5 of the 500 spam-sample collections were finished, so we report no spam result. <!-- src: data/analysis/headlines.json:meta.census_rows_by_stratum; data/analysis/headlines.json:meta.generated_at --> Within a collection we sample three tokens (low, middle, recent id) if it has at least 1,000 holders and two otherwise. If every sampled id reverts, the collection is `broken`. <!-- src: docs/methods/census.md:section 1 -->

**Reading the chain.** We call `tokenURI` (ERC-721) or `uri` (ERC-1155) with `eth_call` on two public RPCs, with retries and the other selector as fallback, and save the raw JSON-RPC response. Public RPCs cap `eth_call` gas, so heavy on-chain renderers appear to revert. Every revert is retried on two higher-cap nodes; if one returns a URI, the token is flagged `revert_gas_cap_suspected` and counted separately. <!-- src: docs/methods/census.md:section 1 step 2 --> In the saved Nouns `tokenURI(1500)` test, six public RPCs answered: three refused even at 150M gas, one needed that manual gas limit, and two served it by default. Six other endpoints required keys or returned infrastructure errors. <!-- src: launch/cards/rpc_check_nouns_2026-10-21.json --> On a local fork, `eth_estimateGas` reports 119,289,149 gas for Nouns and 110,003,480 for Lil Nouns. <!-- src: docs/methods/gallery.md:Method -->

**Classification.** We classify the metadata location, then the location of `image`, `image_data` and `animation_url`, with one classifier: `data-uri`, `onchain-renderer`, `ipfs`, `arweave`, `http`, `other`, `broken` (Appendix A). A `data:` JSON whose image is an `https://` URL has off-chain media. A collection is an **on-chain candidate** when metadata and every sampled media field are on-chain, and "truly on-chain" only if it also renders with the network off. The census runs no browser, so it produces candidates. <!-- src: docs/methods/census.md:section 2 -->

**Liveness.** Each fetch is alive, dead (with a reason) or unknown. Dead needs a negative answer in two passes, the second at least 25 minutes later with 40 second timeouts. Timeouts, 429s, temporary DNS failures and bot walls are unknown. An IPFS or Arweave target is alive if any working gateway serves it, and dead only if at least two distinct working gateways answered negatively after pass 2. Token and collection roll-ups are in Appendix A. <!-- src: docs/methods/census.md:section 2 "Liveness verdicts" -->

We keep **two liveness columns**. `liveness` asks whether the content can be fetched through any working gateway. `liveness_exact` judges the URL exactly as written, so a URL on a dead gateway is dead even if the CID is retrievable elsewhere. ClubNFT showed that results swing with how a gateway URL is counted, so we report both. <!-- src: docs/methods/census.md:section 2; research/prior-art.md:section 3 [T2] -->

**Gateways on the day.** A canary request on 2026-10-21 found working IPFS gateways (Filebase, Rarible's, Blockfrost, Hypha, 4everland and others) and Arweave gateways (`arweave.net`, `turbo-gateway.com`, `ardrive.net`, `ar-io.dev`). It found `ipfs.io`, `dweb.link`, `gateway.ipfs.io`, `w3s.link` and `nftstorage.link` bot-walled to non-browser clients, and `cloudflare-ipfs.com`, `ipfs.infura.io`, `infura-ipfs.io` and several other IPFS and Arweave gateway hostnames dead. <!-- src: docs/methods/census.md:section 3; data/census/gateways.json --> About half of first-pass IPFS attempts on working gateways time out, so `gateway-not-found` means "not retrievable through public gateways within 15 s (pass 1) or 40 s (pass 2)", not "provably gone from IPFS". <!-- src: docs/methods/census.md:section 3 caveat -->

**Audit.** We re-classified the stored `tokenURI` results of 6,462 random-stratum tokens with an independent implementation. It differed from the census on 32 (0.5%), mostly malformed-CID `ipfs://` strings that the census called broken (19). Data-URI re-decoding matched every time, and no liveness verdict contradicted its saved evidence. <!-- src: data/analysis/audit_summary.json -->

**Politeness.** At most 2.5 requests per second per public gateway and 3 per second for other hosts. At most 64 KB of any media file is downloaded, and non-public IP addresses are refused, including after DNS resolution and on redirects. <!-- src: docs/methods/census.md:section 4 -->

### 3.3 Claims

We manually reviewed every saved candidate quote for 283 collections, covering 518 quote rows. We accepted 265 project-authored art/metadata storage statements across 160 collections; 123 candidate collections had no accepted statement. Dependency-library comments, negated statements, unrelated uses of “on-chain” and directory-only descriptions were excluded. Of the accepted claimants, 103 explicitly say “100%”, “fully”, “entirely” or “completely” on-chain. The selected strongest statement is scored for its stated scope. <!-- src: data/analysis/claims_summary.json:metrics; data/claims/claims_reviewed.csv; docs/methods/claims.md -->

We use four storage outcomes: `holds`, `onchain-data-offchain-pointer`, `contradicted`, and `unverifiable`. Only `contradicted` means a failed claim. A live setter establishes control, not that an on-chain storage statement is false. All claimant and mutation figures below use the reviewed definitions in `data/analysis/claims_summary.json` and the evidence limits in `docs/methods/mutability.md`.

### 3.4 Rendering gallery

We rendered 83 tokens from 63 contracts: 23 Art Blocks projects on three core contracts and 60 others. The set is a candidate list found by probing the top 3,500 non-spam ERC-721 and top 800 ERC-1155 collections (256 and 20 data-URI hits) plus known projects, not a random sample. <!-- src: docs/methods/gallery.md:Headline numbers, Limitations -->

The chain-only document is built from `tokenURI` for data-URI collections. Where `tokenURI` is an HTTP URL but the art is on-chain, we call the on-chain function (for example `CryptopunksData.punkImageSvg`, Blitmap `tokenSvgDataOf`, Terraforms `tokenHTML`). For Art Blocks we call the on-chain Generator `getTokenHtml` and use its output unchanged, after checking for all 23 projects that the project script read from the core contract appears verbatim inside it. <!-- src: docs/methods/gallery.md:Method -->

Chromium, driven by Playwright, loads the document from a synthetic origin and logs every request. **A** lets requests through. **B** aborts every non-document request, black-holes DNS and disables service workers. **C** is B plus a local archive of declared dependencies. A second run of A measures the artwork's own animation noise. A token is `identical` if its pixel difference from A is within the larger of 1% or 1.5 times that noise, and `broken` if blank where A has ink or under 25% of A's ink. Eight items with external requests were also checked by eye, and one automatic "degraded" (Art Blocks #76) was re-labelled broken because the metric under-reports it. <!-- src: docs/methods/gallery.md:Method -->

The dependency archive holds every library (script, stylesheet, font) that a normal run requested, plus any URL that appears as a literal in the on-chain document: 10 URLs, 8 archived, 2.8 MB. The archive excludes `api.ipify.org`, whose answer depends on the viewer, and an A-Frame default VR controller model that is invisible in a flat view. <!-- src: docs/methods/gallery.md:Dependency archive; data/dep-archive/MANIFEST.json -->

### 3.5 Mutability

For 606 contracts that are on-chain by census, gallery or claim (283 claimants, 63 gallery, 388 census on-chain, with overlaps), we ask who can still change what a token shows. From verified ABI and source we find setters for URIs, renderers and upgrades, parse their access gates, identify each gate's holder by on-chain probes (Safe, timelock, governor, renounced, plain account), read freeze flags and proxy slots, analyze renderer dependencies one level deep, and decode setter transactions from explorer history. <!-- src: docs/methods/mutability.md:Method --> Classes are `immutable`, `dao-or-timelock-mutable`, `multisig-mutable`, `eoa-mutable` (one externally owned account can change it) and `unknown`; the class is the worst of the contract and its in-path dependencies. Live URI, renderer or upgrade control by one EOA or multisig counts as *repointing power*. It is reported separately from the storage outcome (§3.3); data-only setters are excluded. <!-- src: docs/methods/mutability.md:Method -->

### 3.6 Hosts and statistics

We extract the hostnames behind off-chain metadata and media and check which registrable domains have lapsed, using DNS and RDAP only. The checks stay read-only: we register no domain, contact no owner, and fetch only from hosts with DNS answers. Proportions use Wilson 95% intervals; weighted views use a percentile bootstrap (2,000 resamples). Collection-weighted shares ignore the finite-population correction (the sample is 6% of the stratum), which is conservative. <!-- src: data/analysis/headlines.json:meta.estimator -->

## 4. Results

### 4.1 Where the metadata and the media live

Percentages are for the random stratum: 3,000 collections drawn uniformly from 49,494 non-spam collections (seed 20261021). Intervals are 95% Wilson. Unit = collection. <!-- src: data/analysis/headlines.json:meta; data/analysis/headlines.json:random -->

| Metadata location | Collections | Share (95% CI) |
|---|---|---|
| On-chain (data URI or on-chain renderer) | 152 / 3,000 | 5.1% (4.3 to 5.9) |
| IPFS | 1,656 / 3,000 | 55.2% (53.4 to 57.0) |
| Arweave | 183 / 3,000 | 6.1% (5.3 to 7.0) |
| HTTP(S) | 869 / 3,000 | 29.0% (27.4 to 30.6) |
| Broken or no answer | 140 / 3,000 | 4.7% (4.0 to 5.5) |

<!-- src: data/analysis/headlines.json:random.metadata_location -->

Broken means no usable URI: the call reverted on every node, or the string did not decode. 53 collections (1.8%; 1.4 to 2.3) return different metadata classes for different sampled tokens. <!-- src: data/analysis/headlines.json:random.onchain.metadata_mixed_across_tokens --> We treat the split between plain data URIs and on-chain renderers as a method detail because it rests on best-effort bytecode and gas rules (Appendix A). Where the media location could be determined, 70.9% of collections keep the image on IPFS, 15.1% on HTTP, 8.9% on Arweave and 4.3% on-chain. For 828 collections (27.6% of 3,000) it is unresolved, because their off-chain metadata could not be fetched. <!-- src: data/analysis/headlines.json:random.media_location_resolved; data/analysis/headlines.json:random.media_location_all.unresolved -->

**On-chain JSON, off-chain media.** Of 152 collections with on-chain metadata, 63 (41.4%; CI 33.9 to 49.4) have at least one sampled media field off-chain: 60 through `image` (41 IPFS, four Arweave and 15 HTTP) and three only through `animation_url`. The remaining 89 comprise 87 fully on-chain candidates and two mixed-metadata collections. CyberBrokers and Checks VV Edition return inline JSON with an IPFS image pointer; CyberBrokers also has a separate on-chain art-data route, so this observation alone does not refute its storage claim. <!-- src: data/analysis/headlines.json:random.onchain.fake_onchain_A_offchain_media_of_onchain_metadata; data/analysis/headlines.json:random.onchain.onchain_metadata_media_split; docs/methods/mutability.md -->

**Metadata and sampled media on-chain: candidates.** 87 of 3,000 collections (2.9%; CI 2.4 to 3.6) have metadata and all sampled media on-chain. By standard, 85 of 2,498 ERC-721 collections (3.4%) and 2 of 502 ERC-1155 collections (0.4%). A static scan of their on-chain SVG or HTML finds no external loading reference in any of them. <!-- src: data/analysis/headlines.json:random.onchain.truly_onchain_census; data/analysis/headlines.json:random.by_standard; data/analysis/headlines.json:random.onchain.fake_onchain_B_of_onchain_metadata --> A static scan misses requests that a script builds at run time, which is why the rendering test in Section 4.4 matters. The census flag does not execute JavaScript art, so for HTML and JavaScript pieces "renders unplugged" is confirmed only for collections that are also in the gallery; read 87 as an upper bound for rendering. <!-- src: docs/methods/analysis.md:section 8 --> We call these "candidates" until they pass it. This measure includes financial position and receipt NFTs such as Sablier Lockup and Nexus Mutual Cover; it is not an art-only rate. The infrastructure flag is not an art filter. Among the 2,985 random-stratum collections without an accepted reviewed storage claim, 76 (2.55%; CI 2.0 to 3.2) are candidates too. <!-- src: data/analysis/claims_summary.json:funnel.baseline_random_nonclaimants_truly_onchain -->

**Weighting changes the answer.** Weighted by holder count (a wallet in k collections counts k times), 7.3% (CI 4.7 to 11.2) have on-chain metadata, 3.9% (2.6 to 5.4) are on-chain candidates, and 23.5% (20.0 to 27.0) are dead. Weighted by total supply (2,243 ERC-721 collections with plausible supply), 4.5% (2.9 to 6.4) are on-chain candidates and 22.8% (CI 20.1 to 25.8) are dead. A few large collections dominate the supply weights. <!-- src: data/analysis/headlines.json:random.weighted --> We report both and make no single "share of NFTs" claim.


### 4.2 What loads today

Liveness is a verdict per fetch, rolled up per collection. Timeouts and bot walls stay unknown.

| Collection liveness (random stratum) | Collections | Share (95% CI) |
|---|---|---|
| Alive | 1,830 / 3,000 | 61.0% (59.2 to 62.7) |
| Degraded (metadata loads, image dead) | 180 / 3,000 | 6.0% (5.2 to 6.9) |
| Metadata unavailable (legacy `dead`, including reverts) | 908 / 3,000 | 30.3% (28.6 to 31.9) |
| Unknown | 82 / 3,000 | 2.7% (2.2 to 3.4) |

<!-- src: data/analysis/headlines.json:random.liveness.all -->

Dead plus degraded is 1,088 (36.3%; 34.6 to 38.0). Of the 2,918 collections we could judge, 31.1% are dead and 37.3% are dead or degraded. <!-- src: data/analysis/headlines.json:random.liveness.unknown_excluded -->

"Unknown" is the price of refusing to call a timeout dead. Its main causes are HTTP 5xx (42), timeouts (20) and temporary DNS failures (1). <!-- src: data/analysis/headlines.json:random.dead_reasons.unknown_why --> We therefore state a range. The legacy metadata-unavailable share is between 30.3% (unknown counted alive) and 33.0% (unknown counted dead; CI 31.3 to 34.7). Dead or degraded is between 36.3% and 39.0%. Alive is between 61.0% and 63.7%. <!-- src: data/analysis/headlines.json:random.liveness.bounds_dead; data/analysis/headlines.json:random.liveness.bounds_dead_or_degraded; data/analysis/headlines.json:random.liveness.bounds_alive -->

**Why they fail.** Among the 1,088 dead or degraded collections, the dominant reasons are: DNS failure 38.7% (421), IPFS content not found through the gateways 31.1% (338), HTTP 4xx 10.2% (111), `tokenURI` reverted on every node 8.0% (87), TLS errors 2.7% (29), then undecodable `tokenURI`, non-JSON bodies, connection errors, 5xx, Arweave not found (6) and parked domains (3). <!-- src: data/analysis/headlines.json:random.dead_reasons.dead_or_degraded_share_of_failures --> **Strength of evidence.** The legacy 908 metadata-unavailable collections split into 627 (20.9%) with direct negative evidence such as DNS, TLS, HTTP or malformed-URI failures; 80 (2.7%) with `tokenURI` reverts; and 201 (6.7%) with only content not found through public gateways, mostly gateway 504s. The 627 is derived by subtracting the 80 revert rows from the old 707 “hard evidence” count. Reverts can reflect unminted, unrevealed, paused or burned tokens, or a renderer beyond a provider's gas cap; they establish read failure rather than lost content. Excluding reverts, the unavailable share is 27.6%. These are snapshot observations, not proof of permanent loss. A further 279 collections (9.3%) have retrievable content but are unknown under the exact-URL view because their gateway bot-walls our client. <!-- src: data/analysis/headlines.json:random.dead_reasons; random.exact_url.content_alive_exact_unknown_botwalled -->

**Gateway sensitivity.** 591 of 3,000 collections (19.7%; 18.3 to 21.2) hard-code at least one HTTP gateway rather than using `ipfs://` or `ar://`: `arweave.net` (176), `ipfs.io` (147), `gateway.pinata.cloud` (99), `nftstorage.link` (39), `dweb.link` (7). The legacy “dead gateway” aggregate contains 14 collections across four hosts. Six use Lighthouse, whose canary returned HTTP 402 Payment Required: it refused our client and is paywalled, not dead. The other eight use the three Cloudflare/Infura hostnames that no longer served as public gateways. The saved per-host collection counts are 6, 3, 3 and 2 respectively. The Lighthouse roll-up has inconsistent exact-status counters, so it cannot establish how many exact token URLs failed; we do not reuse its “content alive, exact dead” count. <!-- src: data/census/gateways.json; data/analysis/headlines.json:random.exact_url.dead_gateway_hosts_collections --> <!-- src: data/analysis/headlines.json:random.exact_url --> Under the exact-URL view, 51.3% of collections are alive (61.0% by content), 29.7% dead and 13.9% unknown. Unknowns rise because 279 collections (9.3%) hard-code a gateway that bot-walls our client, mainly `ipfs.io` (142 of its 147). <!-- src: data/analysis/headlines.json:random.exact_url.liveness_exact; data/analysis/headlines.json:random.exact_url.by_gateway_host -->


### 4.3 By deploy year

Deploy year is a proxy for mint year. The table covers the random stratum, which spans every year. Counts before 2021 are small, so those rows are pooled and their intervals are wide.

| Deploy year | n | Metadata on-chain % | On-chain candidate % (95% CI) | IPFS % | Arweave % | HTTP % | Broken % | Dead % | Dead or degraded % | Unknown % |
|---|---|---|---|---|---|---|---|---|---|---|
| up to 2020 | 37 | 0.0 | 0.0 (0.0 to 9.4) | 21.6 | 2.7 | 54.1 | 21.6 | 56.8 | 59.5 | 5.4 |
| 2021 | 290 | 7.2 | 5.2 (3.2 to 8.4) | 44.1 | 2.1 | 43.4 | 3.1 | 34.5 | 40.0 | 2.8 |
| 2022 | 1,634 | 2.7 | 1.5 (1.0 to 2.2) | 56.0 | 5.2 | 31.6 | 4.5 | 37.6 | 44.0 | 3.0 |
| 2023 | 648 | 6.5 | 2.5 (1.5 to 4.0) | 55.4 | 12.0 | 23.9 | 2.2 | 15.4 | 22.5 | 2.6 |
| 2024 | 77 | 7.8 | 3.9 (1.3 to 10.8) | 58.4 | 6.5 | 26.0 | 1.3 | 23.4 | 29.9 | 2.6 |
| 2025 | 78 | 14.1 | 2.6 (0.7 to 8.9) | 61.5 | 2.6 | 17.9 | 3.8 | 9.0 | 12.8 | 2.6 |
| 2026 | 236 | 11.9 | 11.0 (7.6 to 15.7) | 64.8 | 2.5 | 7.2 | 13.6 | 19.9 | 22.0 | 0.8 |

<!-- src: data/analysis/headlines.json:random.by_year -->

Collections deployed up to 2022 have the highest dead-or-degraded shares: 59.5% up to 2020, 40.0% in 2021 and 44.0% in 2022, against 22.5% in 2023. The 2026 anomaly has a concrete classification cause: all 32 random-stratum rows with broken metadata are `tokenURI` reverts. The current fallback flag does not distinguish gas-cap failures from unminted or unrevealed tokens, so this row cannot support an inference of unusually rapid content loss. A high-gas fork and mint-state review of those rows remains necessary to distinguish the causes. The on-chain candidate rate also includes position/receipt NFTs, making the 2026 row unsuitable as evidence of an art-preservation trend. Deploy year remains a proxy for mint year. <!-- src: data/analysis/headlines.json:random.by_year -->


### 4.4 Rendering with the network off

We rendered 83 tokens from 63 contracts under the three conditions.

| Condition | Identical to normal | Broken | Excluded (blank by design) |
|---|---|---|---|
| B: network blocked | 71 | 11 | 1 |
| C: blocked, plus archive of declared dependencies | 81 | 1 | 1 |

<!-- src: docs/methods/gallery.md:Headline numbers; data/gallery/results.csv:verdict_B,verdict_C,manual_verdict_B (auto verdicts 71 identical / 10 broken / 1 degraded / 1 a-blank; the one degraded, ab-76, was reviewed and re-labelled broken) -->

71 of 83 (86%) draw identically with the network blocked. These counts apply to a candidate set, not to all NFTs, and 23 of the 83 tokens are Art Blocks projects.

**Most on-chain art makes no requests.** 58 of the 60 non-Art-Blocks tokens made no external request (48 SVG, ASCII or bitmap tokens and 10 self-contained HTML and JavaScript pieces), so for them B equals A by construction. Only 12 of 83 tokens made any external request in the normal condition (14 requests in total), and all 12 are JavaScript artworks: 10 Art Blocks, ChillOrbs and Generative Exploration. <!-- src: docs/methods/gallery.md:Headline numbers -->

**The 11 that break.** Nine Art Blocks projects (Genesis #1, Construction Token #2, Light Beams #32, dino pals #76, Beatboxes #145, Seadragons #160, spawn #161, Dipolar #385, Art Blocks project #391), plus ChillOrbs and Generative Exploration. All show a blank canvas or a missing subject. Nine of the 11 also throw a page error such as `createREGL`, `Zdog`, `AFRAME` or `paper is not defined`. **Genesis and Construction Token fail silently**: processing.js never runs, nothing is thrown, and the canvas is just blank. <!-- src: docs/methods/gallery.md:Headline numbers -->

**An archive cures ten of them.** The archive of eight public files (regl, processing.js, paper.js, A-Frame, p5.js, seedrandom, zdog, twemoji; 2.8 MB) restores 10 of the 11 to within the animation noise floor. The libraries are standard, versioned and hashed, which is why "declared dependencies" is the right preservation target. <!-- src: docs/methods/gallery.md:Headline numbers, What B vs C tells us -->

**The one that cannot be cured.** Generative Exploration (Reflections), an ERC-1155 token, calls `fetch("https://api.ipify.org?format=json")` and colours a canvas from the viewer's IP address. It is blank unplugged. No archive helps, because the input is runtime content and differs for each viewer. This is a different kind of dependency from a library. <!-- src: docs/methods/gallery.md:Per-collection findings -->

**Art Blocks, surveyed.** We called the on-chain Generator for all 494 project ids. 474 produced HTML and 20 did not. Of the 474, 16 (3.4%) reference a library on a public CDN: regl on cdnjs (9 projects), processing.js (2), paper.js (2), zdog, A-Frame and twemoji (1 each). 362 embed a gzip data-URI library and are self-contained. The Art Blocks documentation estimates about 10% of projects cannot be reconstructed entirely from chain data. Our 3.4% counts literal public-CDN library URLs in generated HTML for one token per project; 20 projects could not be read. These are different measurements. <!-- src: docs/methods/gallery.md:Art Blocks generator survey -->

**Caveats.** Art Blocks' Dependency Registry took its first p5.js upload in January 2024; before that, the same call produced a cdnjs script tag. Our test describes the chain today. <!-- src: docs/methods/gallery.md:Method; research/prior-art.md:section 5.1 [T8] --> "Identical" can still hide a dependency: Dopamine Machines #0 blocked twemoji but rendered identically because that token's text has no emoji. <!-- src: docs/methods/gallery.md:What B vs C tells us -->

### 4.5 The pointer and the art are separate

A tokenURI-only classifier misreads some of the most famous on-chain projects, in both directions. The art is on-chain, but `tokenURI` returns an HTTP URL:

* **Chain Runners.** `tokenURI(1)` is `https://api.chainrunners.xyz/tokens/metadata/1?dna=...`. An on-chain renderer exists.
* **Blitmap.** `tokenURI` is `https://api.blitmap.com/v1/metadata/{id}`, which returned HTTP 500 on 2026-10-21 (two ids, two tries). The 16x16 art is on-chain via `tokenSvgDataOf`.
* **ChainFaces.** `tokenURI` is an Azure web app named for the Rinkeby testnet, still answering 200. `getFace()` draws the face on-chain.
* **Avastars, Terraforms, Every Icon, Art Blocks.** HTTP pointers (in `tokenURI` or `animation_url`) over on-chain art.

<!-- src: docs/methods/gallery.md:Where "on-chain" reputation and reality diverge -->

For these, a census that classifies by `tokenURI` scheme counts the collection as HTTP. We keep that classification, because it is what a marketplace following `tokenURI` sees, and add that the art can still be read from the chain. One Blitmap HTTP 500 is unknown, not dead. The reverse also happens: the local fork estimates 110 to 119 million gas for Lil Nouns and Nouns. In the saved Nouns test, six public RPCs answered: three refused even with 150M gas, one served it only with gas set manually, and two served it by default. Availability depends on the provider. <!-- src: launch/cards/rpc_check_nouns_2026-10-21.json --> <!-- src: docs/methods/gallery.md:Method -->

### 4.6 On-chain storage can still be mutable

The historical mutation audit covers 606 contracts discovered as on-chain candidates or possible claimants; this is a discovery set, not 606 accepted claims:

| Class (worst of the contract and the renderers it depends on) | Contracts | Share (derived) |
|---|---|---|
| eoa-mutable | 323 | 53.3% |
| immutable | 203 | 33.5% |
| unknown | 49 | 8.1% |
| multisig-mutable | 25 | 4.1% |
| dao-or-timelock-mutable | 6 | 1.0% |

<!-- src: docs/methods/mutability.md:Results; data/mutability/mutability.csv:class_final -->

These 606 contracts form a discovery set, not a sample, so the class shares describe that set. “Unknown” leaves control unresolved; dependency coverage and source parsing remain heuristic. <!-- src: docs/methods/mutability.md:Caveats -->

Under the reviewed definition, a live effective URI setter, renderer/descriptor swap or upgrade on the ordinary metadata/art path is repointing power. It is EOA-controlled for 302 contracts and multisig-controlled for 23. Data-only edits are excluded. The broader 323 EOA-mutable class includes 21 without EOA pointer power and must not be called repointable. <!-- src: docs/methods/mutability.md:Headlines -->

These figures retain the historical mutation-audit population for comparability. The reviewed update reuses its saved control-state observations with additional reads for the named cases; it is not a new full audit of every contract. The scope of any edit matters: data-only edits, pointer swaps, upgrades and token-holder selection have different effects. <!-- src: docs/methods/mutability.md -->

### 4.7 Claims against measurement

The 160 reviewed claimants have four storage outcomes: **131 holds, 11 on-chain-data/off-chain-pointer, zero contradicted and 18 unverifiable**. “Holds” supports the selected statement's scope from sampled evidence; it does not establish collection-wide coverage, immutability or browser rendering. The data/pointer category supports stored art or code despite an external marketplace route. “Contradicted” required affirmative evidence; in two explicit or near-explicit cases (Killer GF and Fluffy Polar Bears) the sampled image is off-chain and no alternate data contract was found, so they are counted unverifiable. Zero demonstrated contradictions does not mean every claim checked out. <!-- src: data/analysis/claims_summary.json:metrics; docs/methods/claims.md -->

**Control is a separate axis.** 81 of 160 (50.6%) can be repointed by one EOA or multisig account: 75 EOA and six multisig. In the 103 explicit claimants, 53 (51.5%) have that power: 51 EOA and two multisig. A multisig account may require several signatures. Six further claimants have data-only mutation paths, five in the explicit subset; these are excluded from repointing counts. <!-- src: data/analysis/claims_summary.json:metrics -->

**Ordinary-pointer funnel.** Of 105 reviewed claimants with census rows, 91 have on-chain metadata, 81 of these 105 also have sampled media on-chain, and 41 of those are classed immutable. Only 22 of the 81 candidates were gallery-render-tested. The other 55 claimants are outside the census funnel and use additional saved reads where available. An off-chain pointer is an exclusion from this funnel, not a failed storage claim. The random subset contains 15 reviewed claimants: 13 have on-chain metadata, 11 sampled media on-chain, and five are classed immutable. Those small, discovery-dependent counts provide no estimate of the prevalence or truth of claims across all NFTs. <!-- src: data/analysis/claims_summary.json:funnel -->


### 4.8 Who hosts the off-chain art

We extracted 3,621 distinct HTTP(S) hosts from the sampled token metadata and media URLs, then ran read-only DNS, RDAP and HTTP checks. The results pool the random, top-holder and spam-random strata; collection counts overlap when a collection uses several hosts. Nothing was registered, claimed or written. <!-- src: docs/methods/hosts.md:Method and Results; data/hosts/hosts.csv -->

**Cloud resources.** The saved table flags 204 cloud resources across 232 distinct collections. The platform counts are AWS S3 109, Heroku 58, Vercel 12, DigitalOcean Spaces 12, Azure 7, Elastic Beanstalk 2, GitHub Pages 2, Firebase 1 and Netlify 1. Of these, 195 have a provider response such as a missing-bucket or missing-app fingerprint; 9 rely on DNS evidence alone. The saved table retains two GitHub Pages candidates despite the methods note recording an account-check downgrade, so their reclaimability remains unresolved. These counts describe candidates requiring provider-specific verification. <!-- src: data/hosts/hosts.csv:verdict, platform, cloud_fingerprint; docs/methods/hosts.md:Method and Results; docs/methods/hosts.md:distinct dependent collections -->

**Registry evidence.** Registries returned RDAP 404 for 309 hosts' registrable domains, strong evidence that the registry had no registration record at check time. A further 270 hosts had only an NS lookup returning NXDOMAIN without an RDAP result. The latter signal is weaker because lookup coverage and registry policy can produce the same observation. Counts here are hosts, so several can share a registrable domain. Premium, reserved or pending-delete names may still be unavailable for purchase. <!-- src: data/hosts/hosts.csv:available_evidence; docs/methods/hosts.md:Results, domain-likely-available -->

**Registration-date candidates.** For 58 hosts, the RDAP registration year followed the earliest deployment year of a dependent collection, and the host was not serving the expected content. A legitimate URI change can produce this sequence; establishing a change of hands requires further evidence. <!-- src: data/hosts/hosts.csv:verdict; docs/methods/hosts.md:Results, rereg-after-deploy -->

All checks were read-only. Nothing was registered or claimed. Provider responses and registry records establish stronger evidence of missing resources than DNS-only observations, while actual reclaimability remains untested. Hostnames and collection-to-candidate mappings are withheld. <!-- src: docs/methods/hosts.md:Method and Caveats -->

### 4.9 The top 100 collections by all-time sales

CryptoSlam’s wash-filtered all-time Ethereum ranking supplies a separate panel of 100 collections, normalized by reported contract identity with duplicate aliases removed. The ranking uses historical USD; it is source-specific and does not replace the random-stratum estimates. Three token units per collection, 306 overall across source-listed contracts, were checked. 888 Inner Circle has two distinct IDs and a second fungible unit of ID 888, so its three units are only two metadata paths. <!-- src: docs/methods/top100.md:Ranking and independent cross-check; data/top100/top100.csv; data/top100/tokens.json -->

Six collections route metadata and every sampled declared media field fully on-chain, including CryptoPunks’ separately sealed legacy data renderer. Thirteen have dead or degraded metadata/primary-image delivery; four remain unknown. Fifty-two have live one-key repointing power, distinct from the broader 53 EOA-mutable paths that include artwork-data edits. Forty-nine depend on ordinary HTTP servers for metadata or media, and 49 use IPFS; these dependencies overlap. These are sampled delivery-route findings, not collection-wide permanence or offline-rendering guarantees. <!-- src: data/top100/summary.json:counts; data/top100/top100.csv; docs/methods/top100.md:Census, liveness and control method -->

CryptoPunks (#2) and Autoglyphs (#69) pass the on-chain route test; BAYC (#1) uses IPFS for metadata and images. NFT Worlds (#30) has repeated sampled metadata DNS failures. Mooncats (#68) is the ranked Wrapped MoonCatsRescue contract: owned IDs 4, 8 and 9 return empty strings from successful `tokenURI` calls, so its wrapper metadata is broken; this does not establish death of the legacy artwork. Art Gobblers (#94) is degraded, not dead: owned IDs 1 and 5000 load, while ID 10000 returns HTTP 404 in both passes. Short-window delivery failures do not prove permanent content loss. Public receipts redact withheld origins and retain sample results and saved-packet hashes. <!-- src: data/top100/top100.csv; data/top100/tokens.json; site/data/top100-evidence/; docs/methods/top100.md:Presentation review -->

## 5. Case studies

These cases illustrate the categories above; they provide no ranking or accusation. Quoted claims are verbatim from saved evidence. Dates are transaction or log dates in the saved records.

**Chain Runners: an on-chain renderer behind an HTTP pointer.** The accepted statement says the art is stored and generated on-chain. The current routing contract exposes `onChainTokenURI(1)`, returning inline SVG, and the saved gallery test renders that route unplugged. The ordinary `tokenURI(1)` uses HTTP. This supports `onchain-data-offchain-pointer`, rather than a failed storage claim. <!-- src: docs/methods/mutability.md:Separate data and ordinary pointers -->

**Blitmap and ChainFaces: the data is on-chain; the pointer is off-chain.** Blitmap's “All data is completely on chain” statement is supported by saved `tokenDataOf(1)` and `tokenSvgDataOf(1)` reads. Its ordinary HTTP `tokenURI` remains mutable through `setBaseURI`. ChainFaces' accepted claim concerns on-chain attributes and metadata: `getFace(1)` and `getGolfScore(1)` expose on-chain data while `tokenURI(1)` retains an Azure Rinkeby HTTP URL. ChainFaces is classed immutable. Both receive `onchain-data-offchain-pointer`, rather than `contradicted`. <!-- src: docs/methods/mutability.md:Separate data and ordinary pointers; data/claims/claims_reviewed.csv -->

**CryptoSkulls: a separate, owner-writable art contract.** The project's saved website links CryptoSkullsData at `0x9a7b94954751d539c63e16aa6e0557c451251394`. Read-only coverage checks found attributes and pixel arrays for all 10,000 skull indices. The data contract's EOA owner can overwrite component data through owner-only add functions; it is not sealed. The collection's `tokenURI(1)` still points at IPFS and its base URI remains owner-settable. The scoped storage statement receives `onchain-data-offchain-pointer`. Coverage establishes available data and dimensions, not pixel-by-pixel equivalence to an external archive. <!-- src: docs/methods/mutability.md:CryptoSkulls; data/mutability/reviewed_reads/cryptoskulls_coverage.json -->

**MoonCats: original seed storage, wrapper pointer.** The original 2017 MoonCatRescue contract stores the five-byte cat seed; the published parser is needed to reconstruct pixels. The mutable HTTP pointer is the acclimator wrapper's `setBaseURI` path. This is `onchain-data-offchain-pointer`; the saved check establishes seed storage, not an all-EVM pixel renderer. <!-- src: docs/methods/mutability.md:Separate data and ordinary pointers -->

**Moonbirds: a Safe-owned core and an EOA-owned renderer.** The core owner is a 2-of-4 Safe. On renderer `0xffe53829e5d367d8e3671bbfb95fe0e024f0d8b6`, the EOA owner's `setBaseUri(string)` and `setAnimationBaseUri(string)` redirect illustrated-image and animation prefixes. They do not overwrite legacy pixel-art records: direct legacy reads return pixel bytes and an inline BMP, supporting the scoped pixelated-art claim. Holder-only artwork selection is separate from the renderer owner's authority. <!-- src: docs/methods/mutability.md:Precise Moonbirds statement -->

**Art Blocks: creative-code edits and pointer edits.** Artist/admin functions can add, update or remove scripts before a project's script lock; `updateProjectBaseURI` changes the ordinary pointer separately. Saved reads establish sampled creative scripts on-chain, but the selected documentation combines complete metadata, accessibility and immutability promises, so its full assertion remains `unverifiable`. Locks and authority must be assessed per project. <!-- src: docs/methods/mutability.md:Separate data and ordinary pointers; Precise Moonbirds statement -->

**Nouns: expensive to read, with provider-dependent results.** The fork estimate for `tokenURI(1500)` is 119,289,149 gas. Of six public RPCs that answered, three refused even at 150M gas, one needed that manual limit and two served it by default. The saved evidence supports that provider split, not universal public-RPC failure. <!-- src: launch/cards/rpc_check_nouns_2026-10-21.json; docs/methods/gallery.md:Method -->

**Heraldia and NORMIES: name the authority and its scope.** Heraldia's EOA-controlled core and renderer can replace the renderer or its art-input storage. NORMIES' corresponding controls are held by a 3-of-5 Safe. These controls can replace the source of pixels and traits; they are distinct from whether the currently selected storage record itself has a live setter. Transitive dependencies have not been exhaustively audited. <!-- src: docs/methods/mutability.md:Precise Moonbirds statement -->

**Generative Exploration: a dependency that cannot be archived.** See Section 4.4. The artwork's input is the viewer's IP address.

## 6. Limitations and threats to validity

1. **Deploy year as a mint-year proxy.** A 2021 contract that minted in 2023 is binned as 2021, and an upgrade that changed `tokenURI` is invisible. <!-- src: docs/methods/universe.md:Deploy info -->
2. **Collection sampling gives each collection one count.** Each collection counts once, whether it has 100 holders or 100,000, and two or three sampled tokens stand in for all of them. A pre-reveal placeholder or mixed schemes can be missed. Our shares say nothing about the share of all tokens, or of value. <!-- src: docs/methods/census.md:section 1 -->
3. **How "dead" is judged.** Timeouts, rate limits and bot walls end as unknown and are never counted dead, so the legacy unavailable count and that count plus unknown give snapshot bounds. Reverts and gateway misses require the separate evidence-strength interpretation in Section 4.2. Evidence strength varies across dead rows. A collection is dead if its two or three sampled ids all fail, so one unminted or burned id range can push a live collection to degraded or dead. "IPFS not found" means no public gateway returned the CID in 15 to 40 seconds, which is weaker than a dead domain. In a live DNS re-check of 25 collections the census had called dead by DNS, 22 still failed to resolve; the rest were inconclusive or resolved again, so the DNS label may be about 10% soft. A `tokenURI` revert on every sampled id mixes unrevealed, paused and burned collections with contracts that have no `tokenURI`. <!-- src: docs/methods/census.md:section 3 caveat; docs/methods/analysis.md:sections 7, 8 -->
4. **Gateway status at one point in time.** We probed on 2026-10-21. `ipfs.io` and `dweb.link` were bot-walled to our client, and a browser using the service-worker gateway might still load content, which we cannot test. <!-- src: docs/methods/census.md:section 3 -->
5. **The spam heuristic** is a lower bound on junk. Weak signals can misflag legitimate factory-created collections, and ordinary-looking spam escapes it. <!-- src: docs/methods/universe.md:Flags -->
6. **Claim discovery is incomplete.** Unverified source and JavaScript-only sites can hide statements. Directory descriptions are excluded unless accepted project-authored evidence is also saved. The 160 reviewed claimants describe the adjudicated discovery set, not every collection that has ever made a storage claim. <!-- src: docs/methods/claims.md:Method, Limits -->
7. **Mutability parsing is heuristic.** Access gates are parsed from source with regular expressions; private immutables and lock flags without a getter are invisible; recorded dependency and control paths are incomplete. <!-- src: docs/methods/mutability.md:Caveats -->
8. **RPC gas caps.** A renderer that needs more gas than every available node allows will look broken. Nouns and Lil Nouns needed a local fork. <!-- src: docs/methods/census.md:section 1; docs/methods/gallery.md:Method -->
9. **The gallery is a candidate set.** Its 86% unplugged-identical rate describes this candidate set; it provides no population estimate for all on-chain NFTs. It uses one token per collection, one browser, and today's Art Blocks generator and registry. <!-- src: docs/methods/gallery.md:Limitations -->
10. **Media heads only.** We read at most 64 KB per media file; "alive" means a 2xx response with the expected file type, not an intact file. ERC-1155 ids come from a block-explorer index that can be incomplete. <!-- src: docs/methods/census.md:section 1, 4 -->
11. **Snapshot and search.** Measurements cluster around 2026-10-21. The literature search was limited by the sources available. <!-- src: research/prior-art.md:header -->
12. **Census coverage.** The random stratum (3,000 collections) is complete and is the basis for every percentage with an interval. The top-by-holders stratum is partial (11,186 of 46,494) and not representative. The spam sample has 5 of 500 collections. The ordinary-pointer funnel covers 105 of 160 reviewed claimants; storage outcomes cover all 160. Numbers are from the census snapshot of 2026-10-22 02:21:24 UTC. <!-- src: data/analysis/headlines.json:meta -->

## 7. Responsible disclosure and ethics

Some of the hostnames behind NFT media are domains that have lapsed. In principle, anyone who registers such a domain could serve whatever they like to every wallet and marketplace that resolves the token. We found no documented case of this happening to NFT art, and our read-only checks created none.

* **We observed only.** DNS and RDAP status; no domain registration, bid or owner contact, and no fetch from a hostname without a DNS answer.
* **We publish aggregate counts.** Host-level names, collections and contracts remain in private working data.
* **Notification.** If we contact anyone about an at-risk domain, it will be through a verified private channel (the project's published security contact, a GitHub advisory, or SEAL) before any further release. No notification had been sent at the measurement snapshot.
* **Public data and politeness.** Everything else is on-chain or public. We kept to our rate limits, downloaded at most 64 KB per media file, and refused private IP ranges.
* **Named collections.** Case studies quote public claims beside what the chain shows and make no assessment of intent.

## 8. Conclusion and practical guidance

The honest answer to "how many NFTs would survive if the network went away" depends on what you count as surviving. In a random sample of 3,000 non-spam collections with at least 100 holders, 2.9% have metadata and all sampled media on-chain, including financial position/receipt NFTs. This is an upper bound for rendering; only the gallery is render-tested. Metadata is unavailable for 30.3% under the legacy census label, including contract reverts and public-gateway misses; it reaches 33.0% if every unknown is also unavailable. Most of the rest depend on IPFS, Arweave or a web server that still answers. <!-- src: data/analysis/headlines.json:random.onchain.truly_onchain_census; data/analysis/headlines.json:random.liveness.bounds_dead -->

Three findings hold regardless.

1. **A pointer and the art can diverge.** Of famous "on-chain" projects, several point `tokenURI` at a web API. Some on-chain art requires a provider that accepts an unusually expensive read. Classifying by scheme alone gets both wrong.
2. **Most on-chain art survives being unplugged, and the exceptions are fixable.** 71 of 83 gallery tokens draw identically. 10 of the 11 failures need only a public library that can be archived. The remaining failure uses the viewer's IP address as input.
3. **On-chain storage can remain mutable.** 302 of the 606 historical audit contracts have EOA pointer power. Among reviewed storage claimants, 81 of 160 can be repointed by one EOA or multisig account, including 53 of 103 explicit claimants. This control observation does not refute on-chain storage.

**For collectors.**
* Call `tokenURI` (or `uri`) on the contract's "Read contract" page. `data:` is on-chain. `ipfs://` and `ar://` are content-addressed. `https://` is a server someone pays for. If the metadata is `data:` but the image is a link, we classify the media as off-chain.
* Check `owner()` and whether a freeze, lock or `renounceOwnership` was called. A multisig beats an account. A renounced owner beats a multisig.
* Back up the metadata and media with their hashes, and pin the CID yourself. A gateway URL points at a company, but the CID inside it is still your recovery key.

**For artists.**
* Write `ipfs://<cid>` or `ar://<id>`, never a gateway URL.
* If you claim "on-chain", define what you mean and test it with the network off. Inline your libraries or put them on-chain. Avoid runtime inputs you cannot archive unless that is the piece.
* Freeze what you promise: call the lock or renounce ownership, and cite the transaction in the description.
* Pin with more than one provider, and keep any domain you use renewed. A lapsed domain is a standing offer to whoever registers it next.

**For marketplaces and wallets.**
* Show where the metadata and media live (on-chain, IPFS, Arweave, a named host), and who can change them.
* Resolve `ipfs://` through more than one gateway, run your own, and cache.
* Test an "on-chain" badge with a network-off render. A badge that stays green when the page fetches a CDN script is a promise the chain cannot keep.

**Next.** Re-run the census every quarter, render every on-chain candidate, track `ipfs.io` and `dweb.link` after the Shipyard wind-down, and give projects a private report of their own dead or claimable hostnames before anyone else can act on them.

## Appendix A: Class definitions

Rules are applied in order, first match wins, after `strip()` and `{id}` substitution. <!-- src: docs/methods/census.md:section 2 -->

| Class | Rule |
|---|---|
| `broken` | Empty; undecodable `data:` URI; `ipfs://` with an invalid CID; `ar://` with an invalid id; no scheme and not a CID; or no URI at all. Reasons: `revert` (reverted on every node including fallbacks), `empty-or-undecodable`, `rpc-error` (infrastructure failure, counted unknown, not dead), `no-scheme` |
| `data-uri` | Starts with `data:` (base64, utf8, percent-encoded, or mislabelled), or the string itself is raw JSON, `<svg`, or `<html`. Payload kinds: json, svg, html, text |
| `onchain-renderer` | A `data-uri` collection where any of: bytecode (or implementation bytecode) has the Base64 alphabet table plus an SVG, HTML or JSON data-URI literal, or `EXTCODECOPY` (SSTORE2 or EthFS-style reader); verified source mentions SSTORE2, EthFS, scripty, `Base64.encode`, `<svg`, IRenderer or descriptor; `eth_estimateGas(tokenURI)` is at least 400k gas and at least 120 gas per output byte; or `estimateGas` fails but the call works on a high-cap node. Otherwise it stays `data-uri`. Best effort |
| `ipfs` | `ipfs://<cid>[/path]`, `ipfs://ipfs/<cid>`, `/ipfs/<cid>`, a bare CID, or an http(s) URL with `/ipfs/<cid>` in its path or `<cid>.ipfs.<gateway>` as host. A hard-coded gateway is recorded as `gateway` with its style (path, subdomain, api-arg) |
| `arweave` | `ar://<43-character id>`, a URL on an Arweave gateway whose first path segment is a 43-character id, or an `*.arweave.net` sandbox subdomain |
| `http` | Any other http(s) URL, including `/ipns/` paths on an HTTP gateway |
| `other` | `ipns://`, `bzz://`, `sia://` and similar, recognized but not fetchable |

Media fields (`image`, `image_data`, `animation_url`) use the same classifier. An `image_data` that starts with `<` is an inline SVG or HTML data URI.

**On-chain candidate**: metadata on-chain and every media field on-chain. **Clean candidate**: a candidate whose on-chain SVG or HTML has no external references in loading contexts (`src`, `href`, `xlink:href` and `poster` on loading tags, CSS `url()` and `@import`, `fetch` and `import`, JavaScript `.src=`). Namespaces, doctypes and `<a href>` links are ignored (the latter are recorded as mentions). **Truly on-chain**: a candidate that also renders under condition B.

**Liveness (per fetch)**: `alive` if 2xx and the body parses as JSON (metadata) or looks like media by magic bytes or content type (HTML counts for `animation_url`); `dead` with a reason (NXDOMAIN, SERVFAIL, NODATA confirmed on two resolvers; TLS errors; refused or reset connections; 404, 410 and other 4xx; 5xx; not-json; parked; html-instead-of-media; empty-body; redirect loops; private-IP targets, which are never contacted); `unknown` (timeouts, 408, 425, 429, temporary DNS failures, bot walls). HTTP targets are dead only if negative in both passes.

**Token liveness**: dead if metadata is dead; alive if metadata is fine (or on-chain) and the image is alive; degraded if the image is dead; unknown otherwise. **Collection liveness**: alive if all tokens alive; dead if all dead; degraded for any degraded or any mix of alive and dead; unknown if all unknown.

**Mutability classes:** `immutable`, `dao-or-timelock-mutable`, `multisig-mutable`, `eoa-mutable`, `unknown`. Final class is the worst of the contract's own and its in-path dependencies'. <!-- src: docs/methods/mutability.md:Method -->

**Reviewed claims:** only project-authored art/metadata storage statements count. Explicit strength requires “100%”, “fully”, “entirely” or “completely”; storage-forever alone is excluded from the explicit subset. Outcomes are `holds`, `onchain-data-offchain-pointer`, `contradicted` and `unverifiable`; only `contradicted` is a failed claim. <!-- src: docs/methods/claims.md:Counts -->

## References

Identifiers are those in `research/prior-art.md` section 10, where full URLs and access dates are given. <!-- src: research/prior-art.md:Bibliography A1 -->

**Academic**
* [A1] D. Das, P. Bose, N. Ruaro, C. Kruegel, G. Vigna. Understanding Security Issues in the NFT Ecosystem. ACM CCS 2022, pp. 667-681. doi:10.1145/3548606.3559342. arXiv:2111.08893.
* [A2] Z. Wang, J. Gao, X. Wei. Do NFTs' Owners Really Possess their Assets? A First Look at the NFT-to-Asset Connection Fragility. WWW 2023. doi:10.1145/3543507.3583281. arXiv:2212.11181.
* [A3] L. Balduf, M. Florian, B. Scheuermann. Dude, where's my NFT? Distributed Infrastructures for Digital Art. DICG 2022. doi:10.1145/3565383.3566106. arXiv:2210.11166.
* [A4] S. Barrington, N. Merrill. The 'Fungibility' of Non-Fungible Tokens: A Quantitative Analysis of ERC-721 Metadata. arXiv:2209.14517, 2022 (preprint).

**Tools, essays, documentation and incidents**
* [T1] OpenSea Help Center. What is the metadata field on NFT pages? 2026-02-02.
* [T2] N. Hladek. How many NFTs are actually on the blockchain? Right Click Save, 2022-06-20.
* [T6] W. M. Peaster. What Does "On-Chain" Really Mean? Right Click Save, 2023-06-23.
* [T7] Art Blocks Docs. The Art Blocks Generator. https://docs.artblocks.io/protocol/on-chain-generator.md
* [T8] Art Blocks Docs. NFT Metadata Storage at Art Blocks. https://docs.artblocks.io/protocol/on-chain-storage.md
* [T13] G. Harrison. When good NFTs go bad. alwaysNFT on Medium, 2022-05-13 (archived copy).
* [T20] E. Calderon. True On-Chain Artwork: A Four-Year Journey. Art Blocks, 2024-11-27.
* [T27] NFT.Storage Decommission Notice (js-client README).
* [T29] Cloudflare Blog. Cloudflare's public IPFS gateways and supporting Interplanetary Shipyard, 2024.
* [T30] L. Hitchcock. Why RTFKT and Nike's Ethereum NFT Artwork Disappeared. Decrypt, 2025-04-24.
* [T31] W. M. Peaster. Nifty Gateway's Original Shutdown Plans Threatened Droves of NFTs. Bankless, 2026-01-27.
* [T32] ZKM, The Defiant and Bankless on the Foundation shutdown, 2026.
* [T33] Filebase. Infura IPFS Is Shutting Down: How to Migrate, 2026-07-29 (relays Infura customer notice).
* [T34] Cointelegraph, Cryptobriefing, RuntimeWire on the Shipyard wind-down, 2026-08-25.

**Our data.** Universe: `data/universe/collections.parquet`. Census: `data/census/`. Gallery: `data/gallery/results.csv`, `data/dep-archive/MANIFEST.json`. Claims: `data/claims/claims_reviewed.csv`, `data/analysis/claims_summary.json`. Mutability: `data/mutability/mutability.csv`. Analysis: `data/analysis/headlines.json`. Hosts: `data/hosts/hosts.csv`.
