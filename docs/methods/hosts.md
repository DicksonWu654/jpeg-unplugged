# Host-risk assessment

Host analysis combines observed HTTP and DNS behavior with registration evidence to identify takeover-risk candidates.
A missing-resource response or an unresolving provider name is a screening signal, not a verified ability to register or
recreate the resource. No registration or takeover is attempted. DNS-only and provider-response evidence have different
strengths, and aggregate candidate counts must retain that uncertainty.

Only aggregate risk counts are released. Withheld host names, URLs on those hosts and provider-specific failure signatures
are filtered from the public tables and site evidence. Per-collection storage classes and liveness remain available.
See [Methods](../../METHODS.md) and `data/hosts/summary.json`.
