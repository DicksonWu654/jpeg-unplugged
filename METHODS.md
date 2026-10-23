# Methods

All dates are from the October 2026 run. Every request made by the pipeline is logged (URL, method, status, time, SHA-256) in a
raw-evidence manifest that is not part of this repository (see README, "Raw evidence").

## 1. Universe (`scripts/universe/`, `data/universe/`)

All Ethereum mainnet ERC-721 and ERC-1155 contracts with at least 100 holders, from the Blockscout token list sorted by holder
count (parallel keyset segments with overlap at the seams, deduplicated by address). Creator, creation transaction, block, timestamp
and factory come from Etherscan `getcontractcreation`; `deploy_year` is derived from that timestamp and is a proxy for mint year
only (a collection can mint years after deployment). EIP-1167 minimal-proxy clones are flagged because their logic lives in an
implementation contract.

Flags never remove rows. `spam_suspect` is a heuristic lower bound on junk: URL or TLD in the name, claim/reward/airdrop wording,
templated "Mint Pass" names, imitations of well-known names, the same name on many contracts, and for ERC-1155 many contracts with
an identical holder count. Weak signals only count in pairs. `is_ens_or_infra` marks a short explicit list (ENS, Uniswap
positions, POAP, shared storefronts and similar) that is never treated as spam. Roughly half of ERC-1155 contracts in the universe are
mass-produced airdrop families, and holder-weighted and collection-weighted results differ a lot for that reason.

Limits: Blockscout metadata fields such as reputation, icon and market data carry almost no information; ERC-1155 total supply is
unknown for most rows; proxy details exist only for the highest-holder subset.

## 2. Census (`scripts/census/`, `data/census/`)

**Sampling.** Collections with at least 1,000 holders contribute three tokens (low, middle, recent), smaller ones two. ERC-721
enumerable contracts use `totalSupply` and `tokenByIndex`, every id confirmed with `ownerOf`; non-enumerable ones are probed over
low ids and a geometric grid; ERC-1155 uses the indexer's instance list (minimum, median, maximum id). Each id records how it was
found. If some sampled ids revert and others return a URI, the reverted ones are replaced by up to two others; if all revert the
collection is `broken`.

**Reading the URI.** `tokenURI(uint256)` / `uri(uint256)` through `eth_call` on several public RPC endpoints with retries; the raw
response is saved. Heavy on-chain renderers can exceed the gas cap of some endpoints, so every revert is retried on higher-cap nodes
and flagged `revert_gas_cap_suspected` if that works. The `{id}` placeholder of ERC-1155 is replaced by the id as 64 hex digits.

**Classes** (first match wins): `broken` (empty, undecodable, invalid CID, no scheme, or reverts on every node), `data-uri`
(`data:` URI or raw JSON/SVG/HTML), `onchain-renderer` (a data URI built by contract logic: bytecode with a Base64 table plus SVG or
`EXTCODECOPY` readers, verified source mentioning SSTORE2/EthFS/scripty/Base64, or a very gas-heavy `tokenURI`; best effort),
`ipfs`, `arweave`, `http` (including `/ipns/` on a web gateway) and `other` (`ipns://`, `bzz://` and similar). Image, image_data and
animation_url use the same classifier. A `data:` JSON whose image is an `https://` URL is not on-chain. On-chain SVG and HTML are
scanned for external loading references (`src`, `href`, `url()`, `@import`, `fetch`).

**Liveness.** `alive`, `dead` (with reason) or `unknown`. A fetch is alive if it returns 2xx and the body parses as the expected
kind. HTTP targets are `dead` only if negative in two passes at least 25 minutes apart; timeouts, 429/408 and bot walls are `unknown`.
IPFS and Arweave targets are alive if any working gateway serves the content, and `gateway-not-found` only if at least two distinct
working gateways answered negatively after the second pass. Two columns exist: `liveness` is content-level (some gateway serves the
CID), `liveness_exact` judges the URL exactly as written in the token data. Token liveness is `dead` if metadata is dead, `degraded`
if metadata works but the image is dead, `alive` if both work. Collection liveness aggregates its tokens.

**Gateways.** A canary run classified public gateways as working, bot-walled (HTTP 403/429 to non-browser clients, so unmeasurable) or
dead; see `data/census/gateways.json`. "Not retrievable through the public gateways within 15 s (first pass) or 40 s (second pass)"
is not the same as "gone from IPFS".

**Politeness.** At most 2.5 requests per second per public gateway, 3 per second per other host, honouring 429; a guard refuses
non-global IP targets.

## 3. Marketing claims (`scripts/claims/`, `data/claims/`)

Sources: verified contract source (Etherscan, Blockscout) scanned for on-chain phrasing in comments and string literals (library
paths, protocol-plumbing contexts such as "on-chain royalties" and boilerplate repeated in four or more contracts are removed);
`contractURI()` descriptions; the OpenSea collections API (slug guessed from the name, accepted only if the address matches);
the fullyonchain.art directory, community lists, project sites and READMEs. Every quoted claim was re-checked as a verbatim substring
of its saved evidence. Claim strength is graded explicit ("100%", "fully"), generic ("on-chain"), storage-forever, or implied
(directory headings only; not tested as claims). `negative_controls.csv` lists well-known collections where no storage claim was found.
Coverage is a lower bound: about 38% of the scanned contracts have no verified source anywhere.

## 4. Mutability (`scripts/mutability/`, `data/mutability/`)

For each claimed on-chain collection the pipeline records the setter surface in the bytecode and verified source (URI, base URI,
renderer and royalty setters; freeze and lock functions), the current owner and holders, external dependencies, setter history from
logs, and contradictions between the claim and the pointer. `data/mutability/evidence/` holds one evidence file per contract.

## 5. Gallery (`scripts/gallery/`, `data/gallery/`, `data/dep-archive/`)

Candidates are collections that pass the on-chain pointer check. Each token's artwork document is assembled only from chain
bytes (`eth_call` responses are saved with call data, block and SHA-256) and rendered in headless Chromium under three conditions:
**A** normal, **B** all non-local network requests blocked, **C** blocked plus a local archive of the declared dependencies the
artwork requested successfully in A (scripts, stylesheets, fonts, or URLs that appear literally in the document). A token is
`identical` when its B or C screenshot differs from A by no more than the A-versus-A animation noise floor, `broken` when it does
not, and `a-blank` when the work is near-invisible by design. Manual overrides are stored in separate columns. Runtime content fetches
(API JSON, images computed at run time) are recorded but not archived, because an archive of declared dependencies cannot resurrect
content. Libraries whose licence does not allow redistribution are listed in the manifest with URL and SHA-256 only (see `NOTICE`).

## 6. Site (`site/`)

The site is static. `site/build/` aggregates the census tables into the JSON the site reads (`site/data/`), and `site/build/qa.py`
checks the built data against the tables.

### Public-data redaction

The public export and site-data generator use the same redaction rules. Every withheld host name and URL on that host is
replaced with `[withheld-host]`, including values in parquet, CSV, JSON, JSONL, nested structures and data URIs. Base64, percent encoding, nested JSON/SVG and gzip payloads are decoded recursively;
recoverable prefixes of truncated census URI values are checked too, then changed payloads are re-encoded.
Provider-specific missing-resource responses are generalized to HTTP or DNS failure classes throughout the public data.
Ordinary HTTP failures use the same classes, so the replacement class does not distinguish candidate collections.
This prevents failure signatures from identifying collections associated with a potentially recreatable resource.
Per-collection storage classes and alive/dead/unknown status are retained; raw evidence is not rewritten.
An event signature containing a disallowed provenance keyword in a JSON key is retained in a `signature` value under
a neutral event key in exported evidence; its counts and saved source evidence are unchanged.

The release scan parses every public dataset and checks all decoded strings against the withheld list and failure
signatures. It also rejects internal working directories and editorial reminders. Public methods are maintained as public
documents rather than generated by rewriting working notes.

## 7. Known limits

- Deploy year is not mint year; sampled tokens are not the whole collection; two or three ids per collection can miss mixed
  collections.
- The spam and on-chain-renderer classifications are heuristics; both are lower bounds and are reported as such.
- Public gateways and free API tiers are rate limited, so some results are `unknown`, and `unknown` is never counted as dead.
- Results describe the state of the web on the run dates; servers change.
