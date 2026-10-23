# Reviewed read evidence

Each request record stores `url`, HTTP `method`, exact JSON-RPC `request` (if applicable), HTTP `status`, UTC `retrieved_at`, SHA-256, and the verbatim UTF-8 `response_text`. Parse the latter with `json.loads`; the response is stored once to avoid duplicating large inline artwork. Recompute the hash over `response_text.encode()`.

`block.json` pins the new reads to one Ethereum block. Existing census and mutability evidence retains its original snapshot date. A request's declared gas is not proof of the provider's effective cap: PublicNode responses explicitly impose 50 million gas on these calls.

`cryptoskulls_coverage.json` indexes the complete CryptoSkulls data test. `skulls_coverage.py` builds a tiny view lens, supplied only in an `eth_call` code override at the dummy address `0x000000000000000000000000000000000000cafe`. It issues only `STATICCALL`s to the real, unmodified CryptoSkullsData contract. It counts successful calls with the expected ABI length and chains a digest over every return value. Every range's raw request includes the full lens bytecode and pinned block; no transaction is sent and nothing is deployed. Attribute and pixel checks cover every index from 0 through 9,999. Standalone reads for indices 0, 1 and 9,999 retain the actual arrays. Coverage establishes availability and array lengths; it does not compare all pixels against an external image archive.

The 100-index pixel range exceeded the provider cap. The subsequent complete run uses 50-index ranges. Retain the error as a limit observation, not a data-availability verdict. Similarly, CryptoSkulls `getSvg` exceeds the cap although `getPixels` succeeds.

`claimant_tokenuris.json` indexes the additional sampled reads for reviewed claimants outside the census. The original sample token ID is used when a gallery record supplies it; otherwise ID 1 is attempted. Reverts and gas limits remain unverifiable.

The Moonbirds legacy renderer takes `artworkURI(uint256,uint32)`, not `artworkURI(uint256,uint256)`. Failed selector probes remain saved. The correct 1x BMP and raw pixel calls succeed; the 15x BMP hits the gas cap. The main tokenURI's plain revert is inconclusive; do not assert its reason from that response alone.

EulerBeats `getScriptAtIndex` returns transaction hashes, as its header explains. PublicNode did not return those historical transactions. The saved `euler_script_bs_*` Blockscout responses contain their raw calldata and block numbers. Their four `raw_input` strings concatenate to the JavaScript regeneration program.

The lens known-output control uses a later fresh block (`coverage_control_block.json`) after the provider refused state reads at the original coverage block as archive requests. The successful `coverage_control_fresh_*` lens outputs are checked against standalone `coverage_control_direct_*` arrays at that same later block. This validates the lens algorithm without changing the original coverage snapshot.
