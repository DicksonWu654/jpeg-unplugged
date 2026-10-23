# Publication text checks

Offline check of visible numeric literals in key findings, card HTML and posts, plus the shared paper/site media headline. Expected values come from saved public data. Reproduce with `.venv/bin/python -I article/check_text_numbers.py`.

| Text | Visible numeric literals | Source | Result |
|---|---|---|---|
| Finding 1 | 58617, 100, 49494 | universe parquet; holder threshold | PASS |
| Finding 2 | 5.1, 152, 3000, 4.3, 5.9, 55.2, 29, 6.1 | headlines: metadata_location/onchain | PASS |
| Finding 3 | 2.9, 87, 3000, 2.4, 3.6, 152, 63, 41.4, 33.9, 49.4, 60, 41, 15, 89, 87 | headlines: any sampled media field; image subset; mixed-metadata remainder | PASS |
| Finding 4 | 30.3, 908, 3000, 28.6, 31.9, 20.9, 627, 707, 80, 2.7, 80, 6.7, 201, 6, 2.7, 33 | headlines: liveness/dead_reasons; hard evidence excludes reverts | PASS |
| Finding 5 | 39, 31 | headlines: shares of dead-or-degraded failures | PASS |
| Finding 6 | 19.7, 591, 3000, 147, 142, 402 | headlines: exact_url; gateways: Lighthouse status | PASS |
| Finding 7 | 34.5, 2021, 37.6, 2022, 15.4, 2023, 2026, 32 | headlines by_year; enriched parquet revert diagnosis | PASS |
| Finding 8 | 71, 83, 2.8, 10, 11 | gallery results; archive manifest; ten restores checked below | PASS |
| Finding 9 | 16, 474, 3.4 | Art Blocks generator survey | PASS |
| Finding 10 | 160, 81, 75, 53, 103, 51, 131, 11, 18 | reviewed claims_summary metrics; worded six/two/zero also checked | PASS |
| Finding 11 | 606, 302, 23, 203, 323, 21 | claims_summary metrics; historical class table | PASS |
| Finding 12 | 204, 232, 195 | hosts CSV; published distinct-collection aggregate | PASS |
| Finding scope | 721, 1155, 100, 3000, 49494, 2026, 10, 22, 2, 21, 24, 4, 36, 59, 95 | universe schema; headlines meta timestamps; Wilson convention | PASS |
| Card 01-cover | No numeric literals | headlines / reviewed metrics / gallery / RPC / hosts (see corresponding finding) | PASS |
| Card 02-survival | 2.9, 100, 0.1, 63, 152, 41.4, 87, 3000, 95, 2.4, 3.6, 49494, 100 | headlines / reviewed metrics / gallery / RPC / hosts (see corresponding finding) | PASS |
| Card 03-dead-today | 30.3, 20.9, 2.7, 6.7, 6, 908, 3000, 95, 28.6, 31.9 | headlines / reviewed metrics / gallery / RPC / hosts (see corresponding finding) | PASS |
| Card 04-by-year | 2022, 56.8, 2020, 37, 34.5, 2021, 290, 37.6, 2022, 1634, 15.4, 2023, 648, 23.4, 2024, 77, 9, 2025, 78, 19.9, 2026, 236, 95, 2026 | headlines / reviewed metrics / gallery / RPC / hosts (see corresponding finding) | PASS |
| Card 05-gateway-graveyard | 8, 3, 3, 3, 2, 3000, 6, 402 | headlines / reviewed metrics / gallery / RPC / hosts (see corresponding finding) | PASS |
| Card 06-claims-funnel | 53, 103, 160, 81, 103, 53, 51, 2 | headlines / reviewed metrics / gallery / RPC / hosts (see corresponding finding) | PASS |
| Card 07-genesis | 11, 83, 1 | headlines / reviewed metrics / gallery / RPC / hosts (see corresponding finding) | PASS |
| Card 08-nouns | 119, 119289149, 1500, 3, 6, 150, 1, 2, 1, 2026, 10, 21, 150, 6 | headlines / reviewed metrics / gallery / RPC / hosts (see corresponding finding) | PASS |
| Card 09-takeover | 204, 232, 309, 109, 58, 12, 25, 3621 | headlines / reviewed metrics / gallery / RPC / hosts (see corresponding finding) | PASS |
| Card og | No numeric literals | headlines / reviewed metrics / gallery / RPC / hosts (see corresponding finding) | PASS |
| Tweet 1 | 3000, 49494, 100, 83 | same saved sources as matching finding/card; SHA-256 is an algorithm identifier | PASS |
| Tweet 2 | 2.9, 87, 3000, 152, 63, 41.4 | same saved sources as matching finding/card; SHA-256 is an algorithm identifier | PASS |
| Tweet 3 | 30.3, 20.9, 2.7, 6.7, 6 | same saved sources as matching finding/card; SHA-256 is an algorithm identifier | PASS |
| Tweet 4 | 2022, 34.5, 2021, 37.6, 2022, 15.4, 2023 | same saved sources as matching finding/card; SHA-256 is an algorithm identifier | PASS |
| Tweet 5 | 100, 81, 160, 53, 103 | same saved sources as matching finding/card; SHA-256 is an algorithm identifier | PASS |
| Tweet 6 | 1, 11, 83, 2.8, 10 | same saved sources as matching finding/card; SHA-256 is an algorithm identifier | PASS |
| Tweet 7 | 1500, 119, 12, 6, 3, 150, 1, 2 | same saved sources as matching finding/card; SHA-256 is an algorithm identifier | PASS |
| Tweet 7b | 204, 232 | same saved sources as matching finding/card; SHA-256 is an algorithm identifier | PASS |
| Tweet 8 | No numeric literals | same saved sources as matching finding/card; SHA-256 is an algorithm identifier | PASS |
| Tweet 9 | 256 | same saved sources as matching finding/card; SHA-256 is an algorithm identifier | PASS |
| Paper media headline | 152, 63, 41.4, 33.9, 49.4, 60, 41, 15, 89, 87 | headlines: any sampled media field; image subset; mixed metadata | PASS |

| Post | Characters (URLs = 23) | Result |
|---|---:|---|
| 1 | 260 | PASS |
| 2 | 245 | PASS |
| 3 | 221 | PASS |
| 4 | 193 | PASS |
| 5 | 257 | PASS |
| 6 | 237 | PASS |
| 7 | 238 | PASS |
| 7b | 252 | PASS |
| 8 | 171 | PASS |
| 9 | 275 | PASS |

The media headline counts any sampled image or animation field off-chain: 63/152 (41.4%). The image-only subset is 60. Of the remaining 89, 87 are fully on-chain candidates and two have mixed metadata.

The dependent-collection host aggregate cannot be rebuilt from public redacted mappings. Host counts and fingerprints are independently checked from the public host table. This script checks HTML and post text; rendering, clipping and browser network checks are separate.

Source digests:

| Source | SHA-256 |
|---|---|
| data/analysis/headlines.json | 7bbd304b301ce68d4f2708994a7ebccbfbbaf0eb21c669df7b14f5700cf2004d |
| data/analysis/claims_summary.json | 32ecf3579f5b1d2556cf7427c3a55abca34c1c6365b5d9d2a9201159cb8e0263 |
| data/claims/claims_reviewed.csv | 1e2394f89c0de106bdf5ecca38e0b9ddd86b68772b76537986d814a10e9ec122 |
| data/gallery/results.csv | 5e7b30809e37499e0cbae3ff981370ce7408eca9eedd3b7b562f6cb184a86d84 |
| data/census/gateways.json | c5377ad7b0941f82e918caec1d0df4e252dcb9df2bd026c8364fc94e7c0af484 |
| launch/cards/rpc_check_nouns_2026-10-21.json | d4563ce375a290626488812c34bd18bf9edbe4c989ca57e015f5ddbb72ebeeaf |
