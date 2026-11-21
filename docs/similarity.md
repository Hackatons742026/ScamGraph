# Similarity and incident linking

ScamGraph links incidents only through shared, non-ignored evidence. Candidate
pairs come from an inverted index of `(type, value_hash)`: only observed shared
values create a candidate edge. An absent artifact or value is unknown, never a
disagreement. `comparable` counts evidence types available for that pair; an
edge with fewer than two comparable types is marked low-confidence. Incidents
with no shared evidence have no edge.

## Rules

- A shared tier-A value creates a campaign link by itself.
- All kit signals count as one tier-B family. Kit alone creates only a network
  link; two distinct eligible B families create a campaign link.
- Creative evidence is eligible with three shared content images or one
  near-identical ad creative.
- Tier C contributes weight but cannot create a campaign link; two different C
  types may create a network link.
- Pipeline ignore annotations are respected. The engine also rejects placeholder
  phones and known public-library displays. Values present in more than 30% of
  incidents are excluded.

Every retained value receives inverse-document-frequency weight
`log(N / df)`, where `N` is the incident count and `df` is the count of
incidents containing that value. Edge scores sum the retained weights and are
not calibrated probabilities or fraud scores.
Matched evidence preserves masked display text, source artifact IDs, funnel
steps, and a safe explanation. No raw identifier is returned.
