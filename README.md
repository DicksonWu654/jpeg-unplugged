# JPEG Unplugged

Live site: https://jpeg-unplugged.dicksonwu.xyz

If the internet outside Ethereum went away, how many NFTs would still exist? This project counts it. It takes every
Ethereum mainnet ERC-721 and ERC-1155 collection with at least 100 holders, finds where each token's metadata and image
actually live (on-chain, IPFS, Arweave or an ordinary web server), checks whether those locations still answer today, tests
the "fully on-chain" claims that collections make about themselves, and renders a gallery of on-chain artworks with the
network unplugged.

**Compiled with AI assistance, so there will be mistakes.** Every number traces to a saved table in `data/`, and corrections
are welcome as issues on this repository.

## Contents

| Path | What it is |
|:---|:---|
| `site/` | The built static site, including the "unplug the internet" toggle. Open `site/index.html` or serve the folder as it is |
| `article/` | The written article |
| `launch/` | The launch cards |
| `data/universe/` | The census universe: one row per contract |
| `data/census/` | Sampled tokens, classification of metadata and media location, liveness verdicts, gateway canary |
| `data/claims/` | On-chain marketing claims with quoted text and source, negative controls, source-code signals |
| `data/mutability/` | Setter surface, holders, dependencies and setter history for claimed on-chain collections, with per-contract evidence |
| `data/hosts/` | Aggregate tables of the hosts that metadata and media point to |
| `data/analysis/` | Derived headline tables used by the article and the site |
| `data/gallery/` | One folder per gallery token: result, request logs, console logs, screenshots for the three conditions |
| `data/dep-archive/` | Manifest of the third-party libraries that artworks load at run time, and the ones whose licence allows redistribution |
| `scripts/` | Everything needed to rebuild the tables from the raw evidence |
| `research/` | Prior-art review and its source table |
| `METHODS.md`, `CHANGELOG.md`, `LICENSE`, `NOTICE` | Methodology, release history, licences |

### Table sizes

| File | Rows | What it is |
|:---|---:|:---|
| `data/universe/collections.csv` | 58,617 | Ethereum ERC-721 / ERC-1155 contracts with at least 100 holders (the census universe) |
| `data/census/census_collections.parquet` | 14,191 | Census: one row per collection (metadata and media location, liveness) |
| `data/census/census_tokens.parquet` | 36,687 | Census: one row per sampled token |
| `data/claims/claims.csv` | 753 | On-chain marketing claims, each with its quoted text and source |
| `data/mutability/mutability.csv` | 606 | Mutability of claimed on-chain collections (setter surface, holders, dependencies) |
| `data/gallery/<slug>/` | 83 | On-chain gallery: per-token renders under three network conditions, request logs, results |

## Method in one paragraph

Universe: Blockscout token list filtered to at least 100 holders, with creation data from Etherscan. Census: for each
collection, two or three tokens are sampled (low, middle, recent id); `tokenURI` or `uri` is read with `eth_call`, classified as
`data-uri`, `onchain-renderer`, `ipfs`, `arweave`, `http`, `other` or `broken`, and the image and animation fields are classified
the same way. A target is `dead` only if it fails in two passes; timeouts and rate limits are recorded as `unknown`. Gallery: each
on-chain artwork is rendered in a browser three times (normal, network blocked, network blocked plus a local archive of declared
dependencies) and compared pixel by pixel. See `METHODS.md` for the exact rules and caveats.

## Reproducing the tables

Python 3.11 or newer and `pip install -r requirements.txt` (the gallery renderer also needs `playwright install chromium`).
Scripts read API keys from the environment (`ETHERSCAN_API_KEY`) and write raw evidence to `data/raw/<source>/` with a manifest
line per request (URL, method, status, time, SHA-256). Run order: `scripts/universe/` (enumerate, creation, assemble, flags),
`scripts/census/census.py`, `scripts/claims/`, `scripts/mutability/`, `scripts/gallery/`, then `site/build/`. Public RPC
endpoints and free API tiers are rate limited; the scripts throttle themselves and are resumable.

## Raw evidence

The raw evidence (about 2.4 GB: RPC responses, Blockscout and Etherscan pages, fetched metadata, media heads) is too large for
this repository. The derived tables here are what the article and site use; each table row can be checked against the raw
evidence, which is available on request through an issue on this repository, or can be regenerated with the scripts above
(results will differ where servers have changed since the October 2026 run). Media files were never stored in full: only status,
headers, size, SHA-256 and the first 64 KB.

Public data replaces withheld host names and their URLs with `[withheld-host]` and generalizes provider-specific failure
signatures to HTTP/DNS classes. Storage classifications and liveness are retained. Host names are withheld from the public
derivatives. See `METHODS.md` for the redaction procedure.

## Licence

Code is MIT; data and text are CC BY 4.0; third-party libraries and on-chain artworks keep their own terms (see `LICENSE` and
`NOTICE`).
