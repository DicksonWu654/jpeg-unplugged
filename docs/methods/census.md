# Storage and liveness census

Sampled token identifiers are confirmed through contract calls or the indexer's instance list. Metadata, image and
animation pointers are classified separately as on-chain data, IPFS, Arweave, HTTP, other or broken. A data URI containing
an HTTP image does not make the image on-chain. Sampling cannot establish that every token in a collection behaves alike.

The pipeline distinguishes content-level liveness from the availability of the exact URL in the token. Another gateway
may serve an IPFS object even when the embedded gateway fails. Timeouts, rate limits and bot walls remain unknown;
negative fetches are retried. Reverted contract calls have separate reasons because gas limits and unrevealed tokens can
also cause reverts. See [Methods](../../METHODS.md), `scripts/census/` and `data/census/`.

Public datasets replace withheld host names and their URLs with `[withheld-host]`. Provider-specific missing-resource
signatures are reduced to generic HTTP or DNS failure classes. Storage classes and alive/dead/unknown status are retained.
