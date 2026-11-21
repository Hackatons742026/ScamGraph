# Offline evaluation

Evaluation never bundles labels or source data. Pass an explicit local CSV to
`load_pairs`; required columns are `left_id,right_id,campaign,network`, with
optional `mentor_campaign,mentor_network` boolean columns. IDs are opaque and
the file must remain outside git.

The deterministic synthetic suite covers seven routing situations: tier-A
match, multi-signal match, network-only evidence, no evidence, low coverage,
cross-campaign conflict, and excluded-incident rebuild. These fixtures are the
only built-in tuning input. They exercise all three outcomes without claiming
performance on confidential data.

`build_report` combines campaign/network pair precision, recall and F1; false
merges; mentor agreement when supplied; leave-one-out routing that removes each
synthetic incident and rebuilds memory; and baseline versus reduced-signal
ablation results. `GET /api/eval/report` exposes the same
contract shape. An empty local-label input reports zero metrics, not a claimed
benchmark result.
