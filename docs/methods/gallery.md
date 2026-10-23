# Offline gallery experiment

Each artwork is assembled from recorded chain responses and rendered in Chromium under three conditions: normal network
access, all non-local requests blocked, and blocked requests with a local archive of declared dependencies. Screenshots
are compared against a normal-versus-normal animation baseline. Request logs record the network behavior in each condition.

An archive of libraries cannot restore missing runtime content. A successful gallery render applies to the sampled token
and tested configuration; the census-wide on-chain pointer count is not a render-test result. Redistributed dependencies
are identified in [NOTICE](../../NOTICE); dependencies without redistribution permission retain only their manifest entry.
See [Methods](../../METHODS.md), `scripts/gallery/` and `data/gallery/`.
