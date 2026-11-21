# Clustering and Campaign Memory

Network clusters are connected components over every retained edge. Campaign
clusters use campaign-level edges only; connected components above the size
limit are split by deterministic single-level Louvain modularity optimisation.
Incidents without campaign membership remain explicitly **Unassigned**, even
when they have a network link.

Campaign profiles contain member IDs and the safe evidence types and families
seen on internal edges. Stable IDs derive from the first sorted member; they do
not encode real-world identity or attribution.

Campaign Memory is conservative:

- **Known Campaign:** a tier-A edge to exactly one campaign, or a campaign edge
  with at least two comparable evidence types.
- **New Campaign Candidate:** sufficient coverage and comparability, but no
  campaign-level match. A network-only link is allowed.
- **Needs Review:** low coverage, fewer than two comparable types, or strong
  matches to multiple campaigns.

`exclude_incident` removes an incident and its edges before rebuilding clusters,
supporting leave-one-out evaluation without hard-coded case IDs.
