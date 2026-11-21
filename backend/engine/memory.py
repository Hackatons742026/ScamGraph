"""Deterministic clustering and conservative Campaign Memory decisions."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .linking import LinkEdge


@dataclass(frozen=True)
class Campaign:
    id: str
    level: str
    members: tuple[str, ...]
    evidence_types: tuple[str, ...]
    families: tuple[str, ...]


@dataclass(frozen=True)
class ClusterResult:
    networks: tuple[Campaign, ...]
    campaigns: tuple[Campaign, ...]
    unassigned: tuple[str, ...]
    campaign_by_incident: Mapping[str, str]


@dataclass(frozen=True)
class Classification:
    outcome: str
    campaign_id: str | None
    reasons: tuple[str, ...]


class _UnionFind:
    def __init__(self, nodes: Iterable[str]):
        self.parent = {node: node for node in nodes}

    def find(self, node: str) -> str:
        while self.parent[node] != node:
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    def union(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[max(a, b)] = min(a, b)

    def groups(self) -> list[tuple[str, ...]]:
        groups: dict[str, list[str]] = defaultdict(list)
        for node in sorted(self.parent):
            groups[self.find(node)].append(node)
        return [tuple(nodes) for nodes in groups.values()]


def _components(nodes: Iterable[str], edges: Iterable[LinkEdge]) -> list[tuple[str, ...]]:
    union = _UnionFind(nodes)
    for edge in edges:
        union.union(edge.source, edge.target)
    return union.groups()


def _louvain(nodes: Sequence[str], edges: Sequence[LinkEdge]) -> list[tuple[str, ...]]:
    """Single-level Louvain local moving with deterministic tie-breaking."""
    adjacency: dict[str, dict[str, float]] = {node: {} for node in nodes}
    for edge in edges:
        weight = max(edge.score, 0.000001)
        adjacency[edge.source][edge.target] = adjacency[edge.source].get(edge.target, 0) + weight
        adjacency[edge.target][edge.source] = adjacency[edge.target].get(edge.source, 0) + weight
    degree = {node: sum(neighbors.values()) for node, neighbors in adjacency.items()}
    total = sum(degree.values())
    if not total:
        return [(node,) for node in sorted(nodes)]
    community = {node: node for node in nodes}
    totals = dict(degree)
    for _ in range(20):
        changed = False
        for node in sorted(nodes):
            current = community[node]
            totals[current] -= degree[node]
            weights: dict[str, float] = defaultdict(float)
            for neighbor, weight in adjacency[node].items():
                weights[community[neighbor]] += weight
            candidates = sorted(weights)
            best, best_gain = current, 0.0
            for candidate in candidates:
                gain = weights[candidate] - degree[node] * totals[candidate] / total
                if gain > best_gain + 1e-12:
                    best, best_gain = candidate, gain
            community[node] = best
            totals[best] = totals.get(best, 0) + degree[node]
            changed |= best != current
        if not changed:
            break
    groups: dict[str, list[str]] = defaultdict(list)
    for node in sorted(nodes):
        groups[community[node]].append(node)
    return sorted((tuple(group) for group in groups.values()), key=lambda group: group[0])


def _profile(identifier: str, level: str, members: Sequence[str], edges: Sequence[LinkEdge]) -> Campaign:
    member_set = set(members)
    internal = [edge for edge in edges if edge.source in member_set and edge.target in member_set]
    types = {match.type for edge in internal for match in edge.evidence}
    families = {family for edge in internal for family in edge.families}
    return Campaign(identifier, level, tuple(sorted(members)), tuple(sorted(types)), tuple(sorted(families)))


def cluster_incidents(
    incident_ids: Iterable[str],
    edges: Sequence[LinkEdge],
    *,
    exclude_incident: str | None = None,
    max_campaign_size: int = 20,
) -> ClusterResult:
    nodes = sorted(set(incident_ids) - ({exclude_incident} if exclude_incident else set()))
    usable = [edge for edge in edges if edge.source in nodes and edge.target in nodes]
    network_groups = _components(nodes, usable)
    campaign_edges = [edge for edge in usable if edge.level == "campaign"]
    raw_campaigns = [group for group in _components(nodes, campaign_edges) if len(group) > 1]
    campaign_groups: list[tuple[str, ...]] = []
    for group in raw_campaigns:
        internal = [edge for edge in campaign_edges if edge.source in group and edge.target in group]
        campaign_groups.extend(_louvain(group, internal) if len(group) > max_campaign_size else [group])
    campaign_groups = [group for group in campaign_groups if len(group) > 1]

    networks = tuple(
        _profile(f"network-{group[0]}", "network", group, usable)
        for group in network_groups if len(group) > 1
    )
    campaigns = tuple(
        _profile(f"campaign-{group[0]}", "campaign", group, campaign_edges)
        for group in sorted(campaign_groups)
    )
    membership = {member: campaign.id for campaign in campaigns for member in campaign.members}
    unassigned = tuple(node for node in nodes if node not in membership)
    return ClusterResult(networks, campaigns, unassigned, membership)


def classify(
    candidate_id: str,
    candidate_edges: Sequence[LinkEdge],
    clusters: ClusterResult,
    *,
    coverage_ok: bool,
    exclude_incident: str | None = None,
) -> Classification:
    matches: dict[str, list[LinkEdge]] = defaultdict(list)
    maximum_comparable = 0
    relevant_edges = 0
    for edge in candidate_edges:
        if candidate_id not in {edge.source, edge.target}:
            continue
        other = edge.target if edge.source == candidate_id else edge.source
        if other == candidate_id or other == exclude_incident:
            continue
        relevant_edges += 1
        maximum_comparable = max(maximum_comparable, edge.comparable)
        campaign_id = clusters.campaign_by_incident.get(other)
        strong = edge.level == "campaign" and (edge.tier == "A" or edge.comparable >= 2)
        if campaign_id and strong:
            matches[campaign_id].append(edge)
    if len(matches) > 1:
        names = ", ".join(sorted(matches))
        return Classification("needs_review", None, (f"Strong evidence conflicts across campaigns: {names}.",))
    if matches:
        campaign_id, matching = next(iter(matches.items()))
        strongest = "tier A" if any(edge.tier == "A" for edge in matching) else "multiple evidence families"
        return Classification("known_campaign", campaign_id, (f"Known campaign match via {strongest}.",))
    if not coverage_ok or (relevant_edges and maximum_comparable < 2):
        return Classification("needs_review", None, ("Coverage is too low for a reliable campaign decision.",))
    return Classification("new_candidate", None, ("No campaign-level match was found with sufficient coverage.",))
