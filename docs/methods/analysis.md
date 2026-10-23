# Analysis and site data

The analysis joins the census, universe, gallery and claims tables by contract address. Headline collection shares use the
uniform random stratum; the holder-ranked stratum is supplemental and must not be mixed into random-sample percentages.
Collection counts and holder exposure are reported separately. Confidence intervals describe sampling uncertainty, not
measurement or classification uncertainty.

Site collection rows retain storage classes, liveness, provenance and the available evidence summaries. Census totals are
aggregated from those rows. Withheld host names and URLs are replaced in every public dataset; provider-specific failure
signatures are generalized to HTTP/DNS classes. Raw measurements remain separate from public derivatives.
See [Methods](../../METHODS.md), `data/analysis/` and `site/data/SCHEMA.md`.
