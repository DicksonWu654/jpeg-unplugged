# Site data schema (version 1)

The site never contains a hardcoded result. Every number on the page is read at load time from these files:

| File | Produced by | Used for |
|---|---|---|
| `site/data/census.json` | census pipeline (or `site/build/aggregate_census.py` from `collections.json`) | all census charts, the hero count, methods numbers |
| `site/data/collections.json` | census pipeline | hero dot field (one dot per collection), searchable table, claim exhibits, cross-check of `census.json` |
| `site/data/gallery.json` | `site/build/gallery_json.py` (already real) | gallery |
| `site/gallery-assets/manifest.json` | gallery harness (already real) | file list for the gallery |

**Sample mode.** If `"sample": true` in `census.json` OR `collections.json`, the page shows a sticky banner
"SAMPLE DATA - not real results" and watermarks the census sections. Real files must set `"sample": false`
(or omit it). The two files must agree.

**Consistency check.** On load the page recounts `collections.json` and compares to `census.json` (totals, both
location tables, liveness, survival). Mismatches are printed in the Methods "Data check" line and `console.warn`.
`census.json` is what the charts draw; `collections.json` is what the dots and table draw. Easiest way to avoid
drift: produce `collections.json` first, then run
`python site/build/aggregate_census.py site/data/collections.json site/data/census.json`
and add the optional hand-made parts (`dead_reasons` is generated too).

Unit of everything below: **one ERC-721 / ERC-1155 collection contract on Ethereum mainnet with >= 100 holders.**

---

## Enumerations

### `Location` (where a URL/blob lives; used for metadata AND media)
| value | meaning |
|---|---|
| `data-uri` | the tokenURI / image is literally a `data:` URI stored or returned by the contract |
| `onchain-renderer` | a `data:` URI built at call time by contract logic (SVG/HTML generated or assembled in Solidity, SSTORE2 chunks, on-chain generator) |
| `ipfs` | `ipfs://`, or an IPFS gateway URL (`https://<gw>/ipfs/<cid>`) |
| `arweave` | `ar://` or an Arweave gateway URL |
| `http` | any other http(s) URL (centralized server, CDN, API) |
| `broken` | tokenURI reverts / empty / undecodable / no usable media URL where one was expected |
| `other` | everything else: no token found, no media field (pure-text/audio-less), unrecognised scheme |

"On-chain" below means `data-uri` or `onchain-renderer`.

### `Liveness` (does the collection's media/metadata load today?)
| value | meaning |
|---|---|
| `alive` | metadata and media fetched OK for the sampled tokens (or are on-chain and decoded) |
| `degraded` | metadata loads, media (or part of the sampled tokens) does not |
| `dead` | metadata or media gone for the sampled tokens after retries (DNS gone, 4xx, 5xx, gateway not found...) |
| `unknown` | timeouts / rate limits / bot walls / unreadable; NOT counted as dead |

### `Survival` (`survives_unplugged`: would the collection still render with the outside internet gone?)
| value | meaning |
|---|---|
| `yes` | metadata and media are both on-chain AND nothing external is needed to draw it |
| `partial` | on-chain but depends on something external (CDN script, font, image) or only some tokens/traits survive |
| `no` | needs an off-chain server/network (IPFS, Arweave, HTTP) or is broken |
| `unknown` | could not be determined |

### `ClaimVerdict` (marketed "100% / fully on-chain" vs measured)
`holds` (metadata + media on-chain and renders unplugged) | `partial` | `fails` | `unverified`.

### `ClaimStrength`
`explicit-100%` (says 100% / fully / entirely on-chain) | `strong` (says "on-chain" without qualifier) | `weak` (loosely or partly).

### `GatewayKind`
`ipfs-gateway` | `arweave-gateway` | `cdn` | `api` | `other`.

---

## `census.json`

```jsonc
{
  "schema_version": 1,                    // int, must be 1
  "sample": false,                        // bool. true => SAMPLE banner
  "generated_at": "2026-10-22T09:00:00Z", // ISO 8601 string
  "snapshot_date": "2026-10-21",          // YYYY-MM-DD, day the live fetches were made
  "snapshot_block": 26243220,             // int | null, Ethereum block used for eth_call reads
  "criteria": {
    "chain": "ethereum",                  // string
    "min_holders": 100,                   // int
    "standards": ["ERC-721", "ERC-1155"], // string[]
    "spam_excluded": true                 // bool
  },
  "totals": {
    "collections": 1234,                  // int, == length of collections.json
    "erc721": 900,                        // int
    "erc1155": 334                        // int
  },
  "metadata_location": {                  // counts of collections by Location of the tokenURI JSON
    "data-uri": 0, "onchain-renderer": 0, "ipfs": 0, "arweave": 0, "http": 0, "broken": 0, "other": 0
  },
  "media_location": {                     // counts by Location of the image (or animation_url if no image)
    "data-uri": 0, "onchain-renderer": 0, "ipfs": 0, "arweave": 0, "http": 0, "broken": 0, "other": 0
  },
  "liveness": { "alive": 0, "degraded": 0, "dead": 0, "unknown": 0,
                 "dead_strength": { "strong": 0, "weak": 0 } },
  "dead_reasons": {                       // optional. object string -> int. Counts of collections by the
    "dns-nxdomain": 0,                    // dominant reason among dead + degraded ones. Keys are free text
    "http-404": 0,                        // but use lowercase-with-dashes, e.g. dns-nxdomain, tls-error,
    "gateway-not-found": 0                // http-404, http-5xx, timeout-confirmed, tokenuri-revert
  },
  "survival": { "yes": 0, "partial": 0, "no": 0, "unknown": 0 },
  "by_year": [                            // one entry per deploy year, ascending, no gaps required
    {
      "year": 2021,                       // int, contract deploy year
      "collections": 100,                 // int
      "media_location": { "data-uri": 0, "onchain-renderer": 0, "ipfs": 0, "arweave": 0, "http": 0, "broken": 0, "other": 0 },
      "liveness":       { "alive": 0, "degraded": 0, "dead": 0, "unknown": 0 },
      "survival":       { "yes": 0, "partial": 0, "no": 0, "unknown": 0 }
    }
  ],
  "gateways": [                           // hardcoded gateway/host baked into tokenURIs or media URLs, sorted desc by collections
    { "host": "gateway.pinata.cloud",     // string, hostname
      "kind": "ipfs-gateway",             // GatewayKind
      "collections": 40,                  // int, collections whose URLs hardcode this host
      "dead_collections": 12 }            // int, of those, how many are dead or degraded today
  ],
  "fake_onchain": {                       // collections whose METADATA is on-chain (data-uri | onchain-renderer)
    "metadata_onchain": 90,               // int, == metadata_location["data-uri"] + ["onchain-renderer"]
    "media_location": {                   // Location counts of their MEDIA. "fake" = ipfs + arweave + http
      "data-uri": 0, "onchain-renderer": 0, "ipfs": 0, "arweave": 0, "http": 0, "broken": 0, "other": 0
    },
    "http_dead": 0                        // int, of those with http media, how many are dead/degraded today
  },
  "claims": {                             // collections whose own materials claim to be (fully) on-chain
    "claimed": 60,                        // int, number of collections with a non-null `claim` in collections.json
    "verdicts": { "holds": 0, "partial": 0, "fails": 0, "unverified": 0 },   // sums to claimed
    "explicit_100": 40                    // int, of claimed, how many have strength "explicit-100%"
  }
}
```

Rules the page relies on: each location table sums to `totals.collections`; `liveness` and `survival` sum to
`totals.collections`; `sum(by_year[].collections) == totals.collections`; `claims.verdicts` sums to `claims.claimed`.
Missing optional keys (`dead_reasons`) hide the relevant sub-chart. Missing required keys make the section show a
"census.json is missing <key>" notice instead of silently showing zeros.

---

## `collections.json`

```jsonc
{
  "schema_version": 1,
  "sample": false,                        // bool, must match census.json
  "generated_at": "2026-10-22T09:00:00Z",
  "collections": [
    {
      "address": "0x...",                 // string, 0x + 40 hex, checksum or lowercase
      "name": "CryptoPunks",              // string
      "standard": "ERC-721",              // "ERC-721" | "ERC-1155"
      "holders": 3300,                    // int
      "deploy_year": 2017,                // int
      "metadata_class": "http",           // Location
      "media_class": "onchain-renderer",  // Location
      "animation_class": null,            // Location | null (animation_url, when present)
      "liveness": "alive",                // Liveness
      "dead_reason": null,                // string | null, same vocabulary as census.dead_reasons keys; set when dead/degraded
      "survives_unplugged": "yes",        // Survival
      "hardcoded_gateways": ["ipfs.io"],  // string[], hostnames hardcoded in the URLs ([] if none)
      "media_hosts": ["example.com"],     // string[], optional: other hostnames the media/metadata live on
      "claim": null,                      // null | Claim (see below)
      "evidence_url": "https://github.com/DicksonWu654/jpeg-unplugged/tree/main/evidence/census/0x..." // string | null; relative paths allowed.
                                          // Page links it as "evidence". "#" in sample data.
    }
  ]
}
```

`Claim`:
```jsonc
{
  "strength": "explicit-100%",            // ClaimStrength
  "text": "100% on-chain generative art",// string, verbatim quote (<= 300 chars)
  "source_url": "https://...",            // string, where the quote was found
  "verdict": "fails",                     // ClaimVerdict
  "reason": "image is https://..."        // string, one short sentence on why (shown in the exhibit list)
}
```

The page derives the Etherscan link from `address`. Sort order in the file does not matter.

---

## `gallery.json` (generated, real)

Produced by `site/build/gallery_json.py` from `data/gallery/results.csv` and `site/gallery-assets/manifest.json`.
`items[]` has: `slug, name, family ("art-blocks"|"other"), contract, token (string), medium, storage, file, file_type
("html"|"svg"), bytes, archive|null, archive_bytes, archive_urls[], verdict_B, verdict_C (final, manual override
applied), auto_verdict_B/C, manual_override, diff_B/C, noise, ext_requests_A, ext_hosts_A[], blocked_B,
still_blocked_C, console_errors_B, page_errors_B, declared_deps[], gas_est, needs_fork, notes, thumbs{A,B,C}`.
Verdict enum: `identical | broken | degraded | a-blank`.

---

## `mutability.json` (generated, real)

Built by `site/build/mutability_json.py` from `data/mutability/`. Keys: `classes`, `by_claim.{explicit,generic,forever,none}` (each a count per
class plus `total`; classes are `immutable | dao-or-timelock-mutable | multisig-mutable | eoa-mutable | unknown`), `funnel`
(`claimants, claimants_contradicted, explicit, explicit_contradicted, explicit_contradicted_eoa, data_only_mutable`), `pointer_power`
(`eoa, multisig, dao-or-timelock, none`), `upgradeable`, `swaps_observed`, `lanes[]` (`lane, contract, class, summary, claim, evidence`) and
`timeline[]` (`lane, contract, date, kind: renderer-swap|uri-pointer|descriptor-update|sealed, what, tx`).

## `hosts.json` (optional, aggregate counts only)

Built by `site/build/hosts_json.py` from `data/hosts/hosts.csv`. The section stays hidden unless `data/available.json` lists `hosts: true`
(the build scripts write that file). Never contains individual claimable hostnames; `examples[]` holds only rows flagged as already public.
```jsonc
{
  "schema_version": 1,
  "snapshot_date": "2026-10-21",
  "totals": { "hosts": 0, "collections": 0 },       // hosts required; collections optional
  "by_status": { "live": 0, "dns-nxdomain": 0, "tls-error": 0, "http-error": 0, "parked": 0, "unknown": 0 },  // hostnames per status, required
  "takeover": { "registrable_hosts": 0, "collections_affected": 0,          // optional block
                "dangling_hosts": 0, "dangling_collections_affected": 0,     // optional
                "expiring_soon_hosts": 0, "expiring_soon_collections_affected": 0 },  // optional
  "by_kind": [ { "kind": "ipfs-gateway", "hosts": 0, "dead_hosts": 0 } ],    // optional
  "examples": [ { "host": "example.com", "what": "one line", "source_url": "https://..." } ]  // optional, already-public only
}
```

The saved host table uses `verdict` as its status column. Its aggregate `takeover.evidence_counts`
contains `cloud_candidates`, `registry_404`, `dns_only`, and `registration_after_deploy` host counts.
These are evidence categories; actual reclaimability was not tested. When collection counts are numeric
per-host dependency counts, their sum is `collection_dependencies`, not a distinct collection total.

## `available.json`
`{"mutability": bool, "hosts": bool}`: which optional data files exist (so a missing one costs no failed request).

## `top100.json` and `top100-evidence/<contract>.json`

Built offline by `scripts/top100/build.py` from the saved top-100 evidence. This is a separate CryptoSlam all-time Ethereum ranking, not the random census. `summary.counts` supplies the headline numbers; `collections[]` retains ranks, source identities, metadata/media routes, liveness, strict all-declared-media on-chain flags, HTTP dependencies and mutation controls. `single_key_repointable` excludes data-only edits; `single_key_mutable` is the broader EOA mutation class. `delivery_note` explains exceptional delivery results without changing their scope.

Each same-origin evidence file includes `collection`, `samples[]`, `saved_packet_index[]` (relative raw-packet paths and SHA-256 hashes), and `interpretation`. Raw packets are not shipped. Sample metadata/media attempts retain status, time and hash after public redaction. Mooncats' successful empty `tokenURI` responses have reason `empty-tokenuri`; its fallback `uri` revert is separate. `dead` describes unavailable sampled metadata, not proof of permanent loss of the artwork. Art Gobblers remains `degraded` because two samples load and one repeatedly returns 404.

## Additions (random-sample census)
* `media_location` / `media_class` / `animation_class` may be `unresolved`: the location is unknown because the off-chain metadata that names it could not be fetched. The page shows it as its own class, "Unknown (metadata unreachable)". `other` keeps its meaning (no media field, unrecognised scheme).
* `census.sampling.{universe_collections_non_spam, seed, sample_size}`: when `universe_collections_non_spam > totals.collections` the hero, census lede and Method say "random sample of N of U collections".
* `census.liveness.dead_strength: {strong, weak}` (optional): counted over dead collections only. `strong` covers DNS, TLS, HTTP errors, malformed URIs, non-JSON bodies, connection errors, parked responses and tokenURI reverts; `weak` covers IPFS/Arweave content-not-found results from public gateways. The two values sum to `liveness.dead`; the site shows them in the "Does it load today?" takeaway.
* `data/collections_extra.json` (optional, listed in `available.json` as `collections_extra`): same row schema plus `stratum`; rows outside the random sample. Loaded on demand (table checkbox) and for the claim exhibits. Tagged "outside sample" in the table, never counted in any percentage or the cross-check; `in_random_sample` column in the CSV export.
